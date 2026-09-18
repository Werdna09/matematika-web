from django.core.validators import FileExtensionValidator
from django.db import models

from materials.models import Tag


class SideQuest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Koncept"
        PUBLISHED = "published", "Publikováno"
        ARCHIVED = "archived", "Archivováno"

    title = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=200,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    tags = models.ManyToManyField(
        Tag,
        related_name="sidequests",
        blank=True,
    )

    pdf_file = models.FileField(
        upload_to="sidequests/pdf/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"])],
        blank=True,
    )

    source_tex = models.FileField(
        upload_to="sidequests/sources/%Y/%m/",
        validators=[FileExtensionValidator(["tex"])],
        blank=True,
        help_text=(
            "Zdrojový LaTeX. Webové kapitoly se vyznačují komentářem "
            "% MATHERA-SECTION: Název kapitoly."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "bokovka"
        verbose_name_plural = "bokovky"

    def __str__(self):
        return self.title


class SideQuestSection(models.Model):
    sidequest = models.ForeignKey(
        SideQuest,
        on_delete=models.CASCADE,
        related_name="sections",
    )

    title = models.CharField(
        max_length=200,
    )

    slug = models.SlugField(
        max_length=200,
    )

    html_content = models.TextField(
        blank=True,
        help_text="HTML obsah kapitoly vygenerovaný z LaTeXu.",
    )

    order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["order", "title"]

        constraints = [
            models.UniqueConstraint(
                fields=["sidequest", "slug"],
                name="unique_sidequest_section_slug",
            ),
        ]

        verbose_name = "kapitola bokovky"
        verbose_name_plural = "kapitoly bokovek"

    def __str__(self):
        return f"{self.sidequest.title} — {self.title}"
