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
    Inline zatím ponecháváme přístupný hlavně pro kontrolu výsledku importu.
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

    # -------------------------------------------------------------------------
    # Seznam materiálů
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Editace materiálu
    # -------------------------------------------------------------------------

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

    # Zobrazí kapitoly přímo pod materiálem.
    inlines = (
        MaterialSectionInline,
    )

    # -------------------------------------------------------------------------
    # Hromadné admin akce
    # -------------------------------------------------------------------------

    actions = (
        "reimport_latex",
    )

    # -------------------------------------------------------------------------
    # Automatický import při nahrání nového LaTeXového zdroje
    # -------------------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        """
        Uloží materiál a při změně source_tex automaticky spustí LaTeX importer.

        Pokud se například změní pouze název, popis nebo stav materiálu,
        importer se zbytečně nespouští.

        Při chybě importu zůstává původní online verze zachována.
        """

        # Zjistíme, zda uživatel skutečně změnil zdrojový .tex soubor.
        source_tex_changed = "source_tex" in form.changed_data

        # Nejdříve musí být uložen samotný Material, aby měl importer
        # k dispozici aktuální source_tex.
        super().save_model(request, obj, form, change)

        # Pokud se LaTeX nezměnil nebo není nahrán, není co importovat.
        if not source_tex_changed or not obj.source_tex:
            return

        try:
            import_material_tex(obj)

        except TexImportError as exc:
            # Očekávaná chyba našeho importního procesu.
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
            # Pojistka proti neočekávaným chybám, aby administrace
            # nespadla celou chybovou stránkou.
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
            # Import proběhl úspěšně – zobrazíme počet vzniklých kapitol.
            section_count = obj.sections.count()

            self.message_user(
                request,
                (
                    "LaTeX byl úspěšně importován. "
                    f"Vytvořeno kapitol: {section_count}."
                ),
                level=messages.SUCCESS,
            )

    # -------------------------------------------------------------------------
    # Ruční / hromadný reimport existujících materiálů
    # -------------------------------------------------------------------------

    @admin.action(description="Reimportovat LaTeX vybraných materiálů")
    def reimport_latex(self, request, queryset):
        """
        Znovu vygeneruje online verzi vybraných materiálů.

        Hodí se například po změně:
        - tex_preprocessor.py,
        - mathera.lua,
        - pravidel převodu LaTeXu do HTML.

        Není tedy nutné znovu nahrávat stejný .tex soubor.
        """

        success_count = 0
        failed = []

        for material in queryset:
            # Materiál bez LaTeXového zdroje není možné reimportovat.
            if not material.source_tex:
                failed.append(
                    f"{material.title}: chybí zdrojový LaTeX"
                )
                continue

            try:
                import_material_tex(material)

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

        # Souhrnná zpráva o úspěšných importechech.
        if success_count:
            self.message_user(
                request,
                (
                    "Úspěšně reimportováno materiálů: "
                    f"{success_count}."
                ),
                level=messages.SUCCESS,
            )

        # Chybové materiály zobrazíme zvlášť.
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