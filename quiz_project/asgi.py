# quiz_project/asgi.py
import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack # Optional, aber gut für Authentifizierung

import quiz_app.routing # Dein Routing für die App

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack( # Optional: Für Benutzer-Authentifizierung über WebSockets
        URLRouter(
            quiz_app.routing.websocket_urlpatterns
        )
    ),
})