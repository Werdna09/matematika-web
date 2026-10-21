from django.contrib import admin
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase

from accounts.models import User
from exams.models import Exam
from materials.models import Material
from sidequests.models import SideQuest


class AdminFileDownloadTests(SimpleTestCase):
    file_fields = (
        (Material, "source_tex", "TEX"),
        (Material, "pdf_file", "PDF"),
        (SideQuest, "source_tex", "TEX"),
        (SideQuest, "pdf_file", "PDF"),
        (Exam, "source_tex", "TEX"),
        (Exam, "source_pdf", "PDF"),
    )

    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = User(is_active=True, is_staff=True, is_superuser=True)

    def get_file_field(self, model, field_name, name=""):
        obj = model(**{field_name: name})
        value = getattr(obj, field_name)
        value.storage = InMemoryStorage()
        form = admin.site._registry[model].get_form(self.request, obj)
        return form.base_fields[field_name], value

    def test_existing_files_offer_download_and_keep_upload_and_clear(self):
        for model, field_name, extension in self.file_fields:
            with self.subTest(model=model, field=field_name):
                field, value = self.get_file_field(
                    model, field_name, f"test.{extension.lower()}"
                )
                value.storage.save(value.name, ContentFile(b"test"))
                html = field.widget.render(field_name, value)

                self.assertIn(f'Stáhnout {extension}</a>', html)
                self.assertIn(f'href="{value.url}" download', html)
                self.assertIn(f'type="file" name="{field_name}"', html)
                self.assertIn(f'name="{field_name}-clear"', html)

                upload = SimpleUploadedFile(value.name, b"new content")
                self.assertIs(field.clean(upload, initial=value), upload)
                self.assertIs(field.clean(False, initial=value), False)

    def test_empty_and_missing_files_do_not_offer_download(self):
        for model, field_name, extension in self.file_fields:
            for name in ("", f"missing.{extension.lower()}"):
                with self.subTest(model=model, field=field_name, name=name):
                    field, value = self.get_file_field(model, field_name, name)
                    html = field.widget.render(field_name, value)

                    self.assertNotIn("Stáhnout", html)
                    self.assertIn(f'type="file" name="{field_name}"', html)

    def test_download_url_is_escaped(self):
        field, value = self.get_file_field(Material, "source_tex", "test.tex")
        value.storage.save(value.name, ContentFile(b"test"))
        value.storage.url = lambda name: '/media/test.tex?x="<script>&y=1'

        html = field.widget.render("source_tex", value)

        self.assertIn(
            'href="/media/test.tex?x=&quot;&lt;script&gt;&amp;y=1" download',
            html,
        )
        self.assertNotIn("<script>", html)
