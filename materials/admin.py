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


# =============================================================================
# Ročníky
# =============================================================================

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    """Správa školních ročníků."""

    list_display = (
        "name",
        "order",
    )

    list_editable = (
        "order",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    search_fields = (
        "name",
    )


# =============================================================================
# Tematické okruhy
# =============================================================================

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    """Správa tematických okruhů materiálů."""

    list_display = (
        "name",
        "order",
    )

    list_editable = (
        "order",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    search_fields = (
        "name",
    )


# =============================================================================
# Typy materiálů
# =============================================================================

@admin.register(MaterialType)
class MaterialTypeAdmin(admin.ModelAdmin):
    """Správa typů materiálů, například učebnice nebo pracovní list."""

    list_display = (
        "name",
        "order",
    )

    list_editable = (
        "order",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    search_fields = (
        "name",
    )


# =============================================================================
# Tagy
# =============================================================================

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Správa tagů používaných pro filtrování materiálů."""

    list_display = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    search_fields = (
        "name",
    )


# =============================================================================
# Kapitoly materiálu – inline zobrazení uvnitř materiálu
# =============================================================================

class MaterialSectionInline(admin.StackedInline):
    """
    Zobrazuje jednotlivé kapitoly přímo v administraci materiálu.

    Kapitoly jsou standardně generovány automaticky z LaTeXového zdroje.
    Inline ponecháváme přístupný hlavně pro kontrolu výsledku importu.
    """

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


# =============================================================================
# Materiály
# =============================================================================

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    """Hlavní administrace výukových materiálů."""

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
        "source_material",
        "created_at",
        "updated_at",
    )

    inlines = (
        MaterialSectionInline,
    )

    actions = (
        "reimport_latex",
    )

    # -------------------------------------------------------------------------
    # Automatický import při nahrání nového LaTeXového zdroje
    # -------------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        """
        Samotný Material uložíme běžně.

        Informaci o změně source_tex si pouze zapamatujeme. Import spustíme
        až v save_related(), tedy po uložení M2M polí a inline kapitol.
        Tím se vyhneme kolizím UNIQUE constraint na MaterialSection.
        """

        request._mathera_source_tex_changed = (
            "source_tex" in form.changed_data
        )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def _sync_derived_materials(self, material):
        """
        Udržuje metadata automaticky odvozených materiálů synchronní
        se zdrojovým učebním materiálem i při změně názvu/stavu bez reimportu.
        """

        if material.source_material_id:
            return

        for derived in material.derived_materials.select_related(
            "material_type"
        ):
            derived.topic = material.topic
            derived.status = material.status
            derived.order = material.order

            if derived.material_type.slug == "procvicovani":
                derived.title = (
                    f"{material.title} – procvičování"
                )
                derived.description = (
                    f"Procvičování k materiálu „{material.title}“."
                )

            derived.save()

            derived.grades.set(
                material.grades.all()
            )
            derived.tags.set(
                material.tags.all()
            )

    def save_related(self, request, form, formsets, change):
        """
        Nejdřív necháme Django uložit M2M vztahy a inline formuláře.
        Teprve poté případně přegenerujeme sekce z LaTeXu.
        """

        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        obj = form.instance

        self._sync_derived_materials(
            obj
        )

        source_tex_changed = getattr(
            request,
            "_mathera_source_tex_changed",
            False,
        )

        if (
            not source_tex_changed
            or not obj.source_tex
            or obj.source_material_id
        ):
            return

        try:
            import_material_tex(
                obj
            )

        except TexImportError as exc:
            self.message_user(
                request,
                (
                    "Materiál byl uložen, ale import LaTeXu se nezdařil. "
                    "Původní online verze zůstala zachována. "
                    f"Chyba: {exc}"
                ),
                level=messages.ERROR,
            )

        except Exception as exc:
            self.message_user(
                request,
                (
                    "Materiál byl uložen, ale při importu LaTeXu nastala "
                    "neočekávaná chyba. "
                    f"{type(exc).__name__}: {exc}"
                ),
                level=messages.ERROR,
            )

        else:
            section_count = obj.sections.count()

            has_practice = obj.derived_materials.filter(
                material_type__slug="procvicovani",
            ).exists()

            message = (
                "LaTeX byl úspěšně importován. "
                f"Vytvořeno kapitol učebního textu: {section_count}."
            )

            if has_practice:
                message += " Procvičování bylo vytvořeno nebo aktualizováno."

            self.message_user(
                request,
                message,
                level=messages.SUCCESS,
            )

    # -------------------------------------------------------------------------
    # Ruční / hromadný reimport existujících materiálů
    # -------------------------------------------------------------------------

    @admin.action(description="Reimportovat LaTeX vybraných materiálů")
    def reimport_latex(self, request, queryset):
        """
        Znovu vygeneruje online verzi vybraných zdrojových materiálů.
        """

        success_count = 0
        failed = []

        for material in queryset:
            if material.source_material_id:
                failed.append(
                    f"{material.title}: jde o automaticky odvozený materiál"
                )
                continue

            if not material.source_tex:
                failed.append(
                    f"{material.title}: chybí zdrojový LaTeX"
                )
                continue

            try:
                import_material_tex(
                    material
                )

            except TexImportError as exc:
                failed.append(
                    f"{material.title}: {exc}"
                )

            except Exception as exc:
                failed.append(
                    (
                        f"{material.title}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

            else:
                success_count += 1

        if success_count:
            self.message_user(
                request,
                (
                    "Úspěšně reimportováno materiálů: "
                    f"{success_count}."
                ),
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                (
                    "Některé materiály se nepodařilo reimportovat: "
                    + " | ".join(failed)
                ),
                level=messages.ERROR,
            )


# =============================================================================
# Samostatná administrace kapitol
# =============================================================================

@admin.register(MaterialSection)
class MaterialSectionAdmin(admin.ModelAdmin):
    """
    Samostatný přehled vygenerovaných kapitol.

    Hodí se především pro kontrolu výsledku importu a diagnostiku.
    """

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
