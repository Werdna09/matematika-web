from django.core.validators import FileExtensionValidator
from django.db import models


class Exam(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Koncept"
        PUBLISHED = "published", "Publikováno"
        ARCHIVED = "archived", "Archivováno"

    class Term(models.TextChoices):
        SPRING = "spring", "Jaro"
        AUTUMN = "autumn", "Podzim"
        OTHER = "other", "Jiný termín"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)

    year = models.PositiveSmallIntegerField()
    term = models.CharField(
        max_length=20,
        choices=Term.choices,
        default=Term.SPRING,
    )

    description = models.TextField(blank=True)

    source_pdf = models.FileField(
        upload_to="exams/source-pdf/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
        help_text="Originální PDF testu, ze kterého se automaticky vytvářejí výřezy zadání.",
    )

    source_tex = models.FileField(
        upload_to="exams/source-tex/%Y/%m/",
        validators=[FileExtensionValidator(["tex"])],
        blank=True,
        help_text=r"LaTeX se značkami \uloha{...}{\zadani{...}} a řešeními.",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "term", "title"]
        verbose_name = "maturita"
        verbose_name_plural = "maturity"

    def __str__(self):
        return self.title


class ExamTask(models.Model):
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="tasks",
    )

    number = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField(default=0)

    page_number = models.PositiveSmallIntegerField()

    trim_left_mm = models.DecimalField(max_digits=8, decimal_places=3)
    trim_bottom_mm = models.DecimalField(max_digits=8, decimal_places=3)
    trim_right_mm = models.DecimalField(max_digits=8, decimal_places=3)
    trim_top_mm = models.DecimalField(max_digits=8, decimal_places=3)

    statement_image = models.FileField(
        blank=True,
        help_text="Automaticky vygenerovaný výřez zadání z originálního PDF.",
    )

    solution_tex = models.TextField(
        blank=True,
        help_text="Zdroj řešení vytažený z hlavního LaTeXového souboru.",
    )

    solution_html = models.TextField(
        blank=True,
        help_text="HTML řešení vygenerované z LaTeXu.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "number"],
                name="unique_exam_task_number",
            ),
        ]
        verbose_name = "maturitní úloha"
        verbose_name_plural = "maturitní úlohy"

    def __str__(self):
        return f"{self.exam.title} — úloha {self.number}"
