"""
Configurações de produção.
"""
from .base import *  # noqa: F401, F403

DEBUG = False

# Segurança em produção
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# SECRET_KEY deve vir obrigatoriamente do ambiente em produção
if SECRET_KEY == 'django-insecure-9p!^_t3^&=4+%khqdh8jerbcr6)j^wn@g@pki8et*p+fzk7axs':
    raise ValueError(
        'SECRET_KEY inválida para produção. Defina a variável SECRET_KEY no ambiente.'
    )
