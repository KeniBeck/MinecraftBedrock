"""Parsing de expresiones cron (Blueprint §3.9).

Se delega en ``croniter`` (dependencia del proyecto) en lugar de reescribir un
parser: validación y la próxima ocurrencia son el dominio que el módulo
necesita. ``next_after`` devuelve la siguiente ocurrencia **estrictamente**
posterior a ``now`` (timezone-aware, UTC).
"""

from __future__ import annotations

from datetime import datetime

from croniter import croniter
from croniter.croniter import CroniterBadCronError

from app.modules.scheduler.domain.errors import SchedulerValidationError


def next_after(cron: str, now: datetime) -> datetime:
    """Próxima ocurrencia de ``cron`` después de ``now`` (o lanza si es inválida)."""
    try:
        return croniter(cron, now, ret_type=datetime).get_next(datetime)
    except (CroniterBadCronError, ValueError, KeyError) as exc:
        raise SchedulerValidationError(
            "Expresión cron inválida",
            context={"cron": cron},
        ) from exc
