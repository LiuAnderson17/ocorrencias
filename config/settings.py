import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(nome, padrao=None):
    valor = os.environ.get(nome)
    if valor is None or valor == "":
        return padrao
    return valor


def env_bool(nome, padrao=False):
    valor = os.environ.get(nome)
    if valor is None or valor == "":
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "sim"}


SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "Defina DJANGO_SECRET_KEY no arquivo .env (copie .env.example e gere uma chave nova)."
    )
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "painel.apps.PainelConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "painel.context_processors.painel_nav",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Banco da empresa (opcional). O sistema consulta a nota por número; XML é só um atalho.
NOTAS_ORIGEM = env("NOTAS_ORIGEM", "local")  # local | externa | auto
NOTAS_SQL = env("NOTAS_SQL", "")
NOTAS_ITENS_SQL = env("NOTAS_ITENS_SQL", "")
if env("NOTAS_DB_NAME"):
    DATABASES["notas"] = {
        "ENGINE": env("NOTAS_DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": env("NOTAS_DB_NAME"),
        "USER": env("NOTAS_DB_USER", ""),
        "PASSWORD": env("NOTAS_DB_PASSWORD", ""),
        "HOST": env("NOTAS_DB_HOST", "localhost"),
        "PORT": env("NOTAS_DB_PORT", "5432"),
        "OPTIONS": {},
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "painel.Usuario"

LOGIN_URL = "entrar"
LOGIN_REDIRECT_URL = "painel"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "login": "20/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API de ocorrências",
    "DESCRIPTION": (
        "Integração principal: GET /api/notas/{numero}/ devolve cliente, peso, valor, "
        "placa e itens. A origem é configurável (cadastro local hoje; banco da empresa depois). "
        "POST /api/notas/xml/ é opcional, para quando ainda não há vínculo com o ERP."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = [
    origem.strip() for origem in env("DJANGO_CORS_ORIGINS", "").split(",") if origem.strip()
]
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True
