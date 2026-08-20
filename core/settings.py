import os
from pathlib import Path
from datetime import timedelta
import dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
dotenv.load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production-12345')

DEBUG = int(os.environ.get('DEBUG', 1)) == 1

# Parse ALLOWED_HOSTS from env (comma-separated), default to '*'
raw_hosts = os.environ.get('ALLOWED_HOSTS', '*')
if raw_hosts == '*':
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(',') if host.strip()]

USE_POSTGIS = os.environ.get('USE_POSTGIS', '0') == '1'


# Application definition
INSTALLED_APPS = []

try:
    import daphne
    INSTALLED_APPS.append('daphne')
except ImportError:
    pass

INSTALLED_APPS += [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]


if USE_POSTGIS:
    INSTALLED_APPS.append('django.contrib.gis')

INSTALLED_APPS += [
    # Third-party packages
    'rest_framework',
    'corsheaders',
    'channels',
    'drf_spectacular',

    # Custom Platform Apps
    'apps.users',
    'apps.config_params',
    'apps.pricing',
    'apps.orders',
    'apps.logistics',
    'apps.payments',
    'apps.ratings',
    'apps.incidents',
    'apps.notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Database Configuration (MySQL, PostGIS or SQLite by default)
if os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQL_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'delivery'),
            'USER': os.environ.get('MYSQL_USER', 'fcasame'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', 'Cdarfgvn3004!'),
            'HOST': os.environ.get('MYSQL_HOST', '192.168.20.80'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
            }
        }
    }
elif USE_POSTGIS:
    DATABASES = {
        'default': {
            'ENGINE': os.environ.get('DB_ENGINE', 'django.contrib.gis.db.backends.postgis'),
            'NAME': os.environ.get('DB_NAME', 'delivery_db'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# WebSockets Channel Layer Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
if REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [os.environ.get('CHANNEL_LAYERS_REDIS', REDIS_URL)],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Configure Celery Beat Periodic Tasks
CELERY_BEAT_SCHEDULE = {
    'expire-pending-offers-sweeper': {
        'task': 'apps.logistics.tasks.sweep_expired_offers',
        'schedule': 5.0,
    },
}

# Swagger OpenAPI Metadata
SPECTACULAR_SETTINGS = {
    'TITLE': 'Plataforma de Mensajería y Reparto API',
    'DESCRIPTION': 'API REST y WebSockets para plataforma de logística en tiempo real tipo Uber Flash / Rappi Envíos',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

