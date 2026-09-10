from django.core.validators import FileExtensionValidator
from django.db import models


class Grade(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "ročník"
        verbose_name_plural = "ročníky"

    def __str__(self):
        return self.name


class Topic(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "téma"
        verbose_name_plural = "témata"

    def __str__(self):
        return self.name


class MaterialType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "typ materiálu"
        verbose_name_plural = "typy materiálů"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "štítek"
        verbose_name_plural = "štítky"

    def __str__(self):
        return self.name


class Material(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Koncept"
        PUBLISHED = "published", "Publikováno"
        ARCHIVED = "archived", "Archivováno"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)

    description = models.TextField(blank=True)

    material_type = models.ForeignKey(
        MaterialType,
        on_delete=models.PROTECT,
        related_name="materials",
    )

    topic = models.ForeignKey(
        Topic,
        on_delete=models.PROTECT,
        related_name="materials",
    )

    grades = models.ManyToManyField(
        Grade,
        related_name="materials",
    )

    tags = models.ManyToManyField(
        Tag,
        related_name="materials",
        blank=True,
    )

    pdf_file = models.FileField(
        upload_to="materials/%Y/%m/",
        validators=[FileExtensionValidator(["pdf"])],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["topic__order", "order", "title"]
        verbose_name = "materiál"
        verbose_name_plural = "materiály"

    def __str__(self):
        return self.title