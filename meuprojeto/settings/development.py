"""
Configurações de desenvolvimento.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

# CSRF relaxado em desenvolvimento
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_HTTPONLY = False
