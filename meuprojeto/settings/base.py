"""
Configurações base do Django (comuns a todos os ambientes).
"""
from pathlib import Path

import environ

# Diretório raiz do projeto (pasta ANDRE)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Carregar variáveis de ambiente do ficheiro .env (se existir)
env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)

# Procurar .env em BASE_DIR
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# Segurança: SECRET_KEY obrigatória
SECRET_KEY = env(
    'SECRET_KEY',
    default='django-insecure-9p!^_t3^&=4+%khqdh8jerbcr6)j^wn@g@pki8et*p+fzk7axs'
)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# CSRF Trusted Origins
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:54052',
    'http://localhost:54052',
]

# Vendas / Produção: restringir acesso por grupo Django
RESTRICT_VENDAS_PRODUCAO_BY_GROUP = env.bool(
    'RESTRICT_VENDAS_PRODUCAO_BY_GROUP', default=False
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'meuprojeto.empresa',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'meuprojeto.empresa.middleware.DisableCSRFOriginCheckMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'meuprojeto.empresa.middleware.VendasProducaoAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'meuprojeto.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'meuprojeto.wsgi.application'

# Base de dados
# Suporta DATABASE_URL ou variáveis individuais
if env.str('DATABASE_URL', default=''):
    DATABASES = {'default': env.db()}
else:
    DATABASES = {
        'default': {
            'ENGINE': env.str('DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': env.str('DB_NAME', default='andre_conception'),
            'USER': env.str('DB_USER', default='postgres'),
            'PASSWORD': env.str('DB_PASSWORD', default=''),
            'HOST': env.str('DB_HOST', default='localhost'),
            'PORT': env.str('DB_PORT', default='5432'),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalização
LANGUAGE_CODE = env.str('LANGUAGE_CODE', default='pt')
TIME_ZONE = env.str('TIME_ZONE', default='Africa/Maputo')
USE_I18N = True
USE_TZ = True

# Ficheiros estáticos e media
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'meuprojeto' / 'empresa' / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'django.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'meuprojeto.empresa.views_inventario': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
