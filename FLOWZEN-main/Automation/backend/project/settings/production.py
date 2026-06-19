"""
Production settings for Workflow Automation Platform
Enterprise-grade configuration with security, performance, and scalability
"""

import os
import logging.config
from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database Configuration - PostgreSQL with Connection Pooling
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME', 'workflow_automation'),
        'USER': os.environ.get('DATABASE_USER', 'workflow_user'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'OPTIONS': {
            'MAX_CONNS': 20,
            'OPTIONS': {
                'MAX_CONNS': 20,
            }
        },
        'CONN_MAX_AGE': 600,  # 10 minutes
    },
    # Read replica for analytics and reporting
    'analytics': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('ANALYTICS_DATABASE_NAME', 'workflow_analytics'),
        'USER': os.environ.get('ANALYTICS_DATABASE_USER', 'analytics_user'),
        'PASSWORD': os.environ.get('ANALYTICS_DATABASE_PASSWORD'),
        'HOST': os.environ.get('ANALYTICS_DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('ANALYTICS_DATABASE_PORT', '5432'),
        'OPTIONS': {
            'MAX_CONNS': 10,
        },
        'CONN_MAX_AGE': 600,
    }
}

# Cache Configuration - Redis Cluster
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{os.environ.get('REDIS_PASSWORD')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/0",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'TIMEOUT': 300,  # 5 minutes default timeout
        'KEY_PREFIX': 'workflow_automation',
        'VERSION': 1,
    },
    # Separate cache for sessions
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{os.environ.get('REDIS_PASSWORD')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 20,
            },
        },
        'TIMEOUT': 86400,  # 24 hours for sessions
    },
    # Cache for workflow definitions
    'workflows': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{os.environ.get('REDIS_PASSWORD')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/2",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 30,
            },
        },
        'TIMEOUT': 3600,  # 1 hour for workflow definitions
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Security Settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# CSRF Protection
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [
    'https://api.workflow-automation.com',
    'https://app.workflow-automation.com',
    'https://admin.workflow-automation.com',
]

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    'https://app.workflow-automation.com',
    'https://admin.workflow-automation.com',
]
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration for Production
CELERY_BROKER_URL = f"redis://:{os.environ.get('REDIS_PASSWORD')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/3"
CELERY_RESULT_BACKEND = f"redis://:{os.environ.get('REDIS_PASSWORD')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/4"

CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Performance Optimizations
CELERY_TASK_COMPRESSION = 'gzip'
CELERY_RESULT_COMPRESSION = 'gzip'
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Task Routing
CELERY_TASK_ROUTES = {
    'workflows.tasks.execute_workflow': {'queue': 'workflow_execution'},
    'workflows.tasks.execute_node': {'queue': 'node_execution'},
    'workflows.tasks.send_email': {'queue': 'email'},
    'workflows.tasks.http_request': {'queue': 'http'},
    'workflows.tasks.ai_processing': {'queue': 'ai'},
    'workflows.tasks.analytics': {'queue': 'analytics'},
}

# Queue Configuration
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'workflow_execution': {
        'exchange': 'workflow_execution',
        'routing_key': 'workflow_execution',
    },
    'node_execution': {
        'exchange': 'node_execution',
        'routing_key': 'node_execution',
    },
    'email': {
        'exchange': 'email',
        'routing_key': 'email',
    },
    'http': {
        'exchange': 'http',
        'routing_key': 'http',
    },
    'ai': {
        'exchange': 'ai',
        'routing_key': 'ai',
    },
    'analytics': {
        'exchange': 'analytics',
        'routing_key': 'analytics',
    },
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/workflow-automation/django.log',
            'maxBytes': 1024*1024*100,  # 100MB
            'backupCount': 10,
            'formatter': 'json',
        },
    },
    'root': {
        'level': os.environ.get('LOG_LEVEL', 'INFO'),
        'handlers': ['console', 'file'],
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'workflows': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Static Files Configuration
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files Configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@workflow-automation.com')

# Monitoring and Metrics
PROMETHEUS_METRICS_EXPORT_PORT = int(os.environ.get('METRICS_PORT', '8001'))
PROMETHEUS_METRICS_EXPORT_ADDRESS = '0.0.0.0'

# Feature Flags
ENABLE_AI_FEATURES = os.environ.get('ENABLE_AI_FEATURES', 'True').lower() == 'true'
ENABLE_ADVANCED_ANALYTICS = os.environ.get('ENABLE_ADVANCED_ANALYTICS', 'True').lower() == 'true'
ENABLE_ENTERPRISE_FEATURES = os.environ.get('ENABLE_ENTERPRISE_FEATURES', 'True').lower() == 'true'

# API Configuration
REST_FRAMEWORK.update({
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '1000/hour',
        'user': '10000/hour',
        'premium': '100000/hour',
        'enterprise': '1000000/hour',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'MAX_PAGE_SIZE': 1000,
})

# JWT Configuration
from datetime import timedelta
SIMPLE_JWT.update({
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ.get('JWT_SECRET_KEY', SECRET_KEY),
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
})

# External API Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# OAuth Configuration
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

# Workflow Engine Configuration
MAX_CONCURRENT_EXECUTIONS = int(os.environ.get('MAX_CONCURRENT_EXECUTIONS', '1000'))
DEFAULT_EXECUTION_TIMEOUT = int(os.environ.get('DEFAULT_EXECUTION_TIMEOUT', '3600'))
WORKFLOW_CACHE_TTL = int(os.environ.get('WORKFLOW_CACHE_TTL', '300'))

# Performance Monitoring
PERFORMANCE_MONITORING = {
    'ENABLE_QUERY_PROFILING': True,
    'SLOW_QUERY_THRESHOLD': 0.5,  # seconds
    'ENABLE_MEMORY_PROFILING': True,
    'ENABLE_EXECUTION_PROFILING': True,
}

# Health Check Configuration
HEALTH_CHECK = {
    'DISK_USAGE_MAX': 90,  # percentage
    'MEMORY_USAGE_MAX': 90,  # percentage
    'DATABASE_CONN_MAX': 80,  # percentage of max connections
}

# Backup Configuration
BACKUP_CONFIG = {
    'ENABLE_AUTO_BACKUP': True,
    'BACKUP_INTERVAL': 3600,  # seconds (1 hour)
    'BACKUP_RETENTION_DAYS': 30,
    'BACKUP_STORAGE': 's3://workflow-automation-backups/',
}

# Error Tracking
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(auto_enabling=True),
            CeleryIntegration(auto_enabling=True),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
    )