from django.contrib import admin, messages

from .models import SideQuest, SideQuestSection
from .services.tex_importer import (
    SideQuestImportError,
    import_sidequest_tex,
)


class SideQuestSectionInline(admin.TabularInline):
    model = SideQuestSection
    extra = 0

    fields = (
        "order",
        "title",
        "slug",
    )

    readonly_fields = (
        "order",
        "title",
        "slug",
    )

    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SideQuest)
class SideQuestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "order",
        "updated_at",
    )

    list_filter = (
        "status",
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
        "tags",
    )

    inlines = [
        SideQuestSectionInline,
    ]

    actions = [
        "reimport_selected",
    ]

    @admin.action(
        description="Znovu importovat vybrané bokovky z LaTeXu"
    )
    def reimport_selected(self, request, queryset):
        imported = 0

        for sidequest in queryset:
            try:
                import_sidequest_tex(
                    sidequest
                )

            except SideQuestImportError as error:
                self.message_user(
                    request,
                    f"{sidequest.title}: {error}",
                    level=messages.ERROR,
                )
                continue

            imported += 1

        if imported:
            self.message_user(
                request,
                f"Úspěšně importováno: {imported}.",
                level=messages.SUCCESS,
            )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        source_changed = (
            not change
            or "source_tex" in form.changed_data
        )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        if (
            source_changed
            and obj.source_tex
        ):
            try:
                sections = import_sidequest_tex(
                    obj
                )

            except SideQuestImportError as error:
                self.message_user(
                    request,
                    str(error),
                    level=messages.ERROR,
                )
                return

            self.message_user(
                request,
                (
                    "Bokovka byla úspěšně importována. "
                    f"Kapitol: {len(sections)}."
                ),
                level=messages.SUCCESS,
            )


@admin.register(SideQuestSection)
class SideQuestSectionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "sidequest",
        "order",
    )

    list_filter = (
        "sidequest",
    )

    search_fields = (
        "title",
        "sidequest__title",
    )

    readonly_fields = (
        "sidequest",
        "title",
        "slug",
        "html_content",
        "order",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
