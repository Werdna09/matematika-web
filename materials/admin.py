from django.contrib import admin

from .models import (
    Grade,
    Material,
    MaterialSection,
    MaterialType,
    Tag,
    Topic,
)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class MaterialSectionInline(admin.StackedInline):
    model = MaterialSection
    extra = 0

    fields = (
        "title",
        "slug",
        "order",
        "html_content",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    ordering = (
        "order",
    )


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "topic",
        "material_type",
        "status",
        "order",
        "updated_at",
    )

    list_filter = (
        "status",
        "material_type",
        "topic",
        "grades",
        "tags",
    )

    search_fields = (
        "title",
        "description",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    filter_horizontal = (
        "grades",
        "tags",
    )

    list_editable = (
        "status",
        "order",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    inlines = (
        MaterialSectionInline,
    )


@admin.register(MaterialSection)
class MaterialSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "material",
        "order",
        "updated_at",
    )

    list_filter = (
        "material",
    )

    search_fields = (
        "title",
        "material__title",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    list_editable = (
        "order",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )