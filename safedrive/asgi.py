import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safedrive.settings")

# Initialise Django ASGI application early to populate the app registry
# before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

import rides.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(rides.routing.websocket_urlpatterns))
        ),
    }
)
