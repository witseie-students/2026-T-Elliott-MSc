"""
backend/asgi.py  – ASGI entry-point for HTTP *and* WebSocket
────────────────────────────────────────────────────────────
HTTP/HTTPS   ➜ traditional Django views & DRF  
WebSocket    ➜ URL patterns defined in graphrag.routing
"""

import os, django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()                               # load INSTALLED_APPS

# **import AFTER django.setup()** so app registry is ready
from graphrag.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        # normal Django views
        "http": get_asgi_application(),

        # WebSockets
        # later you can wrap URLRouter in AuthMiddlewareStack
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
