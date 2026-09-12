import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings


class TikzRenderError(Exception):
    """Chyba při převodu TikZ/PGFPlots obrázku do SVG."""


# Prostředí, která Mathera převádí na samostatné SVG obrázky.
# axisgraph je vlastní prostředí definované v ucebnice.sty nad PGFPlots.
FIGURE_ENV_RE = re.compile(
    r"\\begin\{(?P<environment>tikzpicture|axisgraph)\}"
    r"(?P<options>\s*\[[\s\S]*?\])?"
    r"(?P<body>[\s\S]*?)"
    r"\\end\{(?P=environment)\}",
    flags=re.MULTILINE,
)


# Obrázky jednoho materiálu kompilujeme v jednom pdflatex běhu. Balíček preview
# vytvoří z každého tikzpicture samostatnou, těsně oříznutou stránku PDF.
# axisgraph uvnitř expanduje právě na jedno tikzpicture, takže funguje stejně.
#
# Renderovací dokument schválně není závislý na ucebnice.sty. Zdrojové .tex
# soubory jsou uložené v MEDIA_ROOT a nemusí mít .sty vedle sebe; zde proto
# držíme jen malou stabilní vrstvu potřebnou pro obrázky Mathery.
LATEX_PREAMBLE = r"""
\documentclass{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\usepackage{xcolor}
\usepackage{amsmath,amssymb,mathtools}

\usepackage{tikz}
\usepackage{tikz-3dplot}
\usetikzlibrary{
    positioning,
    calc,
    angles,
    quotes,
    fit,
    shapes,
    arrows.meta,
    intersections
}

\usepackage{pgfplots}
\pgfplotsset{compat=1.18}

% Barvy používané v ucebnice.sty.
\definecolor{pastelblue}{RGB}{173,216,230}
\definecolor{pastelgreen}{RGB}{193,225,193}
\definecolor{pastelorange}{RGB}{255,183,120}
\definecolor{pastelviolet}{RGB}{221,160,221}
\colorlet{tableborder}{pastelblue!80!black}

% Vlastní prostředí pro kartézské grafy používané v učebnicích.
\newenvironment{axisgraph}[1][]{
    \begin{tikzpicture}
        \begin{axis}[
            xlabel={$x$}, ylabel={$y$},
            axis lines=center,
            tick align=inside,
            xmin=-5, xmax=5,
            ymin=-5, ymax=5,
            xtick distance=1,
            ytick distance=1,
            axis equal image,
            grid=none,
            major grid style={gray!40},
            minor grid style={gray!20},
            title style={
                font=\bfseries,
                yshift=-2.5ex,
                at={(0.5,0)},
                anchor=north
            },
            #1
        ]
}{
        \end{axis}
    \end{tikzpicture}
}

% Každé tikzpicture bude jedna samostatná, těsně oříznutá stránka.
\usepackage[active,tightpage]{preview}
\PreviewEnvironment{tikzpicture}
\setlength\PreviewBorder{4pt}

\begin{document}
""".strip()

LATEX_POSTAMBLE = r"\end{document}"

# Import běží synchronně z administrace. Timeout chrání server před vadným
# TikZem, který by se při kompilaci zacyklil.
LATEX_TIMEOUT_SECONDS = 90
SVG_TIMEOUT_SECONDS = 30


def _mask_latex_comments(source):
    """
    Zamaskuje LaTeXové komentáře mezerami, ale zachová délku textu.

    Díky tomu ignorujeme například zakomentované \begin{tikzpicture}, zatímco
    indexy nalezených prostředí pořád odpovídají původnímu source.
    """

    chars = list(source)
    index = 0

    while index < len(chars):
        if chars[index] != "%":
            index += 1
            continue

        # Escapované procento \% komentář nezačíná.
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


def _figure_hash(snippet):
    """Stabilní hash obrázku včetně celé renderovací definice."""

    payload = (
        LATEX_PREAMBLE
        + "\n"
        + LATEX_POSTAMBLE
        + "\n"
        + snippet
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()[:20]


def _command_error_output(result, max_lines=60):
    """Vrátí čitelný konec výstupu externího programu."""

    output = "\n".join(
        part
        for part in (result.stdout, result.stderr)
        if part
    ).strip()

    if not output:
        return "Externí program skončil s chybou bez dalšího výstupu."

    lines = output.splitlines()
    return "\n".join(lines[-max_lines:])


def _build_batch_document(items):
    body = []

    for item in items:
        # Marker se objeví v pdflatex stdout. Když kompilace spadne, podle
        # posledního markeru umíme určit konkrétní problematický obrázek.
        body.append(
            f"\\typeout{{MATHERA-FIGURE-{item['figure_number']}}}"
        )
        body.append(item["snippet"].strip())

    return (
        LATEX_PREAMBLE
        + "\n"
        + "\n\n".join(body)
        + "\n"
        + LATEX_POSTAMBLE
        + "\n"
    )


def _compile_batch_pdf(items, source_dir, work_dir):
    pdflatex = shutil.which("pdflatex")

    if not pdflatex:
        raise TikzRenderError(
            "pdflatex nebyl nalezen. "
            "Pro renderování TikZ je potřeba nainstalovat LaTeX."
        )

    tex_path = work_dir / "figures.tex"
    pdf_path = work_dir / "figures.pdf"

    tex_path.write_text(
        _build_batch_document(items),
        encoding="utf-8",
    )

    command = [
        pdflatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-no-shell-escape",
        f"-output-directory={work_dir}",
        str(tex_path),
    ]

    try:
        result = subprocess.run(
            command,
            cwd=source_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=LATEX_TIMEOUT_SECONDS,
            check=False,
        )

    except subprocess.TimeoutExpired as error:
        raise TikzRenderError(
            "Kompilace TikZ překročila časový limit "
            f"{LATEX_TIMEOUT_SECONDS} s."
        ) from error

    if result.returncode != 0 or not pdf_path.exists():
        combined_output = "\n".join(
            part
            for part in (result.stdout, result.stderr)
            if part
        )

        markers = re.findall(
            r"MATHERA-FIGURE-(\d+)",
            combined_output,
        )

        prefix = ""

        if markers:
            failing_number = int(markers[-1])
            failing_item = next(
                (
                    item
                    for item in items
                    if item["figure_number"] == failing_number
                ),
                None,
            )

            if failing_item:
                prefix = (
                    f"Obrázek {failing_number} "
                    f"({failing_item['environment']}) se nepodařilo zkompilovat.\n"
                )

        raise TikzRenderError(
            prefix
            + "pdflatex nedokázal TikZ/PGFPlots zkompilovat:\n"
            + _command_error_output(result)
        )

    return pdf_path


def _convert_pdf_page_to_svg(pdf_path, page_number, svg_path, work_dir):
    """
    Převede jednu stránku PDF na SVG.

    Primárně používáme pdftocairo. Na Windows/MiKTeXu se ukázalo, že
    dvisvgm při převodu PDF s průhledností z TikZu může vytvořit SVG,
    ve kterém mají všechny cesty nulovou opacity, přestože proces skončí
    úspěšně. dvisvgm proto necháváme pouze jako fallback.
    """

    conversion_errors = []

    # Primární převodník. Poppler korektně zachovává průhlednost TikZu
    # a funguje stejně na Windows i Ubuntu.
    pdftocairo = shutil.which("pdftocairo")

    if pdftocairo:
        command = [
            pdftocairo,
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-svg",
            str(pdf_path),
            str(svg_path),
        ]

        try:
            result = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SVG_TIMEOUT_SECONDS,
                check=False,
            )

        except subprocess.TimeoutExpired:
            conversion_errors.append(
                f"pdftocairo pro stránku {page_number} překročil časový limit."
            )

        else:
            if result.returncode == 0 and svg_path.exists():
                return

            conversion_errors.append(
                "pdftocairo: " + _command_error_output(result)
            )

    # Fallback pro systémy, kde pdftocairo není dostupné.
    dvisvgm = shutil.which("dvisvgm")

    if dvisvgm:
        command = [
            dvisvgm,
            "--pdf",
            f"--page={page_number}",
            "--bbox=min",
            f"--output={svg_path}",
            str(pdf_path),
        ]

        try:
            result = subprocess.run(
                command,
                cwd=work_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=SVG_TIMEOUT_SECONDS,
                check=False,
            )

        except subprocess.TimeoutExpired:
            conversion_errors.append(
                f"dvisvgm pro stránku {page_number} překročil časový limit."
            )

        else:
            if result.returncode == 0 and svg_path.exists():
                return

            conversion_errors.append(
                "dvisvgm: " + _command_error_output(result)
            )

    if not pdftocairo and not dvisvgm:
        raise TikzRenderError(
            "Nebyl nalezen převodník PDF → SVG. "
            "Nainstaluj pdftocairo (poppler-utils) nebo dvisvgm."
        )

    raise TikzRenderError(
        f"Stránku {page_number} PDF se nepodařilo převést na SVG:\n"
        + "\n\n".join(conversion_errors)
    )


def _render_missing_figures(items, source_dir):
    """V jednom LaTeX běhu vyrenderuje všechny dosud necachované obrázky."""

    if not items:
        return

    for item in items:
        item["destination"].parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    with tempfile.TemporaryDirectory(
        prefix=".mathera_tikz_",
        dir=source_dir,
    ) as temporary_directory:
        work_dir = Path(temporary_directory)

        pdf_path = _compile_batch_pdf(
            items,
            source_dir=source_dir,
            work_dir=work_dir,
        )

        # Preview vytvoří stránky ve stejném pořadí jako vstupní tikzpicture.
        for page_number, item in enumerate(items, start=1):
            temporary_svg = work_dir / f"figure-{page_number}.svg"

            _convert_pdf_page_to_svg(
                pdf_path,
                page_number=page_number,
                svg_path=temporary_svg,
                work_dir=work_dir,
            )

            destination = item["destination"]
            temporary_destination = destination.with_suffix(".svg.tmp")

            shutil.copyfile(
                temporary_svg,
                temporary_destination,
            )

            # Atomická výměna: čtenář nikdy neuvidí napůl zapsané SVG.
            os.replace(
                temporary_destination,
                destination,
            )


def render_tikz_figures(source, material_slug, source_dir):
    """
    Najde TikZ/PGFPlots obrázky, vyrenderuje je do SVG a v LaTeXu je nahradí
    za ``\\includegraphics`` s URL do MEDIA_URL.

    Podporovaná prostředí:
    - tikzpicture
    - axisgraph
    """

    source_dir = Path(source_dir).resolve()

    media_root_setting = getattr(
        settings,
        "MEDIA_ROOT",
        None,
    )
    media_url_setting = getattr(
        settings,
        "MEDIA_URL",
        "/media/",
    )

    if not media_root_setting:
        raise TikzRenderError(
            "Django MEDIA_ROOT není nastavený."
        )

    media_root = Path(media_root_setting).resolve()

    output_directory = (
        media_root
        / "generated"
        / "tikz"
        / material_slug
    )

    media_url = str(media_url_setting or "/media/")

    if not media_url.endswith("/"):
        media_url += "/"

    masked_source = _mask_latex_comments(source)
    matches = list(FIGURE_ENV_RE.finditer(masked_source))

    if not matches:
        return source

    items = []
    missing_by_hash = {}

    for figure_number, match in enumerate(matches, start=1):
        snippet = source[
            match.start():match.end()
        ]

        digest = _figure_hash(snippet)
        filename = f"figure-{digest}.svg"
        destination = output_directory / filename

        item = {
            "figure_number": figure_number,
            "environment": match.group("environment"),
            "start": match.start(),
            "end": match.end(),
            "snippet": snippet,
            "filename": filename,
            "destination": destination,
        }

        items.append(item)

        # Stejný obrázek stačí vyrenderovat jednou, i kdyby se ve zdroji
        # opakoval vícekrát.
        if not destination.exists():
            missing_by_hash.setdefault(
                digest,
                item,
            )

    _render_missing_figures(
        list(missing_by_hash.values()),
        source_dir=source_dir,
    )

    transformed = source

    # Nahrazujeme odzadu, aby se neposouvaly indexy dalších bloků.
    for item in reversed(items):
        image_url = (
            media_url
            + "generated/tikz/"
            + material_slug
            + "/"
            + item["filename"]
        )

        # Pandoc umí \includegraphics převést přímo na HTML <img>.
        # Případný okolní center/minipage zůstává v původním zdroji.
        replacement = (
            "\n"
            f"\\includegraphics{{{image_url}}}\n"
        )

        transformed = (
            transformed[:item["start"]]
            + replacement
            + transformed[item["end"]:]
        )

    return transformed
