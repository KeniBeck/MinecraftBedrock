"""Implementación de ``IdGeneratorPort`` (UUID; kernel prefiere v7, disponible
en Python 3.14; aquí fallback UUID v4 determinista y sin dependencias)."""

from __future__ import annotations

import uuid


class UuidIdGenerator:
    """Genera identificadores UUID (v4 como fallback portable)."""

    def new_id(self) -> str:
        return str(uuid.uuid4())

    def new_id_bytes(self) -> bytes:
        return uuid.uuid4().bytes
