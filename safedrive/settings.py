"""
Django settings for SafeDrive — a passenger-safety-first ride platform.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(key, default=False):
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = True
<<<<<<< HEAD

# ---- Email (used for 2FA login codes) ----
# Uses Resend's SMTP relay: https://resend.com — sign up free, create an API
# key, set it as EMAIL_HOST_PASSWORD below. No app-password/2FA dance needed.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.resend.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "resend")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "SafeDrive <onboarding@resend.dev>")
# If EMAIL_HOST_PASSWORD is empty, fall back to printing emails to the console
# instead of sending — handy for local dev before you've set up Resend.
if not EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
=======
>>>>>>> 3b4da265b9e6343f66681dd946ef6089191e86dd
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
# Needed for HTTPS POST/CSRF on deployed domains, e.g. https://your-app.vercel.app
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.vercel.app").split(",") if o.strip()
]

INSTALLED_APPS = [
    "daphne",  # must be above staticfiles so runserver uses ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    # Local apps
    "accounts",
    "rides",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "safedrive.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
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

WSGI_APPLICATION = "safedrive.wsgi.application"
ASGI_APPLICATION = "safedrive.asgi.application"

import urllib.parse as _urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    # Postgres (e.g. Neon). SSL is required by Neon; channel_binding in the
    # URL query is ignored here — sslmode=require is sufficient.
    _u = _urlparse.urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _u.path.lstrip("/"),
            "USER": _urlparse.unquote(_u.username or ""),
            "PASSWORD": _urlparse.unquote(_u.password or ""),
            "HOST": _u.hostname or "",
            "PORT": str(_u.port or ""),
            "CONN_MAX_AGE": 600,
            "OPTIONS": {"sslmode": "require"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --- Channels (WebSockets) -------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:redirect_dashboard"
LOGOUT_REDIRECT_URL = "landing"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Vercel serves this directory's contents at /static/ (see vercel.json distDir).
STATIC_ROOT = BASE_DIR / "staticfiles_build" / "static"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Cloudinary media storage -------------------------------------------
# When CLOUDINARY_URL is set, uploaded files (driver documents, images) are
# stored on Cloudinary. Otherwise uploads fall back to the local filesystem.
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
if CLOUDINARY_URL:
    # cloudinary reads CLOUDINARY_URL from the environment automatically.
    INSTALLED_APPS += ["cloudinary", "cloudinary_storage"]
    # RawMediaCloudinaryStorage accepts any file type (PDF scans, images, docs);
    # images are still delivered directly via their Cloudinary URL.
    STORAGES = {
        "default": {"BACKEND": "cloudinary_storage.storage.RawMediaCloudinaryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Safety thresholds (route deviation detection)
ROUTE_DEVIATION_METERS = 500       # distance off planned route to flag
STATIONARY_SECONDS = 180           # how long a vehicle may stay put before warning
STATIONARY_METERS = 40             # movement under this counts as "stationary"

# Production hardening (only applied when DEBUG is off)
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    X_FRAME_OPTIONS = "DENY"
