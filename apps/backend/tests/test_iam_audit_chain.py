"""Tests de la auditoría tamper-evident (cadena de hash SHA-256, Fase H paso 18).

Verifica que ``prev_hash`` encadena los registros, que el hash depende de los
campos normalizados y que ``verify()`` detecta manipulaciones.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.iam.application.audit_chain import compute_audit_hash, verify_chain
from app.modules.iam.application.ports import AuditEntry
from app.modules.iam.infrastructure.memory import InMemoryAuditStore

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def entry(action: str = "AUTH.LOGIN_SUCCESS", **overrides: object) -> AuditEntry:
    values: dict[str, object] = {
        "id": "a1",
        "actor_id": "u1",
        "actor_type": "user",
        "action": action,
        "result": "success",
        "created_at": NOW,
        "resource_type": "user",
        "resource_id": "u1",
        "detail": {"x": 1},
        "ip": "10.0.0.1",
        "ua": "curl",
    }
    values.update(overrides)
    return AuditEntry(**values)  # type: ignore[arg-type]


class TestHashComputation:
    def test_hash_depende_de_todos_los_campos(self) -> None:
        base = compute_audit_hash("", entry())
        assert compute_audit_hash("", entry(action="AUTH.LOGIN_FAILED")) != base
        assert compute_audit_hash("", entry(result="failure")) != base
        assert compute_audit_hash("", entry(resource_id="u2")) != base
        assert compute_audit_hash("", entry(actor_id="u2")) != base

    def test_hash_no_depende_de_detalle_ip_ua(self) -> None:
        plain = entry(detail={}, ip=None, ua=None)
        verbose = entry(detail={"a": 1}, ip="10.0.0.1", ua="curl")
        assert compute_audit_hash("", plain) == compute_audit_hash("", verbose)

    def test_prev_hash_encadena(self) -> None:
        first = compute_audit_hash("", entry(id="a1"))
        second = compute_audit_hash(first, entry(id="a2"))
        assert first != second
        assert second != compute_audit_hash("", entry(id="a2"))


class TestVerifyChain:
    async def test_cadena_lima_devuelve_vacia(self) -> None:
        store = InMemoryAuditStore()
        for index in range(3):
            await store.record(entry(id=f"a{index}"))
        assert await store.verify() == []

    async def test_hash_manipulado_se_detecta(self) -> None:
        store = InMemoryAuditStore()
        await store.record(entry(id="a1"))
        await store.record(entry(id="a2"))
        _, hash_a2 = store._chain[1]
        store._chain[1] = (store._chain[1][0], "0" * 64)
        assert store._chain[1][1] != hash_a2
        errors = await store.verify()
        assert len(errors) >= 1
        assert "hash no coincide" in errors[0]

    async def test_prev_hash_manipulado_se_detecta(self) -> None:
        store = InMemoryAuditStore()
        await store.record(entry(id="a1"))
        await store.record(entry(id="a2"))
        store._chain[1] = ("0" * 64, store._chain[1][1])
        errors = await store.verify()
        assert len(errors) >= 1
        assert "prev_hash" in errors[0]

    def test_verify_chain_vacia_no_es_error(self) -> None:
        assert verify_chain([], []) == []

    def test_cadena_con_longitud_distinta_detecta(self) -> None:
        errors = verify_chain([entry(id="a1")], [])
        assert errors != []
