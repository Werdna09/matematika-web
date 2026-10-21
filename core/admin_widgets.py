from pathlib import Path

from django.contrib.admin.widgets import AdminFileWidget
from django.utils.html import format_html


class DownloadableAdminFileWidget(AdminFileWidget):
    """Ponechá upload i mazání a přidá stažení existujícího souboru."""

    def render(self, name, value, attrs=None, renderer=None):
        widget = super().render(name, value, attrs=attrs, renderer=renderer)

        if not value or not value.storage.exists(value.name):
            return widget

        return format_html(
            '{}<p><a href="{}" download>Stáhnout {}</a></p>',
            widget,
            value.url,
            Path(value.name).suffix[1:].upper(),
        )
