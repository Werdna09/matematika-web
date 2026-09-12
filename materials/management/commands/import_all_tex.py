from django.core.management.base import BaseCommand

from materials.models import Material
from materials.services.tex_importer import TexImportError, import_material_tex


class Command(BaseCommand):
    help = "Importuje LaTeX zdroje všech materiálů, které mají vyplněný source_tex."

    def handle(self, *args, **options):
        materials = (
            Material.objects
            .exclude(source_tex="")
            .order_by("title")
        )

        if not materials.exists():
            self.stdout.write(
                self.style.WARNING("Žádné materiály se zdrojovým .tex nebyly nalezeny.")
            )
            return

        success = 0
        failed = 0

        self.stdout.write(
            f"Nalezeno materiálů se zdrojovým LaTeXem: {materials.count()}\n"
        )

        for material in materials:
            self.stdout.write(f"{material.title} ... ", ending="")

            try:
                import_material_tex(material)

                section_count = material.sections.count()
                success += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK ({section_count} kapitol)"
                    )
                )

            except TexImportError as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(f"CHYBA: {exc}")
                )

            except Exception as exc:
                failed += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"NEOČEKÁVANÁ CHYBA: {type(exc).__name__}: {exc}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Úspěšně: {success}")
        )

        if failed:
            self.stdout.write(
                self.style.ERROR(f"Chyba: {failed}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("Všechny materiály byly naimportovány.")
            )