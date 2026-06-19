"""
Production Django Settings with Security Hardening
CRITICAL: Use this configuration for production deployment
"""
import os
from .settings import *

# ================================
# SECURITY SETTINGS (CRITICAL)
# ================================

# Debug MUST be False in production
DEBUG = False

# Allowed hosts - MUST be configured
ALLOWED_HOSTS = [
    host.strip() 
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') 
    if host.strip()
]

if not ALLOWED_HOSTS:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set in production")

# Security middleware - ORDER IS CRITICAL
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static files
    'workflows.middleware_security.SecurityAuditMiddleware',
    'workflows.middleware_security.RateLimitMiddleware',
    'workflows.middleware_security.PayloadSizeLimitMiddleware',
    'workflows.middleware.SecurityHeadersMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'workflows.middleware_security.CSRFEnhancementMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'workflows.middleware_security.TenantIsolationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'workflows.middleware.PerformanceMonitoringMiddleware',
    'workflows.middleware.MaintenanceModeMiddleware',
]

# ================================
# HTTPS & SSL SETTINGS
# ================================

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REDIRECT_EXEMPT = [r'^health/$']  # Health check exempt

# ================================
# COOKIE SECURITY
# ================================

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS
]

# ================================
# CONTENT SECURITY
# ================================

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ================================
# DATABASE SECURITY
# ================================

DATABASES['default'].update({
    'CONN_MAX_AGE': 60,
    'CONN_HEALTH_CHECKS': True,
    'OPTIONS': {
        'sslmode': 'require',
        'connect_timeout': 10,
        'application_name': 'automation_platform',
    }
})

# Connection pooling for production
if os.environ.get('DATABASE_POOL_ENABLED', 'True') == 'True':
    DATABASES['default']['OPTIONS'].update({
        'MAX_CONNS': 20,
        'MIN_CONNS': 5,
    })

# ================================
# CACHE SECURITY
# ================================

CACHES['default'].update({
    'TIMEOUT': 300,
    'OPTIONS': {
        'MAX_ENTRIES': 10000,
        'CULL_FREQUENCY': 3,
        'CONNECTION_POOL_KWARGS': {
            'max_connections': 50,
            'retry_on_timeout': True,
        }
    }
})

# ================================
# LOGGING CONFIGURATION
# ================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "process": %(process)d, "message": "%(message)s"}',
        },
        'security': {
            'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "type": "security", "message": "%(message)s"}',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/automation/django.log',
            'maxBytes': 50 * 1024 * 1024,  # 50MB
            'backupCount': 5,
            'formatter': 'json',
        },
        'security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/automation/security.log',
            'maxBytes': 50 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'security',
        },
        'audit': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/automation/audit.log',
            'maxBytes': 100 * 1024 * 1024,  # 100MB
            'backupCount': 20,
            'formatter': 'json',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'workflows': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'security': {
            'handlers': ['security', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'audit': {
            'handlers': ['audit'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# ================================
# CELERY PRODUCTION SETTINGS
# ================================

CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
CELERY_TASK_SOFT_TIME_LIMIT = 1800  # 30 minutes
CELERY_TASK_TIME_LIMIT = 3600       # 1 hour hard limit
CELERY_WORKER_DISABLE_RATE_LIMITS = False
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_IGNORE_RESULT = False
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# Celery security
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_ACCEPT_CONTENT = ['json']

# ================================
# REST FRAMEWORK SECURITY
# ================================

REST_FRAMEWORK.update({
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'workflows.security_permissions.StrictTenantIsolation',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'workflows.throttles.BurstProtectionThrottle',
        'workflows.throttles.AdaptiveRateThrottle',
        'workflows.throttles.TenantExecutionRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': '10/min',
        'tenant_execution': '1000/hour',
        'tenant_webhook': '500/hour',
        'anon': '100/hour',
        'user': '1000/hour',
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'EXCEPTION_HANDLER': 'workflows.exceptions.security_exception_handler',
})

# ================================
# STATIC FILES SECURITY
# ================================

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Whitenoise security
WHITENOISE_USE_FINDERS = False
WHITENOISE_AUTOREFRESH = False
WHITENOISE_MAX_AGE = 31536000  # 1 year

# ================================
# FILE UPLOAD SECURITY
# ================================

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# ================================
# CORS SECURITY
# ================================

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS
]

# ================================
# SECURITY MONITORING
# ================================

# Performance monitoring settings
PERFORMANCE_MONITORING = {
    'SLOW_REQUEST_THRESHOLD': 2.0,  # seconds
    'MAX_QUERIES_PER_REQUEST': 50,
    'ENABLE_PROFILING': False,
}

# Security settings
SECURITY_SETTINGS = {
    'MAX_PAYLOAD_SIZE': 10 * 1024 * 1024,  # 10MB
    'MAX_EXECUTION_TIME': 3600,  # 1 hour
    'ENABLE_IP_ALLOWLIST': True,
    'ENABLE_RATE_LIMITING': True,
    'AUDIT_ALL_REQUESTS': True,
}

# ================================
# ENVIRONMENT VALIDATION
# ================================

# Validate required environment variables
REQUIRED_ENV_VARS = [
    'DJANGO_SECRET_KEY',
    'DJANGO_ALLOWED_HOSTS',
    'DATABASE_NAME',
    'DATABASE_USER',
    'DATABASE_PASSWORD',
    'REDIS_URL',
    'CREDENTIALS_MASTER_KEY',
]

for var in REQUIRED_ENV_VARS:
    if not os.environ.get(var):
        raise ValueError(f"Required environment variable {var} is not set")

# Validate secret key strength
if len(SECRET_KEY) < 50:
    raise ValueError("DJANGO_SECRET_KEY must be at least 50 characters long")

# ================================
# ADDITIONAL SECURITY HEADERS
# ================================

# Custom security headers
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_PERMISSIONS_POLICY = {
    'geolocation': [],
    'microphone': [],
    'camera': [],
}

# ================================
# BACKUP & COMPLIANCE
# ================================

# Backup settings
BACKUP_ENABLED = os.environ.get('BACKUP_ENABLED', 'True') == 'True'
BACKUP_ENCRYPTION_KEY = os.environ.get('BACKUP_ENCRYPTION_KEY')

# GDPR compliance
GDPR_COMPLIANCE_ENABLED = os.environ.get('GDPR_COMPLIANCE_ENABLED', 'True') == 'True'
DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', '365'))

# Audit logging
AUDIT_LOGGING_ENABLED = os.environ.get('AUDIT_LOGGING_ENABLED', 'True') == 'True'