"""API del módulo Notification: el gateway WebSocket único ``/ws``."""

from app.modules.notification.api.router import router

__all__ = ["router"]
