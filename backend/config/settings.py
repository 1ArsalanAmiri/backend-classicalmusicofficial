from pathlib import Path
import environ
from datetime import timedelta
from os import path
from django.urls import reverse_lazy
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration


SITE_URL = "http://localhost"  # در سرور واقعی این را به https://yourdomain.com تغییر دهید

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False),ALLOWED_HOSTS=(list, []),)

environ.Env.read_env(BASE_DIR / '.env')

ZP_MERCHANT_ID = env('ZP_MERCHANT_ID', default='c05db87d-9881-4de4-af7f-d998a00d5e48')

ZP_SANDBOX = env.bool('ZP_SANDBOX', default=False)

SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

FRONTEND_URL = "http://localhost:3000"

BACKEND_URL= "http://localhost/"

ALLOWED_HOSTS = ["*"]


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB'),
        'USER': env('POSTGRES_USER'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        'HOST': env('POSTGRES_HOST'),
        'PORT': env('POSTGRES_PORT'),
    }
}


INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_jalali',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'redis',
    'celery',
    'drf_spectacular',
    "drf_spectacular_sidecar",
    "phonenumber_field",
    'nested_admin',
    "django_admin_inline_paginator",
    "admin_extra_buttons",
    'django_filters',
    'channels',


    #my-apps
    'apps.accounts',
    "apps.common",
    "apps.music",
    "apps.playlists",
    "apps.content",
    "apps.payments",
    "apps.subscriptions",
    "apps.tags",
    "apps.contacts",
    "apps.notifications",
    "apps.profiles",
    "apps.interactions"

]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = path.join(BASE_DIR, 'media')


# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    'DEFAULT_THROTTLE_RATES': {
        'zip_generation': '500/hour',  # هر کاربر نهایتاً 5 درخواست در ساعت
    }
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=500),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}


SPECTACULAR_SETTINGS = {
    "TITLE": "Classical Music API",
    "DESCRIPTION": "API documentation",
    "VERSION": "1.0.0",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
}

# Redis Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'KEY_PREFIX': 'music_platform_prod',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            "CONNECTION_POOL_KWARGS": {"max_connections": 100},
            'IGNORE_EXCEPTIONS': True,
            'COMPRESSOR': 'django_redis.compressors.lz4.Lz4Compressor',
        }
    }
}

# Celery
CELERY_BROKER_URL = 'redis://redis:6379/0'
CELERY_RESULT_BACKEND = 'redis://redis:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Tehran'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True


#AUTH USER MODEL
AUTH_USER_MODEL = "accounts.CustomUser"


#MAXIMUM DJANGO MEMORY DATA SET IN ONE REQUEST (10MB)
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760

#MAXIMUM DATA SIZE (MUST BE SET WITH NGINX)
DATA_UPLOAD_MAX_MEMORY_SIZE = 524288000


CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [("redis", 6379)],
            "capacity": 5000,
        },
    },
}


SENTRY_DSN = env("SENTRY_DSN")

if not DEBUG and SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.2,
        environment="production",
        send_default_pii=True
    )


# HSTS SETTINGS
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True