import base64
import re
import struct
import subprocess
import tempfile

from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction

from materials.services.tex_preprocessor import preprocess_tex
from materials.services.tikz_renderer import TikzRenderError, render_tikz_figures

from exams.models import ExamTask
from exams.services.pdf_crop_renderer import PdfCropRenderError, PdfCropRenderer


class ExamImportError(Exception):
    pass


LUA_FILTER = (
    Path(settings.BASE_DIR)
    / "materials"
    / "services"
    / "pandoc"
    / "mathera.lua"
)


DOCUMENT_BEGIN_RE = re.compile(r"\\begin\{document\}")
DOCUMENT_END_RE = re.compile(r"\\end\{document\}")
TASK_COMMAND_RE = re.compile(r"\\uloha\b")
STATEMENT_COMMAND_RE = re.compile(r"\\zadani\b")

RESULT_COMMAND = r"\vysledek"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _decimal(value):
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation as error:
        raise ExamImportError(f"Neplatná hodnota ořezu: {value}") from error


def _extract_preamble(source):
    match = DOCUMENT_BEGIN_RE.search(source)
    if match is None:
        return ""
    return source[:match.start()].rstrip()


def _document_body_bounds(source):
    begin_match = DOCUMENT_BEGIN_RE.search(source)
    body_start = begin_match.end() if begin_match is not None else 0

    end_matches = list(DOCUMENT_END_RE.finditer(source))
    body_end = end_matches[-1].start() if end_matches else len(source)

    return body_start, body_end


def _is_escaped(source, index):
    backslashes = 0
    index -= 1

    while index >= 0 and source[index] == "\\":
        backslashes += 1
        index -= 1

    return backslashes % 2 == 1


def _mask_latex_comments(source):
    """Nahradí obsah LaTeXových komentářů mezerami a zachová indexy."""

    chars = list(source)
    index = 0

    while index < len(chars):
        if chars[index] != "%" or _is_escaped(source, index):
            index += 1
            continue

        while index < len(chars) and chars[index] not in "\r\n":
            chars[index] = " "
            index += 1

    return "".join(chars)


def _skip_space_and_comments(source, index):
    while index < len(source):
        if source[index].isspace():
            index += 1
            continue

        if source[index] == "%" and not _is_escaped(source, index):
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            continue

        break

    return index


def _read_braced_argument(source, index, *, context):
    """Vrátí (obsah argumentu, index za uzavírací závorkou)."""

    index = _skip_space_and_comments(source, index)

    if index >= len(source) or source[index] != "{":
        raise ExamImportError(
            f"{context}: očekává se složený argument v {{...}}."
        )

    argument_start = index + 1
    depth = 1
    index += 1

    while index < len(source):
        char = source[index]

        if char == "%" and not _is_escaped(source, index):
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            continue

        if char == "{" and not _is_escaped(source, index):
            depth += 1
        elif char == "}" and not _is_escaped(source, index):
            depth -= 1

            if depth == 0:
                return source[argument_start:index], index + 1

        index += 1

    raise ExamImportError(
        f"{context}: neuzavřený složený argument."
    )


def _parse_trim_mm(value, *, task_number, crop_number, name):
    value = value.strip()

    match = re.fullmatch(
        r"([-+]?\d+(?:[.,]\d+)?)\s*mm",
        value,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise ExamImportError(
            f"Úloha {task_number}, výřez {crop_number}: "
            f"neplatná hodnota {name}: {value!r}. Očekávám např. 17.5mm."
        )

    return _decimal(match.group(1))


def _parse_statement_crops(task_body, *, task_number):
    masked_body = _mask_latex_comments(task_body)
    matches = list(STATEMENT_COMMAND_RE.finditer(masked_body))

    if not matches:
        raise ExamImportError(
            f"Úloha {task_number}: uvnitř \\uloha chybí příkaz \\zadani."
        )

    crops = []

    for crop_index, match in enumerate(matches, start=1):
        cursor = match.end()
        args = []

        for argument_number in range(5):
            argument, cursor = _read_braced_argument(
                task_body,
                cursor,
                context=(
                    f"Úloha {task_number}, výřez {crop_index}, "
                    f"argument {argument_number + 1} příkazu \\zadani"
                ),
            )
            args.append(argument.strip())

        try:
            page_number = int(args[0])
        except ValueError as error:
            raise ExamImportError(
                f"Úloha {task_number}, výřez {crop_index}: "
                f"neplatné číslo strany {args[0]!r}."
            ) from error

        crops.append(
            {
                "page_number": page_number,
                "trim_left_mm": _parse_trim_mm(
                    args[1],
                    task_number=task_number,
                    crop_number=crop_index,
                    name="left",
                ),
                "trim_bottom_mm": _parse_trim_mm(
                    args[2],
                    task_number=task_number,
                    crop_number=crop_index,
                    name="bottom",
                ),
                "trim_right_mm": _parse_trim_mm(
                    args[3],
                    task_number=task_number,
                    crop_number=crop_index,
                    name="right",
                ),
                "trim_top_mm": _parse_trim_mm(
                    args[4],
                    task_number=task_number,
                    crop_number=crop_index,
                    name="top",
                ),
            }
        )

    return crops


def _replace_balanced_command(source, command, replacer):
    """Nahradí příkaz s jedním složeným argumentem; argument může být vnořený."""

    pieces = []
    cursor = 0

    while True:
        start = source.find(command, cursor)
        if start < 0:
            pieces.append(source[cursor:])
            break

        pieces.append(source[cursor:start])

        index = start + len(command)
        while index < len(source) and source[index].isspace():
            index += 1

        if index >= len(source) or source[index] != "{":
            pieces.append(command)
            cursor = start + len(command)
            continue

        depth = 0
        arg_start = index + 1
        index += 1

        while index < len(source):
            char = source[index]

            if char == "{" and (index == 0 or source[index - 1] != "\\"):
                depth += 1
            elif char == "}" and (index == 0 or source[index - 1] != "\\"):
                if depth == 0:
                    argument = source[arg_start:index]
                    pieces.append(replacer(argument))
                    cursor = index + 1
                    break
                depth -= 1

            index += 1
        else:
            raise ExamImportError(
                f"Příkaz {command} má neuzavřený argument."
            )

    return "".join(pieces)


def _prepare_solution_tex(solution_tex):
    return _replace_balanced_command(
        solution_tex,
        RESULT_COMMAND,
        lambda body: (
            "\n\\par\\medskip\n"
            "\\textbf{Výsledek:} "
            + body.strip()
            + "\n\\par\n"
        ),
    )


def parse_exam_tasks(source):
    body_start, body_end = _document_body_bounds(source)
    masked_source = _mask_latex_comments(source)

    task_matches = list(
        TASK_COMMAND_RE.finditer(
            masked_source,
            body_start,
            body_end,
        )
    )

    if not task_matches:
        raise ExamImportError(
            "V LaTeXu nebyla nalezena žádná úloha ve tvaru "
            r"\uloha{N}{\zadani{page}{left}{bottom}{right}{top}}."
        )

    parsed_starts = []
    seen_numbers = set()

    for match in task_matches:
        cursor = match.end()

        number_text, cursor = _read_braced_argument(
            source,
            cursor,
            context="Příkaz \\uloha – číslo úlohy",
        )

        try:
            number = int(number_text.strip())
        except ValueError as error:
            raise ExamImportError(
                f"Neplatné číslo úlohy: {number_text!r}."
            ) from error

        if number in seen_numbers:
            raise ExamImportError(
                f"Úloha {number} je v LaTeXu uvedena vícekrát."
            )
        seen_numbers.add(number)

        task_body, command_end = _read_braced_argument(
            source,
            cursor,
            context=f"Úloha {number} – zadání",
        )

        crops = _parse_statement_crops(
            task_body,
            task_number=number,
        )

        parsed_starts.append(
            {
                "number": number,
                "command_start": match.start(),
                "command_end": command_end,
                "crops": crops,
            }
        )

    tasks = []

    for index, parsed in enumerate(parsed_starts):
        solution_start = parsed["command_end"]
        solution_end = (
            parsed_starts[index + 1]["command_start"]
            if index + 1 < len(parsed_starts)
            else body_end
        )

        solution_tex = source[solution_start:solution_end].strip()
        first_crop = parsed["crops"][0]

        tasks.append(
            {
                "number": parsed["number"],
                "order": index + 1,
                # Zachováváme původní DB pole kvůli kompatibilitě.
                # U více výřezů obsahují údaje prvního výřezu.
                **first_crop,
                "crops": parsed["crops"],
                "solution_tex": solution_tex,
            }
        )

    return tasks


def _png_dimensions(png_bytes):
    if len(png_bytes) < 24 or not png_bytes.startswith(PNG_SIGNATURE):
        raise ExamImportError(
            "Interní chyba: renderer zadání nevytvořil platný PNG soubor."
        )

    if png_bytes[12:16] != b"IHDR":
        raise ExamImportError(
            "Interní chyba: PNG zadání nemá očekávanou hlavičku IHDR."
        )

    width, height = struct.unpack(">II", png_bytes[16:24])

    if width <= 0 or height <= 0:
        raise ExamImportError(
            "Interní chyba: PNG zadání má neplatné rozměry."
        )

    return width, height


def _combine_statement_pngs_as_svg(png_images, *, gap_px=18):
    """
    Spojí více PNG výřezů do jednoho SVG bez další image dependency.

    Každý výřez zůstane samostatný a je vložen jako PNG data URI. Prohlížeč
    výsledné SVG normálně zobrazí uvnitř stávajícího <img> v šabloně.
    """

    if not png_images:
        raise ExamImportError(
            "Interní chyba: úloha nemá žádný výřez zadání."
        )

    sizes = [
        _png_dimensions(image)
        for image in png_images
    ]

    canvas_width = max(width for width, _ in sizes)
    canvas_height = (
        sum(height for _, height in sizes)
        + gap_px * (len(sizes) - 1)
    )

    elements = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{canvas_width}" height="{canvas_height}" '
            f'viewBox="0 0 {canvas_width} {canvas_height}">'
        ),
        f'<rect width="{canvas_width}" height="{canvas_height}" fill="white"/>',
    ]

    y = 0

    for image, (width, height) in zip(png_images, sizes):
        x = (canvas_width - width) / 2
        encoded = base64.b64encode(image).decode("ascii")

        elements.append(
            f'<image x="{x:g}" y="{y:g}" '
            f'width="{width}" height="{height}" '
            f'href="data:image/png;base64,{encoded}"/>'
        )

        y += height + gap_px

    elements.append("</svg>")

    return "\n".join(elements).encode("utf-8")


def _prepare_statement_file(renderer, task):
    rendered_crops = []

    for crop_index, crop in enumerate(task["crops"], start=1):
        try:
            rendered_crops.append(
                renderer.render(
                    page_number=crop["page_number"],
                    trim_left_mm=crop["trim_left_mm"],
                    trim_bottom_mm=crop["trim_bottom_mm"],
                    trim_right_mm=crop["trim_right_mm"],
                    trim_top_mm=crop["trim_top_mm"],
                )
            )
        except PdfCropRenderError as error:
            raise ExamImportError(
                f"Úloha {task['number']}, výřez {crop_index}: {error}"
            ) from error

    if len(rendered_crops) == 1:
        return rendered_crops[0], "png"

    return _combine_statement_pngs_as_svg(rendered_crops), "svg"


def _run_pandoc(source, source_dir):
    processed_tex = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tex",
            prefix=".mathera_exam_",
            encoding="utf-8",
            dir=source_dir,
            delete=False,
        ) as temp_file:
            temp_file.write(source)
            processed_tex = Path(temp_file.name)

        try:
            result = subprocess.run(
                [
                    "pandoc",
                    processed_tex.name,
                    "--from=latex",
                    "--to=html5",
                    "--mathjax",
                    "--wrap=none",
                    "--lua-filter",
                    str(LUA_FILTER),
                ],
                cwd=source_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except FileNotFoundError as error:
            raise ExamImportError(
                "Pandoc nebyl nalezen. Zkontroluj, že je dostupný v PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise ExamImportError(
                "Pandoc nedokázal převést řešení:\n" + error.stderr
            ) from error

        return result.stdout.strip()

    finally:
        if processed_tex is not None:
            processed_tex.unlink(missing_ok=True)


def _solution_to_html(*, exam, task, preamble, source_dir):
    solution = _prepare_solution_tex(task["solution_tex"])

    source = (
        preamble
        + "\n\\begin{document}\n"
        + solution
        + "\n\\end{document}\n"
    )

    try:
        source = render_tikz_figures(
            source,
            material_slug=f"exam-{exam.slug}-task-{task['number']:02d}",
            source_dir=source_dir,
        )
    except TikzRenderError as error:
        raise ExamImportError(
            f"Úloha {task['number']}: TikZ/PGFPlots se nepodařilo zpracovat:\n{error}"
        ) from error

    source = preprocess_tex(source)

    try:
        return _run_pandoc(source, source_dir)
    except ExamImportError as error:
        raise ExamImportError(
            f"Úloha {task['number']}: {error}"
        ) from error


def import_exam_tex(exam):
    if not exam.source_tex:
        raise ExamImportError("Maturita nemá nahraný zdrojový .tex soubor.")

    if not exam.source_pdf:
        raise ExamImportError("Maturita nemá nahrané originální PDF zadání.")

    try:
        source_tex_path = Path(exam.source_tex.path)
        source_pdf_path = Path(exam.source_pdf.path)
    except (NotImplementedError, ValueError) as error:
        raise ExamImportError(
            "Import maturity zatím vyžaduje lokální filesystem storage."
        ) from error

    try:
        source = source_tex_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ExamImportError(
            f"Zdrojový LaTeX nelze načíst: {error}"
        ) from error

    tasks = parse_exam_tasks(source)
    preamble = _extract_preamble(source)
    source_dir = source_tex_path.parent

    renderer = PdfCropRenderer(source_pdf_path, dpi=180)
    prepared = []

    # Vše nejdřív připravíme mimo DB transakci. Při chybě zůstane starý import zachovaný.
    for task in tasks:
        statement_file, statement_extension = _prepare_statement_file(
            renderer,
            task,
        )

        solution_html = _solution_to_html(
            exam=exam,
            task=task,
            preamble=preamble,
            source_dir=source_dir,
        )

        if not solution_html:
            raise ExamImportError(
                f"Úloha {task['number']}: Pandoc vytvořil prázdné řešení."
            )

        prepared.append(
            {
                **task,
                "statement_file": statement_file,
                "statement_extension": statement_extension,
                "solution_html": solution_html,
            }
        )

    imported_numbers = set()

    with transaction.atomic():
        for task in prepared:
            number = task["number"]
            imported_numbers.add(number)

            image_base = (
                f"generated/exams/{exam.slug}/task-{number:02d}"
            )

            # Pokud se počet výřezů mezi importy změnil, odstraníme obě možné varianty.
            for extension in ("png", "svg"):
                stale_name = f"{image_base}.{extension}"

                if default_storage.exists(stale_name):
                    default_storage.delete(stale_name)

            image_name = (
                f"{image_base}.{task['statement_extension']}"
            )

            saved_image_name = default_storage.save(
                image_name,
                ContentFile(task["statement_file"]),
            )

            ExamTask.objects.update_or_create(
                exam=exam,
                number=number,
                defaults={
                    "order": task["order"],
                    "page_number": task["page_number"],
                    "trim_left_mm": task["trim_left_mm"],
                    "trim_bottom_mm": task["trim_bottom_mm"],
                    "trim_right_mm": task["trim_right_mm"],
                    "trim_top_mm": task["trim_top_mm"],
                    "statement_image": saved_image_name,
                    "solution_tex": task["solution_tex"],
                    "solution_html": task["solution_html"],
                },
            )

        exam.tasks.exclude(number__in=imported_numbers).delete()

    return len(prepared)
