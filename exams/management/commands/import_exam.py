from django.core.management.base import BaseCommand, CommandError

from exams.models import Exam
from exams.services.tex_importer import ExamImportError, import_exam_tex


class Command(BaseCommand):
    help = "Reimportuje jednu maturitu z nahraného LaTeXu a originálního PDF."

    def add_arguments(self, parser):
        parser.add_argument("slug")

    def handle(self, *args, **options):
        slug = options["slug"]

        try:
            exam = Exam.objects.get(slug=slug)
        except Exam.DoesNotExist as error:
            raise CommandError(f'Maturita se slugem "{slug}" neexistuje.') from error

        try:
            count = import_exam_tex(exam)
        except ExamImportError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Import dokončen: {exam.title} — {count} úloh."
            )
        )
