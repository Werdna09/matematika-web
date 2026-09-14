\
import re
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

from exams.models import Exam, ExamTask
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


TASK_START_RE = re.compile(
    r"\\uloha\s*\{\s*(\d+)\s*\}\s*"
    r"\{\s*\\zadani\s*"
    r"\{\s*(\d+)\s*\}\s*"
    r"\{\s*([-+]?\d+(?:[.,]\d+)?)mm\s*\}\s*"
    r"\{\s*([-+]?\d+(?:[.,]\d+)?)mm\s*\}\s*"
    r"\{\s*([-+]?\d+(?:[.,]\d+)?)mm\s*\}\s*"
    r"\{\s*([-+]?\d+(?:[.,]\d+)?)mm\s*\}\s*"
    r"\}",
    flags=re.DOTALL,
)


RESULT_COMMAND = r"\vysledek"


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


def _document_body_end(source):
    matches = list(DOCUMENT_END_RE.finditer(source))
    if not matches:
        return len(source)
    return matches[-1].start()


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
    matches = list(TASK_START_RE.finditer(source))

    if not matches:
        raise ExamImportError(
            "V LaTeXu nebyla nalezena žádná úloha ve tvaru "
            r"\uloha{N}{\zadani{page}{left}{bottom}{right}{top}}."
        )

    body_end = _document_body_end(source)
    tasks = []
    seen_numbers = set()

    for index, match in enumerate(matches):
        number = int(match.group(1))

        if number in seen_numbers:
            raise ExamImportError(f"Úloha {number} je v LaTeXu uvedena vícekrát.")
        seen_numbers.add(number)

        solution_start = match.end()
        solution_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else body_end
        )

        solution_tex = source[solution_start:solution_end].strip()

        tasks.append(
            {
                "number": number,
                "order": index + 1,
                "page_number": int(match.group(2)),
                "trim_left_mm": _decimal(match.group(3)),
                "trim_bottom_mm": _decimal(match.group(4)),
                "trim_right_mm": _decimal(match.group(5)),
                "trim_top_mm": _decimal(match.group(6)),
                "solution_tex": solution_tex,
            }
        )

    return tasks


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
        try:
            statement_png = renderer.render(
                page_number=task["page_number"],
                trim_left_mm=task["trim_left_mm"],
                trim_bottom_mm=task["trim_bottom_mm"],
                trim_right_mm=task["trim_right_mm"],
                trim_top_mm=task["trim_top_mm"],
            )
        except PdfCropRenderError as error:
            raise ExamImportError(
                f"Úloha {task['number']}: {error}"
            ) from error

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
                "statement_png": statement_png,
                "solution_html": solution_html,
            }
        )

    imported_numbers = set()

    with transaction.atomic():
        for task in prepared:
            number = task["number"]
            imported_numbers.add(number)

            image_name = (
                f"generated/exams/{exam.slug}/task-{number:02d}.png"
            )

            if default_storage.exists(image_name):
                default_storage.delete(image_name)

            saved_image_name = default_storage.save(
                image_name,
                ContentFile(task["statement_png"]),
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
