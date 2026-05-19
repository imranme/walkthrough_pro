import os
import sys
import environ
from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers

# ─────────────────────────────────────────────────────────────
# BASE & ENV
# ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ─────────────────────────────────────────────────────────────
# PATH MANAGEMENT
# ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

AI_DIR = os.path.join(BASE_DIR, 'ai')
if os.path.exists(AI_DIR):
    sys.path.insert(0, AI_DIR)
    sys.path.insert(0, os.path.join(AI_DIR, 'app'))

# ─────────────────────────────────────────────────────────────
# SECURITY
# ─────────────────────────────────────────────────────────────
SECRET_KEY = env(
    'SECRET_KEY',
    default='django-insecure-default-key'
)

DEBUG = env('DEBUG', default=False)

ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=[
        '127.0.0.1',
        'localhost',
        'backend.walkthroughpro.app',
    ]
)

CSRF_TRUSTED_ORIGINS = env.list(
    'CSRF_TRUSTED_ORIGINS',
    default=[
        'https://backend.walkthroughpro.app',
        'https://walkthroughpro.app',
    ]
)

# ─────────────────────────────────────────────────────────────
# APPLICATIONS
# ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    # Django Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party Apps
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Local Apps
    'apps.accounts',
    'apps.observations',
    'apps.community',
    'apps.payments',
]

# ─────────────────────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ─────────────────────────────────────────────────────────────
# URLS & WSGI
# ─────────────────────────────────────────────────────────────
ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'

# ─────────────────────────────────────────────────────────────
# TEMPLATES
# ─────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ─────────────────────────────────────────────────────────────
# REST FRAMEWORK
# ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

# ─────────────────────────────────────────────────────────────
# JWT CONFIG
# ─────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ─────────────────────────────────────────────────────────────
# PASSWORD VALIDATION
# ─────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'
    },
]

# ─────────────────────────────────────────────────────────────
# CORS & CSRF
# ─────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    "https://walkthroughpro.app",
    "https://backend.walkthroughpro.app",
]

CORS_ALLOW_HEADERS = list(default_headers) + [
    "ngrok-skip-browser-warning",
]
ALLOWED_HOSTS = ["*"]
# ─────────────────────────────────────────────────────────────
# INTERNATIONALIZATION
# ─────────────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Dhaka'

USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────
# STATIC & MEDIA
# ─────────────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─────────────────────────────────────────────────────────────
# EMAIL CONFIG
# ─────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587

EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

# ─────────────────────────────────────────────────────────────
# STRIPE CONFIG
# ─────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_PRO_PRICE_ID = env('STRIPE_PRO_PRICE_ID')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')

FRONTEND_URL = env('FRONTEND_URL')

# ─────────────────────────────────────────────────────────────
# SECURITY SETTINGS
# ─────────────────────────────────────────────────────────────
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True