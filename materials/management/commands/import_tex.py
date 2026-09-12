from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from materials.models import Material
from materials.services.tex_importer import (
    TexImportError,
    import_material_tex,
)


class Command(BaseCommand):
    help = (
        "Převede zdrojový LaTeX materiálu na "
        "jednotlivé online kapitoly."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "slug",
            type=str,
            help="Slug materiálu v databázi.",
        )

        parser.add_argument(
            "tex_file",
            nargs="?",
            type=str,
            help=(
                "Volitelná cesta k .tex souboru. "
                "Pokud není uvedena, použije se "
                "source_tex uložený u materiálu."
            ),
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        tex_file = options["tex_file"]

        try:
            material = Material.objects.get(
                slug=slug
            )
        except Material.DoesNotExist:
            raise CommandError(
                f'Materiál se slugem "{slug}" neexistuje.'
            )

        source_path = (
            Path(tex_file).resolve()
            if tex_file
            else None
        )

        try:
            sections = import_material_tex(
                material,
                source_path,
            )

        except TexImportError as error:
            raise CommandError(
                str(error)
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Materiál "{material.title}" byl aktualizován. '
                f"Vytvořeno kapitol: {len(sections)}."
            )
        )

        for section in sections:
            self.stdout.write(
                f"  {section.order:02d}  "
                f"{section.title} "
                f"({section.slug})"
            )