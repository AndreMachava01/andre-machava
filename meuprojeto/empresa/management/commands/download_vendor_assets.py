"""
Descarrega Font Awesome e Chart.js para static/vendor/ para evitar
"Tracking Prevention blocked access to storage" no Edge (recursos no mesmo domínio).
Executar uma vez: python manage.py download_vendor_assets
"""
import os
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


# Destino: STATICFILES_DIRS[0] = .../empresa/static
VENDOR_BASE = Path(settings.STATICFILES_DIRS[0]) / "vendor"

ASSETS = [
    # Chart.js 4.4.0
    (
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js",
        "chart.js/chart.umd.min.js",
    ),
    # Font Awesome 6.4.0
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
        "fontawesome/css/all.min.css",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-solid-900.woff2",
        "fontawesome/webfonts/fa-solid-900.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-regular-400.woff2",
        "fontawesome/webfonts/fa-regular-400.woff2",
    ),
    (
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/webfonts/fa-brands-400.woff2",
        "fontawesome/webfonts/fa-brands-400.woff2",
    ),
]


class Command(BaseCommand):
    help = "Descarrega Font Awesome e Chart.js para static/vendor/ (evita Tracking Prevention no Edge)."

    def handle(self, *args, **options):
        VENDOR_BASE.mkdir(parents=True, exist_ok=True)
        for url, rel_path in ASSETS:
            path = VENDOR_BASE / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.stdout.write(f"A obter {rel_path} ...")
                urllib.request.urlretrieve(url, path)
                self.stdout.write(self.style.SUCCESS(f"  OK {path}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  Erro {rel_path}: {e}"))
        self.stdout.write(
            self.style.SUCCESS(
                "Concluído. Use {% static 'vendor/fontawesome/css/all.min.css' %} e "
                "{% static 'vendor/chart.js/chart.umd.min.js' %} nos templates."
            )
        )
