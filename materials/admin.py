from urllib import request

from django.contrib import admin, messages

from .models import (
    Grade,
    Material,
    MaterialSection,
    MaterialType,
    Tag,
    Topic,
)
from .services.tex_importer import TexImportError, import_material_tex


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

    def save_model(self, request, obj, form, change):
        source_tex_changed = "source_tex" in form.changed_data

        super().save_model(request, obj, form, change)

        if not source_tex_changed or not obj.source_tex:
            return

        try:
            import_material_tex(obj)

        except TexImportError as exc:
            self.message_user(
                request,
                (
                    "Materiál byl uložen, ale import LaTeXu se nezdařil. "
                    f"Původní online verze zůstala zachována. Chyba: {exc}"
                ),
                level=messages.ERROR,
            )

        except Exception as exc:
            self.message_user(
                request,
                (
                    "Materiál byl uložen, ale při importu LaTeXu nastala "
                    f"neočekávaná chyba: {type(exc).__name__}: {exc}"
                ),
                level=messages.ERROR,
            )

        else:
            section_count = obj.sections.count()

            self.message_user(
                request,
                (
                    f"LaTeX byl úspěšně importován. "
                    f"Vytvořeno kapitol: {section_count}."
                ),
                level=messages.SUCCESS,
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