"""
Django settings for project project.
"""
import os
import logging
import base64
from urllib.parse import urlparse
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    _possible_env_paths = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        BASE_DIR.parent.parent / ".env",
    ]
    for _env_p in _possible_env_paths:
        if _env_p.exists():
            load_dotenv(dotenv_path=_env_p, override=False)
            break
except ImportError:
    pass


# Centralized Base Site URL
SITE_URL = os.environ.get("SITE_URL", os.environ.get("PUBLIC_URL", "http://localhost:8000")).rstrip("/")

# Environment & Security
_insecure_default_key = "django-insecure-q7_fc9z_$)r9(gb-+6*#(e+$fc_gh6hdg1!4m2%ihxuj85f5p#"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", os.environ.get("SECRET_KEY", _insecure_default_key))
DEBUG = os.environ.get("DJANGO_DEBUG", os.environ.get("DEBUG", "False")).lower() in ["true", "1", "yes"]

# Strict Secret Key Validation in Production
if not DEBUG and (not SECRET_KEY or SECRET_KEY == _insecure_default_key):
    raise ImproperlyConfigured(
        "CRITICAL SECURITY ERROR: DJANGO_SECRET_KEY environment variable must be set to a secure secret key in production."
    )

_allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", os.environ.get("DJANGO_ALLOWED_HOSTS", "*"))
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]
for ngrok_domain in [".ngrok-free.dev", ".ngrok.io", "localhost", "127.0.0.1", "*"]:
    if ngrok_domain not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(ngrok_domain)

# Trusted Origins for CSRF
_csrf_origins_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_env.split(",") if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        SITE_URL,
        "https://*.ngrok-free.dev",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

# Reverse Proxy & SSL Headers
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Production Security & Cookie Hardening
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() == "true"
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "True").lower() == "true"
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "True").lower() == "true"
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = os.environ.get("SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin")
    
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
    CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True").lower() == "true"
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = os.environ.get("CSRF_COOKIE_HTTPONLY", "True").lower() == "true"
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_AGE = int(os.environ.get("SESSION_COOKIE_AGE", "1209600")) # 2 weeks
SESSION_SAVE_EVERY_REQUEST = True


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'notifications',
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "channels",
    "django_celery_beat",
    "workflows",
    "authentication",
    "django_prometheus",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "workflows.middleware.HealthCheckMiddleware",  # Health Check (High Priority)
    "workflows.middleware.SecurityHeadersMiddleware",  # Security Headers
    "whitenoise.middleware.WhiteNoiseMiddleware", # Enable WhiteNoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "workflows.middleware_security.CSRFEnhancementMiddleware", # Enhanced CSRF
    "workflows.middleware_security.TenantIsolationMiddleware", # Critical Tenant Isolation
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "workflows.middleware_security.RateLimitMiddleware", # Rate Limiting
    "workflows.middleware_security.PayloadSizeLimitMiddleware", # Payload Size Limit
    "workflows.middleware_security.InputSanitizationMiddleware", # Input Sanitization
    "workflows.middleware_security.SecurityAuditMiddleware", # Audit Logging
    # Global exception handling (must be early in the stack)
    "workflows.middleware.exception_handling.GlobalExceptionHandlingMiddleware",
    "workflows.middleware.exception_handling.SafeAdminMiddleware",
    "workflows.middleware.maintenance.MaintenanceModeMiddleware", # Maintenance Mode
]


# Add WhiteNoise only in production
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "frontend" / "templates",          # Docker: /app/frontend/templates
            BASE_DIR.parent / "frontend" / "templates",   # Local: ../frontend/templates
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"


# Database
# Supports DATABASE_URL (Railway, Render, DigitalOcean) and individual parameters
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    _parsed_db = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed_db.path.lstrip("/"),
            "USER": _parsed_db.username or "automation",
            "PASSWORD": _parsed_db.password or "",
            "HOST": _parsed_db.hostname or "db",
            "PORT": str(_parsed_db.port or 5432),
            "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "600" if not DEBUG else "0")),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DATABASE_NAME", "automation"),
            "USER": os.environ.get("DATABASE_USER", "automation"),
            "PASSWORD": os.environ.get("DATABASE_PASSWORD", "automation"),
            "HOST": os.environ.get("DATABASE_HOST", "db"),
            "PORT": os.environ.get("DATABASE_PORT", "5432"),
            "CONN_MAX_AGE": int(os.environ.get("CONN_MAX_AGE", "600" if not DEBUG else "0")),
            "CONN_HEALTH_CHECKS": True,
        }
    }

if os.environ.get("DJANGO_DB_SQLITE", "False") == "True":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True



# Media files (User uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Authentication Redirects
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"



# Only use WhiteNoise storage in production
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "workflows.throttles.TenantExecutionRateThrottle",
        "workflows.throttles.TenantWebhookRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "tenant_execution": os.environ.get("RATE_TENANT_EXECUTION", "30/min"),
        "tenant_webhook": os.environ.get("RATE_TENANT_WEBHOOK", "300/min"),
    },
    # Custom exception handler for structured error responses
    "EXCEPTION_HANDLER": "workflows.middleware.exception_handling.custom_drf_exception_handler",
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# CORS Settings
_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _cors_origins_env:
    CORS_ALLOWED_ORIGINS = [c.strip() for c in _cors_origins_env.split(",") if c.strip()]
    CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "False").lower() == "true"
else:
    CORS_ALLOW_ALL_ORIGINS = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "True").lower() == "true"
CORS_ALLOW_CREDENTIALS = True

# Celery Configuration
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

# Celery Broker Connection Resilience
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_ALWAYS_EAGER", "False") == "True"

# For development: Use localhost Redis if Docker Redis is unreachable
if DEBUG and not os.environ.get("CELERY_BROKER_URL"):
    try:
        import redis
        # Test connection to localhost Redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=1)
        r.ping()
        print("✅ Using localhost Redis for development")
    except:
        # If no Redis available, use eager mode (synchronous execution)
        CELERY_TASK_ALWAYS_EAGER = True
        CELERY_TASK_EAGER_PROPAGATES = True
        print("!  No Redis available - using synchronous task execution")

# Google Integrations
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", f"{SITE_URL}/api/auth/google/callback")


CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Celery High Throughput & Reliability Optimization
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.environ.get("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get("CELERY_WORKER_MAX_TASKS_PER_CHILD", "1000"))
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True

# Celery Beat for scheduled workflows - CRITICAL: Use DatabaseScheduler explicitly
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# CRITICAL: Ensure django-celery-beat is properly configured
CELERY_BEAT_SCHEDULE = {}  # Will be populated from database
CELERY_BEAT_MAX_LOOP_INTERVAL = 60  # Check for new tasks every 60 seconds

# Django Channels
ASGI_APPLICATION = "project.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (
                    urlparse(REDIS_URL).hostname or "redis",
                    urlparse(REDIS_URL).port or 6379,
                )
            ],
        },
    },
}

# Webhook Security
WEBHOOK_SECRET_KEY = os.environ.get("WEBHOOK_SECRET_KEY", SECRET_KEY)

# File Storage & Media Abstraction
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": os.environ.get("DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage"),
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not DEBUG else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Static Files Configuration
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Flexible Static Asset Directory Resolution (Local OS & Container compatibility)
_frontend_static_candidates = [
    BASE_DIR / "frontend" / "static",
    BASE_DIR.parent / "frontend" / "static",
    Path("/app/frontend/static"),
]
STATICFILES_DIRS = [str(p) for p in _frontend_static_candidates if p.exists()]

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# Encryption key for encrypted fields
_field_key = os.environ.get("FIELD_ENCRYPTION_KEY")
if not _field_key or len(_field_key) < 43:
    try:
        from cryptography.fernet import Fernet
        _field_key = Fernet.generate_key().decode()
    except Exception:
        _field_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
FIELD_ENCRYPTION_KEY = _field_key

# PHASE-2: Stripe Configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# PHASE-3: AI Configuration
AI_PROVIDER = os.environ.get("AI_PROVIDER", "ollama")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:8b")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4")

# Execution capacity defaults (can be tuned per tenant/workflow)
GLOBAL_EXECUTION_CAPACITY = int(os.environ.get("GLOBAL_EXECUTION_CAPACITY", "100"))
DEFAULT_TENANT_EXECUTION_CAPACITY = int(os.environ.get("DEFAULT_TENANT_EXECUTION_CAPACITY", "50"))
DEFAULT_WORKFLOW_EXECUTION_CAPACITY = int(os.environ.get("DEFAULT_WORKFLOW_EXECUTION_CAPACITY", "10"))
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")

# PHASE-4: Prometheus Metrics
PROMETHEUS_EXPORT_MIGRATIONS = False

# Rate Limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"

# Caching Configuration (Redis in Production, LocMem fallback)
if os.environ.get("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "RETRY_ON_TIMEOUT": True,
                "MAX_CONNECTIONS": 50,
            }
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.db"

# WhiteNoise Static Files Performance Optimization
WHITENOISE_MAX_AGE = int(os.environ.get("WHITENOISE_MAX_AGE", "31536000"))
WHITENOISE_KEEP_ONLY_HASHED_FILES = True

# Error Monitoring with Sentry (if configured)
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN and "your-sentry-dsn" not in SENTRY_DSN and "sentry.io" in SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            sentry_logging,
        ],
        traces_sample_rate=0.1,
        send_default_pii=True
    )

# Performance Monitoring
PERFORMANCE_MONITORING = {
    'SLOW_REQUEST_THRESHOLD': 2.0,  # seconds
    'ENABLE_QUERY_LOGGING': DEBUG,
    'MAX_QUERIES_PER_REQUEST': 50,
}


# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs/django.log",
            "maxBytes": 1024 * 1024 * 10, # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "workflows": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "performance": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Create logs directory
(BASE_DIR / "logs").mkdir(exist_ok=True)

# ================================
# EMAIL CONFIGURATION - STRICT VALIDATION
# ================================

# CRITICAL: NO SILENT FALLBACKS - CRASH FAST if misconfigured
# Default to SMTP backend (requires .env configuration)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

# SMTP Configuration (for non-Gmail addresses only)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").replace(" ", "")

# Default sender email
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or EMAIL_HOST_USER or "noreply@flowzen.ai"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Email timeout settings
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "30"))

# CRITICAL: NEVER allow console backend in production
if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    if not DEBUG:
        raise ImproperlyConfigured(
            "Console email backend is not allowed in production. "
            "Configure proper SMTP settings or Gmail OAuth."
        )

# ================================
# GMAIL OAUTH CONFIGURATION - STRICT VALIDATION
# ================================

# Gmail OAuth settings (Hardcoded for provided credentials)
GMAIL_OAUTH_ENABLED = True
GMAIL_OAUTH_CLIENT_ID = os.environ.get("GMAIL_OAUTH_CLIENT_ID", "your-client-id")
GMAIL_OAUTH_CLIENT_SECRET = os.environ.get("GMAIL_OAUTH_CLIENT_SECRET", "your-client-secret")
GMAIL_OAUTH_REDIRECT_URI = os.environ.get("GMAIL_OAUTH_REDIRECT_URI", f"{SITE_URL}/api/v1/gmail-oauth/callback/")

# Google Calendar OAuth settings
GOOGLE_CALENDAR_REDIRECT_URI = os.environ.get("GOOGLE_CALENDAR_REDIRECT_URI", f"{SITE_URL}/api/v1/google-calendar-oauth/callback/")

# Credentials encryption key (for OAuth tokens)
CREDENTIALS_MASTER_KEY = os.environ.get("CREDENTIALS_MASTER_KEY", "")
if not CREDENTIALS_MASTER_KEY:
    try:
        from cryptography.fernet import Fernet
        CREDENTIALS_MASTER_KEY = Fernet.generate_key().decode()
        print("⚠️  Generated new CREDENTIALS_MASTER_KEY - set this in environment for production")
    except Exception:
        CREDENTIALS_MASTER_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode()

# CRITICAL: STRICT Gmail OAuth validation - NO SILENT FALLBACKS
_gmail_oauth_configured = bool(GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET)

# STRICT VALIDATION: If Gmail OAuth env vars exist, they MUST be valid (skip in dev with placeholder defaults)
if (GMAIL_OAUTH_CLIENT_ID or GMAIL_OAUTH_CLIENT_SECRET) and DEBUG is False:
    if not GMAIL_OAUTH_CLIENT_ID:
        raise ImproperlyConfigured(
            "GMAIL_OAUTH_CLIENT_ID is required when Gmail OAuth is configured. "
            "Set GMAIL_OAUTH_CLIENT_ID environment variable."
        )
    
    if not GMAIL_OAUTH_CLIENT_SECRET:
        raise ImproperlyConfigured(
            "GMAIL_OAUTH_CLIENT_SECRET is required when Gmail OAuth is configured. "
            "Set GMAIL_OAUTH_CLIENT_SECRET environment variable."
        )
    
    # Validate they are not placeholder values
    _invalid_placeholders = [
        "<REAL_GOOGLE_CLIENT_ID>", 
        "<REAL_GOOGLE_CLIENT_SECRET>", 
        "your-client-id", 
        "your-client-secret",
        "placeholder",
        ""
    ]
    
    if GMAIL_OAUTH_CLIENT_ID in _invalid_placeholders:
        raise ImproperlyConfigured(
            f"GMAIL_OAUTH_CLIENT_ID contains placeholder value: {GMAIL_OAUTH_CLIENT_ID}. "
            "Please set a real Google OAuth Client ID."
        )
    
    if GMAIL_OAUTH_CLIENT_SECRET in _invalid_placeholders:
        raise ImproperlyConfigured(
            f"GMAIL_OAUTH_CLIENT_SECRET contains placeholder value. "
            "Please set a real Google OAuth Client Secret."
        )

# STRICT LOGGING: Clear status messages - NO SILENT FALLBACKS
if _gmail_oauth_configured:
    print("[OK] Gmail OAuth configured - Gmail addresses will use OAuth API")
    print(f"[OK] Gmail OAuth Client ID: {GMAIL_OAUTH_CLIENT_ID[:20]}...")
    print(f"[OK] Gmail OAuth Redirect URI: {GMAIL_OAUTH_REDIRECT_URI}")
else:
    print("[ERROR] Gmail OAuth not configured")
    print("[ERROR] Gmail addresses will FAIL - no fallback to SMTP")
    print("[ERROR] Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET to enable Gmail sending")

# CRITICAL: Export Gmail OAuth status for runtime checks
GMAIL_OAUTH_ENABLED = _gmail_oauth_configured
