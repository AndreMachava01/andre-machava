"""
Exemplo de configurações para integrações com transportadoras.
Adicione estas configurações ao seu settings.py
"""

# =============================================================================
# CONFIGURAÇÕES DE INTEGRAÇÃO COM TRANSPORTADORAS
# =============================================================================

# Correios (Brasil)
CORREIOS_API_KEY = 'sua_api_key_correios'
CORREIOS_API_SECRET = 'seu_api_secret_correios'
CORREIOS_ENVIRONMENT = 'sandbox'  # ou 'production'

# DHL
DHL_API_KEY = 'sua_api_key_dhl'
DHL_API_SECRET = 'seu_api_secret_dhl'
DHL_ENVIRONMENT = 'sandbox'  # ou 'production'

# Transportadora Local
LOCAL_CARRIER_API_KEY = 'sua_api_key_local'
LOCAL_CARRIER_API_URL = 'https://api.transportadora-local.com'
LOCAL_CARRIER_ENVIRONMENT = 'sandbox'  # ou 'production'

# Firebase (para notificações push)
FIREBASE_SERVER_KEY = 'sua_firebase_server_key'

# =============================================================================
# CONFIGURAÇÕES DE TIMEOUT E RETRY
# =============================================================================

# Timeouts para APIs externas
CARRIER_API_TIMEOUT = 30
CARRIER_API_RETRY_COUNT = 3
CARRIER_API_RETRY_DELAY = 1

# Intervalo de sincronização automática (em minutos)
CARRIER_SYNC_INTERVAL_MINUTES = 30

# =============================================================================
# CONFIGURAÇÕES DE LOGGING
# =============================================================================

# Nível de log para integrações
INTEGRATION_LOG_LEVEL = 'INFO'

# Log de requests/responses das APIs
LOG_API_CALLS = True

# =============================================================================
# CONFIGURAÇÕES DE CACHE
# =============================================================================

# Cache para cotações (em segundos)
QUOTE_CACHE_TIMEOUT = 300  # 5 minutos

# Cache para dados de rastreamento (em segundos)
TRACKING_CACHE_TIMEOUT = 60  # 1 minuto

# =============================================================================
# CONFIGURAÇÕES DE VALIDAÇÃO
# =============================================================================

# Validação de CEP
VALIDATE_ZIPCODE = True

# Validação de dimensões
MAX_WEIGHT_KG = 30
MAX_DIMENSION_CM = 100

# =============================================================================
# CONFIGURAÇÕES DE WEBHOOK
# =============================================================================

# URLs de webhook para cada transportadora
CORREIOS_WEBHOOK_URL = 'https://seu-site.com/webhooks/correios/'
DHL_WEBHOOK_URL = 'https://seu-site.com/webhooks/dhl/'
LOCAL_CARRIER_WEBHOOK_URL = 'https://seu-site.com/webhooks/local/'

# Chaves de validação de webhook
CORREIOS_WEBHOOK_SECRET = 'seu_webhook_secret_correios'
DHL_WEBHOOK_SECRET = 'seu_webhook_secret_dhl'
LOCAL_CARRIER_WEBHOOK_SECRET = 'seu_webhook_secret_local'

# =============================================================================
# CONFIGURAÇÕES DE AMBIENTE
# =============================================================================

# Ambiente atual
ENVIRONMENT = 'development'  # 'development', 'staging', 'production'

# =============================================================================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================================================================

# Email para alertas
ALERT_EMAIL = 'admin@empresa.com'

# Webhook do Slack para alertas
SLACK_WEBHOOK_URL = 'https://hooks.slack.com/services/...'

# =============================================================================
# CONFIGURAÇÕES DE RATE LIMITING
# =============================================================================

# Limites de requisições por minuto
CORREIOS_RATE_LIMIT = 100
DHL_RATE_LIMIT = 200
LOCAL_CARRIER_RATE_LIMIT = 500

# =============================================================================
# CONFIGURAÇÕES DE DESENVOLVIMENTO
# =============================================================================

# Mock de respostas da API (apenas para desenvolvimento)
MOCK_API_RESPONSES = False

# =============================================================================
# CONFIGURAÇÕES DE EMAIL
# =============================================================================

# Configurações de email para notificações
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'seu_email@gmail.com'
EMAIL_HOST_PASSWORD = 'sua_senha_app'
DEFAULT_FROM_EMAIL = 'Logística <noreply@empresa.com>'

# =============================================================================
# CONFIGURAÇÕES DE CELERY (para tarefas assíncronas)
# =============================================================================

# Configurações do Celery para processamento assíncrono
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Sao_Paulo'

# =============================================================================
# CONFIGURAÇÕES DE REDIS (para cache e sessões)
# =============================================================================

# Configurações do Redis
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# =============================================================================
# CONFIGURAÇÕES DE LOGGING
# =============================================================================

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
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/integrations.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'meuprojeto.empresa.services.carrier_integration_service': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'meuprojeto.empresa.services.carriers': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
