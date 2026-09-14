from django.contrib import admin, messages

from .models import Exam, ExamTask
from .services.tex_importer import ExamImportError, import_exam_tex


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "year",
        "term",
        "status",
        "task_count",
        "updated_at",
    )

    list_filter = (
        "status",
        "term",
        "year",
    )

    search_fields = (
        "title",
        "description",
    )

    prepopulated_fields = {
        "slug": ("title",),
    }

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    actions = (
        "reimport_exam",
    )

    @admin.display(description="Úloh")
    def task_count(self, obj):
        return obj.tasks.count()

    def save_model(self, request, obj, form, change):
        source_changed = (
            "source_tex" in form.changed_data
            or "source_pdf" in form.changed_data
        )

        super().save_model(request, obj, form, change)

        if not source_changed or not obj.source_tex or not obj.source_pdf:
            return

        try:
            count = import_exam_tex(obj)
        except ExamImportError as exc:
            self.message_user(
                request,
                (
                    "Maturita byla uložena, ale automatický import se nezdařil. "
                    f"Původní webové úlohy zůstaly zachovány. Chyba: {exc}"
                ),
                level=messages.ERROR,
            )
        except Exception as exc:
            self.message_user(
                request,
                f"Neočekávaná chyba importu: {type(exc).__name__}: {exc}",
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Maturita byla úspěšně importována. Úloh: {count}.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Reimportovat vybrané maturity")
    def reimport_exam(self, request, queryset):
        success = 0
        failed = []

        for exam in queryset:
            if not exam.source_tex or not exam.source_pdf:
                failed.append(f"{exam.title}: chybí .tex nebo originální PDF")
                continue

            try:
                import_exam_tex(exam)
            except Exception as exc:
                failed.append(f"{exam.title}: {exc}")
            else:
                success += 1

        if success:
            self.message_user(
                request,
                f"Úspěšně reimportováno maturit: {success}.",
                level=messages.SUCCESS,
            )

        if failed:
            self.message_user(
                request,
                "Některé importy selhaly: " + " | ".join(failed),
                level=messages.ERROR,
            )


@admin.register(ExamTask)
class ExamTaskAdmin(admin.ModelAdmin):
    list_display = (
        "exam",
        "number",
        "page_number",
        "order",
        "updated_at",
    )

    list_filter = (
        "exam",
    )

    search_fields = (
        "exam__title",
    )

    ordering = (
        "exam",
        "order",
        "number",
    )

    readonly_fields = (
        "exam",
        "number",
        "order",
        "page_number",
        "trim_left_mm",
        "trim_bottom_mm",
        "trim_right_mm",
        "trim_top_mm",
        "statement_image",
        "solution_tex",
        "solution_html",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
