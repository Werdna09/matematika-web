import re
import subprocess
import tempfile

from html import unescape
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify

from materials.models import Material, MaterialSection, MaterialType
from materials.services.tex_preprocessor import preprocess_tex
from materials.services.tikz_renderer import TikzRenderError, render_tikz_figures


class TexImportError(Exception):
    pass


LUA_FILTER = (
    Path(__file__).resolve().parent
    / "pandoc"
    / "mathera.lua"
)


PRACTICE_TYPE_SLUG = "procvicovani"
PRACTICE_TYPE_NAME = "Procvičování"
PRACTICE_SECTION_TITLE = "Příklady k procvičení"
PRACTICE_SECTION_SLUG = "priklady-k-procviceni"


HEADING_RE = re.compile(
    r"<h([1-6])([^>]*)>(.*?)</h\1>",
    flags=re.IGNORECASE | re.DOTALL,
)

ID_RE = re.compile(
    r'\bid=["\']([^"\']+)["\']',
    flags=re.IGNORECASE,
)

TAG_RE = re.compile(
    r"<[^>]+>"
)

DOCUMENT_BEGIN_RE = re.compile(
    r"\\begin\{document\}"
)

DOCUMENT_END_RE = re.compile(
    r"\\end\{document\}"
)

EXERCISE_PART_RE = re.compile(
    r"\\exercisepart\b"
)

LEADING_SECTION_COUNTER_RE = re.compile(
    r"^\s*"
    r"\\setcounter\s*"
    r"\{\s*section\s*\}"
    r"\s*"
    r"\{\s*\d+\s*\}"
    r"\s*",
    flags=re.DOTALL,
)


def _heading_text(html):
    text = TAG_RE.sub("", html)
    return unescape(text).strip()


def _unique_slug(base_slug, used_slugs):
    slug = base_slug or "kapitola"

    candidate = slug
    counter = 2

    while candidate in used_slugs:
        candidate = f"{slug}-{counter}"
        counter += 1

    used_slugs.add(candidate)

    return candidate


def _mask_latex_comments(source):
    """
    Zamaskuje LaTeXové komentáře mezerami, ale zachová délku textu.

    Díky tomu se zakomentované \\exercisepart nepovažuje za skutečný
    předěl mezi učebním textem a procvičováním.
    """

    chars = list(source)
    index = 0

    while index < len(chars):
        if chars[index] != "%":
            index += 1
            continue

        backslashes = 0
        check_index = index - 1

        while check_index >= 0 and chars[check_index] == "\\":
            backslashes += 1
            check_index -= 1

        if backslashes % 2 == 1:
            index += 1
            continue

        while index < len(chars) and chars[index] not in "\r\n":
            chars[index] = " "
            index += 1

    return "".join(chars)


def _split_source_at_exercise_part(source):
    """
    Rozdělí jeden LaTeXový dokument na:

    1. učební text před \\exercisepart,
    2. procvičování za \\exercisepart.

    Pokud jde o kompletní LaTeXový dokument, obě části dostanou stejnou
    preambuli a vlastní \\begin{document} / \\end{document}. To je důležité
    kvůli TikZu, PGFPlots i vlastním makrům.
    """

    masked = _mask_latex_comments(source)

    begin_match = DOCUMENT_BEGIN_RE.search(masked)
    end_matches = list(DOCUMENT_END_RE.finditer(masked))

    if begin_match is not None and end_matches:
        end_match = end_matches[-1]

        if end_match.start() > begin_match.end():
            body_start = begin_match.end()
            body_end = end_match.start()
        else:
            body_start = 0
            body_end = len(source)
    else:
        body_start = 0
        body_end = len(source)

    exercise_match = EXERCISE_PART_RE.search(
        masked,
        body_start,
        body_end,
    )

    if exercise_match is None:
        return source, None

    theory_body = source[
        body_start:exercise_match.start()
    ]

    practice_body = source[
        exercise_match.end():body_end
    ]

    # Ve zdrojových PDF se po \exercisepart často ručně nastavuje číslo
    # sekce kvůli číslování úloh. Pro samostatnou webovou stránku to
    # nepotřebujeme.
    practice_body = LEADING_SECTION_COUNTER_RE.sub(
        "",
        practice_body,
        count=1,
    )

    if body_start == 0 and body_end == len(source):
        return (
            theory_body.strip() + "\n",
            practice_body.strip() + "\n",
        )

    prefix = source[:body_start]
    suffix = source[body_end:]

    theory_source = (
        prefix
        + theory_body
        + "\n"
        + suffix
    )

    practice_source = (
        prefix
        + "\n"
        + practice_body
        + "\n"
        + suffix
    )

    return theory_source, practice_source


def _split_html_into_sections(html):
    headings = list(
        HEADING_RE.finditer(html)
    )

    if not headings:
        raise TexImportError(
            "Pandoc vytvořil HTML, ale nebyly v něm nalezeny žádné nadpisy."
        )

    # Nejvyšší úroveň nadpisu v dokumentu považujeme
    # za jednotlivé kapitoly.
    top_level = min(
        int(match.group(1))
        for match in headings
    )

    chapter_headings = [
        match
        for match in headings
        if int(match.group(1)) == top_level
    ]

    if not chapter_headings:
        raise TexImportError(
            "Nepodařilo se určit kapitoly dokumentu."
        )

    sections = []
    used_slugs = set()

    for index, heading in enumerate(chapter_headings):
        title = _heading_text(
            heading.group(3)
        )

        if not title:
            title = f"Kapitola {index + 1}"

        attributes = heading.group(2)

        id_match = ID_RE.search(
            attributes
        )

        if id_match:
            base_slug = slugify(
                id_match.group(1)
            )
        else:
            base_slug = slugify(
                title
            )

        section_slug = _unique_slug(
            base_slug,
            used_slugs,
        )

        content_start = heading.end()

        if index + 1 < len(chapter_headings):
            content_end = chapter_headings[
                index + 1
            ].start()
        else:
            content_end = len(html)

        content = html[
            content_start:content_end
        ].strip()

        sections.append(
            {
                "title": title,
                "slug": section_slug,
                "html_content": content,
            }
        )

    return sections


def _run_pandoc(source, source_dir):
    processed_tex = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tex",
            prefix=".mathera_",
            encoding="utf-8",
            dir=source_dir,
            delete=False,
        ) as temp_file:
            temp_file.write(source)

            processed_tex = Path(
                temp_file.name
            )

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
                check=True,
            )

        except FileNotFoundError:
            raise TexImportError(
                "Pandoc nebyl nalezen. "
                "Zkontroluj, že je nainstalovaný "
                "a dostupný v PATH."
            )

        except subprocess.CalledProcessError as error:
            raise TexImportError(
                "Pandoc nedokázal LaTeX převést:\n"
                + error.stderr
            ) from error

        return result.stdout

    finally:
        if processed_tex is not None:
            processed_tex.unlink(
                missing_ok=True
            )


def _convert_source_to_html(
    source,
    *,
    material_slug,
    source_dir,
    part_name,
):
    """
    TikZ/PGFPlots -> SVG, Mathera preprocessing -> Pandoc -> HTML.
    """

    try:
        source = render_tikz_figures(
            source,
            material_slug=material_slug,
            source_dir=source_dir,
        )

    except TikzRenderError as error:
        raise TexImportError(
            f"{part_name}: TikZ/PGFPlots obrázky se nepodařilo zpracovat:\n"
            + str(error)
        ) from error

    source = preprocess_tex(
        source
    )

    try:
        return _run_pandoc(
            source,
            source_dir,
        )

    except TexImportError as error:
        raise TexImportError(
            f"{part_name}: {error}"
        ) from error


def _get_practice_type():
    practice_type = (
        MaterialType.objects
        .filter(slug=PRACTICE_TYPE_SLUG)
        .first()
    )

    if practice_type is None:
        practice_type = (
            MaterialType.objects
            .filter(name__iexact=PRACTICE_TYPE_NAME)
            .first()
        )

    if practice_type is None:
        raise TexImportError(
            'V databázi chybí typ materiálu "Procvičování". '
            'V administraci vytvoř MaterialType s názvem "Procvičování" '
            'a slugem "procvicovani".'
        )

    return practice_type


def _practice_material_slug(material, existing_practice=None):
    if existing_practice is not None:
        return existing_practice.slug

    base = slugify(
        f"{material.slug}-procvicovani"
    )[:190].rstrip("-")

    if not base:
        base = "procvicovani"

    candidate = base
    counter = 2

    while Material.objects.filter(
        slug=candidate
    ).exists():
        suffix = f"-{counter}"
        candidate = (
            base[:200 - len(suffix)].rstrip("-")
            + suffix
        )
        counter += 1

    return candidate


def _replace_sections(material, sections):
    material.sections.all().delete()

    created_sections = []

    for order, section_data in enumerate(
        sections,
        start=1,
    ):
        section = MaterialSection.objects.create(
            material=material,
            title=section_data["title"],
            slug=section_data["slug"],
            html_content=section_data["html_content"],
            order=order,
        )

        created_sections.append(
            section
        )

    return created_sections


def import_material_tex(material, tex_file=None):
    if material.source_material_id:
        raise TexImportError(
            "Odvozený materiál se neimportuje samostatně. "
            "Reimportuj jeho zdrojový učební materiál."
        )

    if tex_file is None:
        if not material.source_tex:
            raise TexImportError(
                f'Materiál "{material.title}" '
                "nemá nahraný zdrojový LaTeX."
            )

        try:
            tex_file = Path(
                material.source_tex.path
            ).resolve()

        except (NotImplementedError, ValueError):
            raise TexImportError(
                "Zdrojový LaTeX není dostupný jako lokální soubor."
            )

    else:
        tex_file = Path(
            tex_file
        ).resolve()

    if not tex_file.exists():
        raise TexImportError(
            f"Soubor neexistuje: {tex_file}"
        )

    if tex_file.suffix.lower() != ".tex":
        raise TexImportError(
            "Zdrojový soubor musí mít příponu .tex."
        )

    if not LUA_FILTER.exists():
        raise TexImportError(
            f"Pandoc filtr nebyl nalezen: {LUA_FILTER}"
        )

    try:
        source = tex_file.read_text(
            encoding="utf-8",
        )

    except UnicodeDecodeError as error:
        raise TexImportError(
            "Zdrojový LaTeX není uložen v UTF-8."
        ) from error

    except OSError as error:
        raise TexImportError(
            f"Zdrojový LaTeX se nepodařilo načíst: {error}"
        ) from error

    # =====================================================
    # ROZDĚLENÍ UČEBNÍHO TEXTU A PROCVIČOVÁNÍ
    # =====================================================

    theory_source, practice_source = (
        _split_source_at_exercise_part(
            source
        )
    )

    practice_type = None
    existing_practice = None
    practice_slug = None

    if practice_source is not None:
        practice_type = _get_practice_type()

        existing_practice = (
            Material.objects
            .filter(
                source_material=material,
                material_type=practice_type,
            )
            .order_by("pk")
            .first()
        )

        practice_slug = _practice_material_slug(
            material,
            existing_practice,
        )

    # =====================================================
    # UČEBNÍ TEXT -> HTML
    # =====================================================

    theory_html = _convert_source_to_html(
        theory_source,
        material_slug=material.slug,
        source_dir=tex_file.parent,
        part_name="Učební text",
    )

    theory_sections = _split_html_into_sections(
        theory_html
    )

    # =====================================================
    # PROCVIČOVÁNÍ -> HTML
    # =====================================================

    practice_html = None

    if practice_source is not None:
        practice_html = _convert_source_to_html(
            practice_source,
            material_slug=practice_slug,
            source_dir=tex_file.parent,
            part_name="Procvičování",
        ).strip()

        if not practice_html:
            raise TexImportError(
                "Za \\exercisepart nebyl nalezen žádný obsah."
            )

    # =====================================================
    # AKTUALIZACE DATABÁZE
    # =====================================================
    #
    # Do databáze saháme až poté, co úspěšně vznikl HTML výstup
    # učebnice i procvičování. Při chybě tedy původní webová verze
    # zůstane zachována.

    with transaction.atomic():
        created_sections = _replace_sections(
            material,
            theory_sections,
        )

        if practice_source is not None:
            practice = existing_practice

            if practice is None:
                practice = Material(
                    source_material=material,
                    material_type=practice_type,
                    slug=practice_slug,
                )

            practice.title = (
                f"{material.title} – procvičování"
            )
            practice.description = (
                f"Procvičování k materiálu „{material.title}“."
            )
            practice.topic = material.topic
            practice.status = material.status
            practice.order = material.order
            practice.html_content = ""
            practice.source_tex = ""
            practice.pdf_file = ""

            practice.save()

            practice.grades.set(
                material.grades.all()
            )
            practice.tags.set(
                material.tags.all()
            )

            _replace_sections(
                practice,
                [
                    {
                        "title": PRACTICE_SECTION_TITLE,
                        "slug": PRACTICE_SECTION_SLUG,
                        "html_content": practice_html,
                    }
                ],
            )

        else:
            # Pokud byl \exercisepart ze zdroje odstraněn,
            # odstraníme i dříve vygenerované procvičování.
            Material.objects.filter(
                source_material=material,
                material_type__slug=PRACTICE_TYPE_SLUG,
            ).delete()

    return created_sections
