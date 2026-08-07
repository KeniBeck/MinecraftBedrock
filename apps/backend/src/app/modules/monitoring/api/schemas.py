"""Serialización de ``StatusSnapshot`` para el envelope WS (Blueprint §13.2).

No hay REST en esta iteración; el payload del evento de transporte
``SERVER.STATE`` se construye aquí (solo presentación, no se publica en el
bus).
"""

from __future__ import annotations

from app.modules.monitoring.application.polling import StatusSnapshot


def status_payload(snapshot: StatusSnapshot) -> dict[str, object]:
    """Payload plano con las métricas y el estado de dominio del snapshot."""
    sample = snapshot.sample
    return {
        "state": snapshot.state.value,
        "status": sample.status.value,
        "latency_ms": sample.latency_ms,
        "players": sample.players_online,
        "players_max": sample.players_max,
        "cpu": sample.cpu,
        "ram_mb": sample.ram_mb,
        "disk_mb": sample.disk_mb,
    }
