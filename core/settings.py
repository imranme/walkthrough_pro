# import os
# import sys
# import environ
# from pathlib import Path
# from datetime import timedelta
# from corsheaders.defaults import default_headers

# # ১. Environment Variables Setup
# env = environ.Env(
#     DEBUG=(bool, False)
# )

# # Build paths inside the project
# BASE_DIR = Path(__file__).resolve().parent.parent

# # .env ফাইলটি পড়ার জন্য (Base Directory তে থাকতে হবে)
# environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# # ২. PATH Management (AI এবং Apps এর জন্য)
# sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# # AI ফোল্ডারের জন্য (যাতে বাইরের ai/ ফোল্ডারটি জ্যাঙ্গো চিনতে পারে)
# AI_DIR = os.path.join(BASE_DIR, 'ai')
# if os.path.exists(AI_DIR):
#     sys.path.insert(0, AI_DIR)
#     sys.path.insert(0, os.path.join(AI_DIR, 'app'))

# SECRET_KEY = env('SECRET_KEY', default='django-insecure-default-key')
# DEBUG = env('DEBUG', default=False)
# ALLOWED_HOSTS = ['*']

# # .env থেকে ডেটা পড়া
# ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', 'backend.walkthroughpro.app'])
# CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['https://backend.walkthroughpro.app','https://walkthroughpro.app'])



# INSTALLED_APPS = [
#     'django.contrib.admin',
#     'django.contrib.auth',
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',
#     'django.contrib.messages',
#     'django.contrib.staticfiles',
    
#     # Third Party Apps
#     'django_filters',
#     'rest_framework',
#     'rest_framework_simplejwt',
#     'rest_framework_simplejwt.token_blacklist',
#     'corsheaders',
    

#     # Local Apps
#     'apps.accounts',
#     'apps.observations',
#     'apps.community',
#     'apps.payments',
#     #'apps.ai_engine',
# ]

# # ── REST FRAMEWORK CONFIG ─────────────────────────────────────────────────────
# REST_FRAMEWORK = {
#     'DEFAULT_PERMISSION_CLASSES': [
#         'rest_framework.permissions.IsAuthenticated',
#     ],
#     'DEFAULT_AUTHENTICATION_CLASSES': (
#         'rest_framework_simplejwt.authentication.JWTAuthentication',
#     ),
# }

# # ── JWT CONFIG ───────────────────────────────────────────────────────────────
# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
#     'ROTATE_REFRESH_TOKENS': True,
#     'BLACKLIST_AFTER_ROTATION': True,
#     'AUTH_HEADER_TYPES': ('Bearer',),
# }

# MIDDLEWARE = [
#     'corsheaders.middleware.CorsMiddleware', 
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]

# ROOT_URLCONF = 'core.urls'

# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = 'core.wsgi.application'

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# CORS_ALLOW_HEADERS = list(default_headers) + [
#     "ngrok-skip-browser-warning",
# ]

# AUTH_PASSWORD_VALIDATORS = [
#     {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
#     {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
#     {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
#     {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
# ]

# CORS_ALLOW_ALL_ORIGINS = True
# LANGUAGE_CODE = 'en-us'
# TIME_ZONE = 'Asia/Dhaka'
# USE_I18N = True
# USE_TZ = True

# STATIC_URL = '/static/'
# STATIC_ROOT = BASE_DIR / 'staticfiles'
# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, "media")
# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_USE_SSL = False  # এটি নিশ্চিত করো False আছে

# EMAIL_HOST_USER = env('EMAIL_HOST_USER')
# EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')



# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'django.contrib.sessions.middleware.SessionMiddleware',  # এটি উপরে থাকবে
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware', # সেশন মিডলওয়্যারের নিচে
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]

# STRIPE_SECRET_KEY    = env('STRIPE_SECRET_KEY')
# STRIPE_PRO_PRICE_ID  = env('STRIPE_PRO_PRICE_ID')
# STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
# FRONTEND_URL         = env('FRONTEND_URL')

import os
import sys
import environ
from pathlib import Path
from datetime import timedelta
from corsheaders.defaults import default_headers

# 1. Environment Variables Setup
env = environ.Env(DEBUG=(bool, False))
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# 2. PATH Management
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))
AI_DIR = os.path.join(BASE_DIR, 'ai')
if os.path.exists(AI_DIR):
    sys.path.insert(0, AI_DIR)
    sys.path.insert(0, os.path.join(AI_DIR, 'app'))

# 3. Security
SECRET_KEY = env('SECRET_KEY', default='django-insecure-default-key')
DEBUG = env('DEBUG', default=False)
# settings.py এ গিয়ে এটি সরাসরি লিখুন
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0', '*']
# ALLOWED_HOSTS ঠিক করা হয়েছে যাতে লোকাল এবং প্রোডাকশন দুইটাই কাজ করে
# ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost', 'backend.walkthroughpro.app'])

# 4. Application Definition
INSTALLED_APPS = [
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

# 5. Middleware (ডুপ্লিকেট রিমুভ করা হয়েছে এবং CorsMiddleware সবার উপরে রাখা হয়েছে)
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

ROOT_URLCONF = 'core.urls'

# 6. REST & JWT Config
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# 7. Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# 8. CORS & CSRF
CORS_ALLOW_ALL_ORIGINS = True  # ডেভেলপমেন্টের জন্য এটি সহজ
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=['https://backend.walkthroughpro.app','https://walkthroughpro.app'])
CORS_ALLOW_HEADERS = list(default_headers) + ["ngrok-skip-browser-warning"]

# 9. Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')

# 10. Stripe Settings
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_PRO_PRICE_ID = env('STRIPE_PRO_PRICE_ID')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')
FRONTEND_URL = env('FRONTEND_URL')

# 11. Static & Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

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
WSGI_APPLICATION = 'core.wsgi.application'
TIME_ZONE = 'Asia/Dhaka'
USE_TZ = True