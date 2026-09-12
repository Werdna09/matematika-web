import re
import subprocess
import tempfile

from html import unescape
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify

from materials.models import MaterialSection
from materials.services.tex_preprocessor import preprocess_tex
from materials.services.tikz_renderer import TikzRenderError, render_tikz_figures


class TexImportError(Exception):
    pass


LUA_FILTER = (
    Path(__file__).resolve().parent
    / "pandoc"
    / "mathera.lua"
)


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


def import_material_tex(material, tex_file=None):
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


    # =====================================================
    # PREPROCESSING LATEXU
    # =====================================================

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
    # TIKZ / PGFPLOTS → SVG
    # =====================================================
    #
    # TikZ a vlastní axisgraph nevkládáme do Pandocu přímo.
    # Nejprve je vyrenderujeme jako SVG do MEDIA_ROOT a v LaTeXu
    # je nahradíme za \includegraphics s veřejnou MEDIA_URL.

    try:
        source = render_tikz_figures(
            source,
            material_slug=material.slug,
            source_dir=tex_file.parent,
        )

    except TikzRenderError as error:
        raise TexImportError(
            "TikZ/PGFPlots obrázky se nepodařilo zpracovat:\n"
            + str(error)
        ) from error


    source = preprocess_tex(
        source
    )


    processed_tex = None

    try:
        # Dočasný soubor vytváříme ve stejné složce jako
        # původní .tex, aby relativní cesty a \input nadále
        # fungovaly.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tex",
            prefix=".mathera_",
            encoding="utf-8",
            dir=tex_file.parent,
            delete=False,
        ) as temp_file:

            temp_file.write(source)

            processed_tex = Path(
                temp_file.name
            )


        # =================================================
        # PANDOC
        # =================================================

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
                cwd=tex_file.parent,
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
            )


        # =================================================
        # ROZDĚLENÍ HTML NA KAPITOLY
        # =================================================

        sections = _split_html_into_sections(
            result.stdout
        )


        # =================================================
        # AKTUALIZACE DATABÁZE
        # =================================================
        #
        # Do databáze saháme až ve chvíli, kdy:
        #
        # - preprocessing proběhl,
        # - Pandoc proběhl,
        # - kapitoly byly úspěšně nalezeny.
        #
        # Pokud vytvoření nových sekcí selže,
        # transaction.atomic() vrátí databázi zpět.

        with transaction.atomic():
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


    finally:
        # Dočasný předzpracovaný LaTeX po sobě vždy uklidíme,
        # ať Pandoc uspěje nebo selže.
        if processed_tex is not None:
            processed_tex.unlink(
                missing_ok=True
            )