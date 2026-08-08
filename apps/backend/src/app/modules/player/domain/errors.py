"""Errores del dominio Player (Blueprint §11.1).

Subtipo de las ramas del kernel con códigos ``PLAYER.*``. Viven en el módulo
para que el kernel no conozca dominios (mismo criterio que Server/Console).
"""

from __future__ import annotations

from app.kernel.errors import NotFoundError, ValidationError


class PlayerValidationError(ValidationError):
    """Identidad de jugador o payload inválido (sin ``xuid``/``name``)."""

    code = "PLAYER.INVALID_PAYLOAD"


class PlayerNotFoundError(NotFoundError):
    """El jugador no existe en la caché del panel (``xuid`` desconocido)."""

    code = "PLAYER.NOT_FOUND"


class PlayerBanNotFoundError(NotFoundError):
    """El ban (global o por servidor) no existe en el panel."""

    code = "PLAYER.BAN_NOT_FOUND"
