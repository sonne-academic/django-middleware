"""
Django settings for sonne project.

Generated by 'django-admin startproject' using Django 2.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import socket
from pathlib import Path
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECURITY WARNING: don't run with debug turned on in production!
if socket.gethostname() == 'sonne':
    print('running in PRODUCTION mode')
    DEBUG = False
    SECRET_KEY = Path('/srv/http/DJANGO_SECRET').read_text()
    SOLR_HOST = 'http://solr1:8983'
else:
    print('running in DEBUG mode')
    DEBUG = True
    SOLR_HOST = 'http://localhost:8983'
    SECRET_KEY = '$39&prvnp-+)docy$k&ue425%g5e$6$@sv!*_@prtg-^$8v8*i'
ALLOWED_HOSTS = []

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'verbose': {
            # 'format': '[{levelname}-{asctime}][{module}][{process:d}-{thread:d}] {message}',
            'format': '[{levelname:5s}][{asctime}][{module}.{name}][{funcName}] {message}',
            'style': '{',
        },
        'shorter': {
            # 'format': '[{levelname}-{asctime}][{module}][{process:d}-{thread:d}] {message}',
            'format': '[{levelname:5s}][{asctime}][{module}][{funcName}] {message}',
            'style': '{',
        },
    },
    'handlers': {
        'stdout': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'stderr': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'shorter': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'shorter',
        },
    },
    'loggers': {
        # 'JsonRpcSolrPassthrough': {
        #     'handlers': ['stdout'],
        #     'level': 'INFO',
        #     'propagate': True,
        # },
        'channels_zeromq': {
            'handlers': ['stdout','stderr'],
            'level': 'INFO',
            'propagate': False,
        },
        'solr_channel': {
            'handlers': ['shorter'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_zeromq.core.ZeroMqGroupLayer',
        'CONFIG': {
            "capacity": 2,
            "channel_capacity": 1000,
        },
    },
}


# Application definition

INSTALLED_APPS = [
    'channels',
    'solr_channel',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
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

ROOT_URLCONF = 'sonne.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'sonne.wsgi.application'
ASGI_APPLICATION = 'sonne.routing.application'

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = '/static/'
