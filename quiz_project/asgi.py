import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack

import quiz_app.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quiz_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            quiz_app.routing.websocket_urlpatterns
        )
    ),
})