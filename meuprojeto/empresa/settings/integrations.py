"""
Configurações para integrações com transportadoras.
"""
import os
from django.conf import settings

# =============================================================================
# CONFIGURAÇÕES DE INTEGRAÇÃO
# =============================================================================

# Correios (Brasil)
CORREIOS_API_KEY = getattr(settings, 'CORREIOS_API_KEY', os.getenv('CORREIOS_API_KEY', ''))
CORREIOS_API_SECRET = getattr(settings, 'CORREIOS_API_SECRET', os.getenv('CORREIOS_API_SECRET', ''))
CORREIOS_ENVIRONMENT = getattr(settings, 'CORREIOS_ENVIRONMENT', os.getenv('CORREIOS_ENVIRONMENT', 'sandbox'))

# DHL
DHL_API_KEY = getattr(settings, 'DHL_API_KEY', os.getenv('DHL_API_KEY', ''))
DHL_API_SECRET = getattr(settings, 'DHL_API_SECRET', os.getenv('DHL_API_SECRET', ''))
DHL_ENVIRONMENT = getattr(settings, 'DHL_ENVIRONMENT', os.getenv('DHL_ENVIRONMENT', 'sandbox'))

# Transportadora Local
LOCAL_CARRIER_API_KEY = getattr(settings, 'LOCAL_CARRIER_API_KEY', os.getenv('LOCAL_CARRIER_API_KEY', ''))
LOCAL_CARRIER_API_URL = getattr(settings, 'LOCAL_CARRIER_API_URL', os.getenv('LOCAL_CARRIER_API_URL', ''))
LOCAL_CARRIER_ENVIRONMENT = getattr(settings, 'LOCAL_CARRIER_ENVIRONMENT', os.getenv('LOCAL_CARRIER_ENVIRONMENT', 'sandbox'))

# Firebase (para notificações push)
FIREBASE_SERVER_KEY = getattr(settings, 'FIREBASE_SERVER_KEY', os.getenv('FIREBASE_SERVER_KEY', ''))

# =============================================================================
# CONFIGURAÇÕES DE TIMEOUT E RETRY
# =============================================================================

# Timeouts para APIs externas
API_TIMEOUT = getattr(settings, 'CARRIER_API_TIMEOUT', 30)
API_RETRY_COUNT = getattr(settings, 'CARRIER_API_RETRY_COUNT', 3)
API_RETRY_DELAY = getattr(settings, 'CARRIER_API_RETRY_DELAY', 1)

# Intervalo de sincronização automática (em minutos)
SYNC_INTERVAL_MINUTES = getattr(settings, 'CARRIER_SYNC_INTERVAL_MINUTES', 30)

# =============================================================================
# CONFIGURAÇÕES DE LOGGING
# =============================================================================

# Nível de log para integrações
INTEGRATION_LOG_LEVEL = getattr(settings, 'INTEGRATION_LOG_LEVEL', 'INFO')

# Log de requests/responses das APIs
LOG_API_CALLS = getattr(settings, 'LOG_API_CALLS', False)

# =============================================================================
# CONFIGURAÇÕES DE CACHE
# =============================================================================

# Cache para cotações (em segundos)
QUOTE_CACHE_TIMEOUT = getattr(settings, 'QUOTE_CACHE_TIMEOUT', 300)  # 5 minutos

# Cache para dados de rastreamento (em segundos)
TRACKING_CACHE_TIMEOUT = getattr(settings, 'TRACKING_CACHE_TIMEOUT', 60)  # 1 minuto

# =============================================================================
# CONFIGURAÇÕES DE VALIDAÇÃO
# =============================================================================

# Validação de CEP
VALIDATE_ZIPCODE = getattr(settings, 'VALIDATE_ZIPCODE', True)

# Validação de dimensões
MAX_WEIGHT_KG = getattr(settings, 'MAX_WEIGHT_KG', 30)
MAX_DIMENSION_CM = getattr(settings, 'MAX_DIMENSION_CM', 100)

# =============================================================================
# CONFIGURAÇÕES DE WEBHOOK
# =============================================================================

# URLs de webhook para cada transportadora
WEBHOOK_URLS = {
    'CORREIOS': getattr(settings, 'CORREIOS_WEBHOOK_URL', ''),
    'DHL': getattr(settings, 'DHL_WEBHOOK_URL', ''),
    'LOCAL': getattr(settings, 'LOCAL_CARRIER_WEBHOOK_URL', ''),
}

# Chaves de validação de webhook
WEBHOOK_SECRETS = {
    'CORREIOS': getattr(settings, 'CORREIOS_WEBHOOK_SECRET', ''),
    'DHL': getattr(settings, 'DHL_WEBHOOK_SECRET', ''),
    'LOCAL': getattr(settings, 'LOCAL_CARRIER_WEBHOOK_SECRET', ''),
}

# =============================================================================
# CONFIGURAÇÕES DE AMBIENTE
# =============================================================================

# Ambiente atual
ENVIRONMENT = getattr(settings, 'ENVIRONMENT', 'development')

# URLs base para cada ambiente
BASE_URLS = {
    'development': 'http://localhost:8000',
    'staging': 'https://staging.empresa.com',
    'production': 'https://empresa.com',
}

# URL base atual
BASE_URL = BASE_URLS.get(ENVIRONMENT, 'http://localhost:8000')

# =============================================================================
# CONFIGURAÇÕES DE NOTIFICAÇÃO
# =============================================================================

# Configurações de notificação por transportadora
NOTIFICATION_CONFIGS = {
    'CORREIOS': {
        'enabled': True,
        'channels': ['PUSH', 'EMAIL'],
        'events': ['STATUS_CHANGE', 'DELIVERY', 'EXCEPTION']
    },
    'DHL': {
        'enabled': True,
        'channels': ['PUSH', 'EMAIL', 'SMS'],
        'events': ['STATUS_CHANGE', 'DELIVERY', 'EXCEPTION']
    },
    'LOCAL': {
        'enabled': True,
        'channels': ['PUSH', 'EMAIL'],
        'events': ['STATUS_CHANGE', 'DELIVERY', 'EXCEPTION']
    }
}

# =============================================================================
# CONFIGURAÇÕES DE RATE LIMITING
# =============================================================================

# Limites de requisições por minuto
RATE_LIMITS = {
    'CORREIOS': getattr(settings, 'CORREIOS_RATE_LIMIT', 100),
    'DHL': getattr(settings, 'DHL_RATE_LIMIT', 200),
    'LOCAL': getattr(settings, 'LOCAL_CARRIER_RATE_LIMIT', 500),
}

# =============================================================================
# CONFIGURAÇÕES DE FALLBACK
# =============================================================================

# Configurações de fallback quando APIs externas falham
FALLBACK_CONFIG = {
    'enabled': True,
    'use_cached_data': True,
    'notify_on_failure': True,
    'retry_after_minutes': 15
}

# =============================================================================
# CONFIGURAÇÕES DE MONITORAMENTO
# =============================================================================

# Configurações de monitoramento e alertas
MONITORING_CONFIG = {
    'enabled': True,
    'alert_threshold_failure_rate': 0.1,  # 10%
    'alert_threshold_response_time': 5.0,  # 5 segundos
    'alert_email': getattr(settings, 'ALERT_EMAIL', 'admin@empresa.com'),
    'slack_webhook': getattr(settings, 'SLACK_WEBHOOK_URL', ''),
}

# =============================================================================
# CONFIGURAÇÕES DE SEGURANÇA
# =============================================================================

# Configurações de segurança para APIs
SECURITY_CONFIG = {
    'validate_ssl': True,
    'max_redirects': 3,
    'user_agent': 'LogisticaApp/1.0',
    'request_timeout': API_TIMEOUT,
}

# =============================================================================
# CONFIGURAÇÕES DE DESENVOLVIMENTO
# =============================================================================

# Configurações específicas para desenvolvimento
if ENVIRONMENT == 'development':
    DEBUG_API_CALLS = True
    MOCK_API_RESPONSES = getattr(settings, 'MOCK_API_RESPONSES', False)
    LOG_ALL_REQUESTS = True
else:
    DEBUG_API_CALLS = False
    MOCK_API_RESPONSES = False
    LOG_ALL_REQUESTS = False
