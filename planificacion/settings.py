import os
from pathlib import Path
import sys
import pyodbc

# Build paths inside the project like this: BASE_DIR / 'subdir'.
if getattr(sys, 'frozen', False):
    exe_dir = Path(sys.executable).resolve().parent
    if exe_dir.name == '_internal':
        BASE_DIR = exe_dir.parent
    else:
        BASE_DIR = exe_dir
    BUNDLE_DIR = Path(sys._MEIPASS).resolve()
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    BUNDLE_DIR = BASE_DIR

# Soporte dinámico para rutas de PyInstaller de escritorio
if hasattr(sys, '_MEIPASS'):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'planificacion.settings'
    TEMPLATE_DIR = os.path.join(sys._MEIPASS, 'produccion', 'templates')
else:
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'produccion', 'templates')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-523g52y7&sa8p7rjdfgc)ms400)zsqckhb%pv-=yi5d9@2^th='

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'produccion', # Custom app for process planning
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'planificacion.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATE_DIR],
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

WSGI_APPLICATION = 'planificacion.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

drivers_en_sistema = pyodbc.drivers()

# Lista de prioridad de drivers de SQL Server (del más nuevo al más viejo)
drivers_compatibles = [
    'ODBC Driver 18 for SQL Server',
    'ODBC Driver 17 for SQL Server',
    'SQL Server Native Client 11.0',
    'SQL Server'
]

driver_final = 'SQL Server Native Client 11.0' # Por defecto por si falla la detección
for d in drivers_compatibles:
    if d in drivers_en_sistema:
        driver_final = d
        break

params_extra = 'ReadOnly=True'
if 'Driver 18' in driver_final:
    params_extra += ';TrustServerCertificate=yes'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    },
    'production': {
        'ENGINE': 'mssql',
        'NAME': 'EqualRP_Prod_Master',
        'USER': 'tablero',
        'PASSWORD': 'tablero2019',
        'HOST': '192.168.88.12',
        'PORT': '',
        'OPTIONS': {
            'driver': driver_final,
            'extra_params': params_extra,
        },
    }
}

# Database Routers
DATABASE_ROUTERS = ['planificacion.db_routers.ProductionRouter']

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'es-ar'

TIME_ZONE = 'America/Argentina/Buenos_Aires'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BUNDLE_DIR / 'produccion' / 'static',
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# OpenAI Configurations
OPENAI_API_KEY = "sk-yS7ILi6rPssss1tKySVkjcsDhU1InAvw0CrM97JIgWrcFR0GTuALLQQdKvrRCPGU"

# Google AI Studio Configuration
GOOGLE_API_KEY = "AIzaSyCULho2Owbti5yJcgaoc__OtvIX3DVBD4Y"
