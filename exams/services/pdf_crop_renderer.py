\
import re
import subprocess
import tempfile

from decimal import Decimal
from pathlib import Path


class PdfCropRenderError(Exception):
    pass


PAGE_SIZE_RE = re.compile(
    r"Page\s+\d+\s+size:\s+([0-9.]+)\s+x\s+([0-9.]+)\s+pts",
    flags=re.IGNORECASE,
)


class PdfCropRenderer:
    """
    Převádí LaTeXový trim (left bottom right top) na automatický PNG výřez.

    Používá jen nástroje Poppleru: pdfinfo + pdftocairo. Mathera už
    pdftocairo používá i v TikZ pipeline, takže nepřidáváme Python image dependency.
    """

    def __init__(self, pdf_path, *, dpi=180):
        self.pdf_path = Path(pdf_path)
        self.dpi = int(dpi)
        self._page_sizes = {}

    def _page_size_points(self, page_number):
        if page_number in self._page_sizes:
            return self._page_sizes[page_number]

        try:
            result = subprocess.run(
                [
                    "pdfinfo",
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    str(self.pdf_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except FileNotFoundError as error:
            raise PdfCropRenderError(
                "Nástroj pdfinfo nebyl nalezen. Nainstaluj Poppler a ověř PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise PdfCropRenderError(
                "pdfinfo nedokázal načíst originální PDF:\n" + error.stderr
            ) from error

        match = PAGE_SIZE_RE.search(result.stdout)
        if match is None:
            raise PdfCropRenderError(
                f"Nepodařilo se zjistit rozměr strany {page_number} v PDF."
            )

        size = (
            Decimal(match.group(1)),
            Decimal(match.group(2)),
        )
        self._page_sizes[page_number] = size
        return size

    def render(
        self,
        *,
        page_number,
        trim_left_mm,
        trim_bottom_mm,
        trim_right_mm,
        trim_top_mm,
    ):
        page_width_pt, page_height_pt = self._page_size_points(page_number)

        dpi = Decimal(self.dpi)
        px_per_mm = dpi / Decimal("25.4")
        px_per_pt = dpi / Decimal(72)

        page_width_px = int(round(page_width_pt * px_per_pt))
        page_height_px = int(round(page_height_pt * px_per_pt))

        left_px = int(round(Decimal(trim_left_mm) * px_per_mm))
        bottom_px = int(round(Decimal(trim_bottom_mm) * px_per_mm))
        right_px = int(round(Decimal(trim_right_mm) * px_per_mm))
        top_px = int(round(Decimal(trim_top_mm) * px_per_mm))

        crop_width = page_width_px - left_px - right_px
        crop_height = page_height_px - top_px - bottom_px

        if crop_width <= 0 or crop_height <= 0:
            raise PdfCropRenderError(
                f"Neplatný ořez strany {page_number}: výsledný výřez má "
                f"{crop_width} × {crop_height} px."
            )

        with tempfile.TemporaryDirectory(prefix="mathera_exam_crop_") as temp_dir:
            output_base = Path(temp_dir) / "crop"
            output_png = output_base.with_suffix(".png")

            try:
                subprocess.run(
                    [
                        "pdftocairo",
                        "-png",
                        "-singlefile",
                        "-f",
                        str(page_number),
                        "-l",
                        str(page_number),
                        "-r",
                        str(self.dpi),
                        "-x",
                        str(left_px),
                        "-y",
                        str(top_px),
                        "-W",
                        str(crop_width),
                        "-H",
                        str(crop_height),
                        str(self.pdf_path),
                        str(output_base),
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=True,
                )
            except FileNotFoundError as error:
                raise PdfCropRenderError(
                    "Nástroj pdftocairo nebyl nalezen. Nainstaluj Poppler a ověř PATH."
                ) from error
            except subprocess.CalledProcessError as error:
                raise PdfCropRenderError(
                    f"Nepodařilo se vyrenderovat výřez ze strany {page_number}:\n"
                    + error.stderr
                ) from error

            if not output_png.exists():
                raise PdfCropRenderError(
                    f"pdftocairo nevytvořil PNG pro úlohu na straně {page_number}."
                )

            return output_png.read_bytes()
