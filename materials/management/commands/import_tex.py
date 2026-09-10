import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from materials.models import Material


class Command(BaseCommand):
    help = "Převede LaTeX soubor na HTML a uloží jej do materiálu."

    def add_arguments(self, parser):
        parser.add_argument(
            "slug",
            type=str,
            help="Slug materiálu v databázi.",
        )

        parser.add_argument(
            "tex_file",
            type=str,
            help="Cesta k hlavnímu .tex souboru.",
        )

    def handle(self, *args, **options):
        slug = options["slug"]

        tex_file = Path(options["tex_file"]).resolve()

        if not tex_file.exists():
            raise CommandError(
                f"Soubor neexistuje: {tex_file}"
            )

        if tex_file.suffix.lower() != ".tex":
            raise CommandError(
                "Zdrojový soubor musí mít příponu .tex."
            )

        try:
            material = Material.objects.get(slug=slug)
        except Material.DoesNotExist:
            raise CommandError(
                f'Materiál se slugem "{slug}" neexistuje.'
            )

        try:
            result = subprocess.run(
                [
                    "pandoc",
                    tex_file.name,
                    "--from=latex",
                    "--to=html5",
                    "--math-method=mathjax",
                ],
                cwd=tex_file.parent,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

        except FileNotFoundError:
            raise CommandError(
                "Pandoc nebyl nalezen. "
                "Zkontroluj, že je nainstalovaný a dostupný v PATH."
            )

        except subprocess.CalledProcessError as error:
            raise CommandError(
                "Pandoc nedokázal soubor převést:\n"
                + error.stderr
            )

        material.html_content = result.stdout

        material.save(
            update_fields=[
                "html_content",
                "updated_at",
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Materiál "{material.title}" byl aktualizován.'
            )
        )