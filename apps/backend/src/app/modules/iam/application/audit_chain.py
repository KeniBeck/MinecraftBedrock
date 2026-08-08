"""Cadena de hash tamper-evident del audit log (Fase H paso 18).

Cada registro persiste ``prev_hash`` (hash del registro anterior, global) y
``hash`` = SHA-256 de ``f"{prev_hash}|{id}|{actor_id}|{action}|{resource_id}|"
f"{created_at}|{result}"``. La verificación recorre la cadena y devuelve la
lista de errores (vacía = íntegra).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.modules.iam.application.ports import AuditEntry


def compute_audit_hash(prev_hash: str, entry: AuditEntry) -> str:
    """SHA-256 del registro normalizado (campos fijos, orden determinista)."""
    raw = (
        f"{prev_hash}|{entry.id}|{entry.actor_id}|{entry.action}|"
        f"{entry.resource_id}|{entry.created_at.isoformat()}|{entry.result}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_chain(entries: Sequence[AuditEntry], chain: Sequence[tuple[str, str]]) -> list[str]:
    """Verifica la cadena ``chain`` frente a los registros.

    ``chain`` es una secuencia de ``(prev_hash, hash)`` en orden de inserción.
    Devuelve errores como ``"audit:{i}: {mensaje}"``; vacío = íntegra.
    """
    errors: list[str] = []
    if len(entries) != len(chain):
        errors.append(f"cadena incompleta: {len(chain)} hashes para {len(entries)} registros")
    expected_prev = ""
    for index, (prev_hash, entry_hash) in enumerate(chain):
        if prev_hash != expected_prev:
            errors.append(f"audit:{index}: prev_hash no coincide con el hash anterior")
        entry = entries[index]
        recomputed = compute_audit_hash(prev_hash, entry)
        if recomputed != entry_hash:
            errors.append(f"audit:{index}: hash no coincide con el registro")
        expected_prev = entry_hash
    return errors
