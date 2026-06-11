"""
Carrega as configurações conforme o ambiente (DJANGO_ENV).
- development: DEBUG=True, CSRF relaxado
- production: DEBUG=False, opções de segurança activas

Por defeito usa development se DJANGO_ENV não estiver definido.
"""
import os

env_name = os.environ.get('DJANGO_ENV', 'development')

if env_name == 'production':
    from .production import *  # noqa: F401, F403
else:
    from .development import *  # noqa: F401, F403
