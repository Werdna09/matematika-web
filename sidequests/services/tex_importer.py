\
import re
import subprocess
import tempfile

from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from materials.services.tex_preprocessor import preprocess_tex
from materials.services.tikz_renderer import (
    TikzRenderError,
    render_tikz_figures,
)

from sidequests.models import SideQuestSection


class SideQuestImportError(Exception):
    pass


LUA_FILTER = (
    Path(settings.BASE_DIR)
    / "materials"
    / "services"
    / "pandoc"
    / "mathera.lua"
)


DOCUMENT_BEGIN_RE = re.compile(
    r"\\begin\{document\}"
)

DOCUMENT_END_RE = re.compile(
    r"\\end\{document\}"
)

SECTION_MARKER_RE = re.compile(
    r"^[ \t]*%[ \t]*MATHERA-SECTION[ \t]*:[ \t]*(.+?)[ \t]*$",
    flags=re.IGNORECASE | re.MULTILINE,
)

LEADING_LATEX_HEADING_RE = re.compile(
    r"^\s*\\(?:section|subsection|subsubsection)\*?\s*\{",
    flags=re.DOTALL,
)

LEADING_HTML_HEADING_RE = re.compile(
    r"^\s*<h[1-6]\b[^>]*>.*?</h[1-6]>\s*",
    flags=re.IGNORECASE | re.DOTALL,
)


def _unique_slug(base_slug, used_slugs):
    slug = base_slug or "kapitola"

    candidate = slug
    counter = 2

    while candidate in used_slugs:
        candidate = f"{slug}-{counter}"
        counter += 1

    used_slugs.add(candidate)
    return candidate


def _document_parts(source):
    begin_match = DOCUMENT_BEGIN_RE.search(source)
    end_matches = list(DOCUMENT_END_RE.finditer(source))

    if begin_match is None or not end_matches:
        raise SideQuestImportError(
            "Zdroj musí obsahovat \\\\begin{document} a \\\\end{document}."
        )

    end_match = end_matches[-1]

    if end_match.start() <= begin_match.end():
        raise SideQuestImportError(
            "LaTeX dokument má neplatnou strukturu."
        )

    prefix = source[:begin_match.end()]
    body = source[
        begin_match.end():end_match.start()
    ]
    suffix = source[end_match.start():]

    return prefix, body, suffix


def _split_marked_sections(body):
    markers = list(
        SECTION_MARKER_RE.finditer(body)
    )

    if not markers:
        raise SideQuestImportError(
            "Ve zdrojovém LaTeXu nebyly nalezeny webové kapitoly. "
            "Přidej komentáře ve tvaru "
            "'% MATHERA-SECTION: Název kapitoly'."
        )

    sections = []
    used_slugs = set()

    for index, marker in enumerate(markers):
        title = marker.group(1).strip()

        if not title:
            raise SideQuestImportError(
                "Nalezen prázdný marker MATHERA-SECTION."
            )

        content_start = marker.end()

        if index + 1 < len(markers):
            content_end = markers[
                index + 1
            ].start()
        else:
            content_end = len(body)

        content = body[
            content_start:content_end
        ].strip()

        if not content:
            raise SideQuestImportError(
                f'Kapitola "{title}" neobsahuje žádný text.'
            )

        section_slug = _unique_slug(
            slugify(title),
            used_slugs,
        )

        sections.append(
            {
                "title": title,
                "slug": section_slug,
                "source": content,
                "starts_with_heading": bool(
                    LEADING_LATEX_HEADING_RE.match(
                        content
                    )
                ),
            }
        )

    return sections


def _run_pandoc(source, source_dir):
    processed_tex = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tex",
            prefix=".mathera_sidequest_",
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
            raise SideQuestImportError(
                "Pandoc nebyl nalezen. "
                "Zkontroluj, že je dostupný v PATH."
            )

        except subprocess.CalledProcessError as error:
            raise SideQuestImportError(
                "Pandoc nedokázal LaTeX převést:\n"
                + error.stderr
            ) from error

        return result.stdout

    finally:
        if processed_tex is not None:
            processed_tex.unlink(
                missing_ok=True
            )


def _convert_section_to_html(
    source,
    *,
    cache_slug,
    source_dir,
    title,
    strip_leading_heading,
):
    try:
        source = render_tikz_figures(
            source,
            material_slug=cache_slug,
            source_dir=source_dir,
        )

    except TikzRenderError as error:
        raise SideQuestImportError(
            f'Kapitola "{title}": '
            "TikZ/PGFPlots obrázky se nepodařilo zpracovat:\n"
            + str(error)
        ) from error

    source = preprocess_tex(
        source
    )

    try:
        html = _run_pandoc(
            source,
            source_dir,
        ).strip()

    except SideQuestImportError as error:
        raise SideQuestImportError(
            f'Kapitola "{title}": {error}'
        ) from error

    if strip_leading_heading:
        html = LEADING_HTML_HEADING_RE.sub(
            "",
            html,
            count=1,
        ).strip()

    if not html:
        raise SideQuestImportError(
            f'Kapitola "{title}" vytvořila prázdný HTML obsah.'
        )

    return html


def _replace_sections(sidequest, sections):
    sidequest.sections.all().delete()

    created_sections = []

    for order, section_data in enumerate(
        sections,
        start=1,
    ):
        section = SideQuestSection.objects.create(
            sidequest=sidequest,
            title=section_data["title"],
            slug=section_data["slug"],
            html_content=section_data["html_content"],
            order=order,
        )

        created_sections.append(
            section
        )

    return created_sections


def import_sidequest_tex(sidequest, tex_file=None):
    if tex_file is None:
        if not sidequest.source_tex:
            raise SideQuestImportError(
                f'Bokovka "{sidequest.title}" '
                "nemá nahraný zdrojový LaTeX."
            )

        try:
            tex_file = Path(
                sidequest.source_tex.path
            ).resolve()

        except (NotImplementedError, ValueError):
            raise SideQuestImportError(
                "Zdrojový LaTeX není dostupný jako lokální soubor."
            )

    else:
        tex_file = Path(
            tex_file
        ).resolve()

    if not tex_file.exists():
        raise SideQuestImportError(
            f"Soubor neexistuje: {tex_file}"
        )

    if tex_file.suffix.lower() != ".tex":
        raise SideQuestImportError(
            "Zdrojový soubor musí mít příponu .tex."
        )

    if not LUA_FILTER.exists():
        raise SideQuestImportError(
            f"Pandoc filtr nebyl nalezen: {LUA_FILTER}"
        )

    try:
        source = tex_file.read_text(
            encoding="utf-8",
        )

    except UnicodeDecodeError as error:
        raise SideQuestImportError(
            "Zdrojový LaTeX není uložen v UTF-8."
        ) from error

    except OSError as error:
        raise SideQuestImportError(
            f"Zdrojový LaTeX se nepodařilo načíst: {error}"
        ) from error

    prefix, body, suffix = _document_parts(
        source
    )

    marked_sections = _split_marked_sections(
        body
    )

    converted_sections = []

    for section_data in marked_sections:
        standalone_source = (
            prefix
            + "\n\n"
            + section_data["source"]
            + "\n\n"
            + suffix
        )

        html = _convert_section_to_html(
            standalone_source,
            cache_slug=(
                f"sidequest-{sidequest.slug}-"
                f"{section_data['slug']}"
            ),
            source_dir=tex_file.parent,
            title=section_data["title"],
            strip_leading_heading=(
                section_data[
                    "starts_with_heading"
                ]
            ),
        )

        converted_sections.append(
            {
                "title": section_data["title"],
                "slug": section_data["slug"],
                "html_content": html,
            }
        )

    # Do databáze saháme až po úspěšném převodu všech kapitol.
    # Při chybě tak zůstane předchozí webová verze zachována.
    with transaction.atomic():
        created_sections = _replace_sections(
            sidequest,
            converted_sections,
        )

    return created_sections
