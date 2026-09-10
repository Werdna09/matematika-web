from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Grade, Material, MaterialType, Tag, Topic

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