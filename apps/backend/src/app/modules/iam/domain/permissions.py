"""Matriz de permisos por acción (Fase H paso 18, TDD §14.2).

Catálogo de códigos de permiso organizados por categoría y la matriz
rol → permisos que usan tanto ``AccessControlService`` (autorización) como la
persistencia (``iam_permissions``/``iam_role_permissions`` sembradas en la
migración 0012).

Clasificación por rol:
- ``READ_ACTIONS``: solo lectura (viewer): ``*.list``, ``*.view``, ``*.read``,
  ``*.download``, ``*.sessions``, ``*.online`` más lecturas del panel.
- ``PANEL_ACTIONS``: operaciones de ámbito panel (``resource=None``/``panel``):
  gestión de usuarios/API keys/settings y creación global de servidores. Solo
  admin/super_admin global las poseen.
- ``OPERATOR`` = lectura + escritura sobre servidores (todo el catálogo salvo
  las acciones de panel reservadas a admin).
- ``ADMIN``/``SUPER_ADMIN`` = todo el catálogo (y además bypass en ``authorize``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.iam.domain.role import BuiltinRole

# (código, categoría) — fuente del catálogo persistido y de la matriz.
PERMISSION_CODES: tuple[tuple[str, str], ...] = (
    # server
    ("server.list", "server"),
    ("server.view", "server"),
    ("server.status", "server"),
    ("server.status.read", "server"),
    ("server.create", "server"),
    ("server.start", "server"),
    ("server.stop", "server"),
    ("server.restart", "server"),
    ("server.delete", "server"),
    ("server.update", "server"),
    ("server.config.apply", "server"),
    ("server.config.read", "server"),
    ("server.config.update", "server"),
    ("server.version.change", "server"),
    ("server.version.update", "server"),
    ("server.console.read", "server"),
    ("server.console.write", "server"),
    # world
    ("world.list", "world"),
    ("world.view", "world"),
    ("world.create", "world"),
    ("world.import", "world"),
    ("world.export", "world"),
    ("world.duplicate", "world"),
    ("world.activate", "world"),
    ("world.delete", "world"),
    ("world.sync", "world"),
    ("world.update", "world"),
    # backup
    ("backup.list", "backup"),
    ("backup.view", "backup"),
    ("backup.create", "backup"),
    ("backup.restore", "backup"),
    ("backup.delete", "backup"),
    ("backup.validate", "backup"),
    ("backup.prune", "backup"),
    ("backup.download", "backup"),
    # player
    ("player.list", "player"),
    ("player.view", "player"),
    ("player.manage", "player"),
    ("player.sessions", "player"),
    ("player.online", "player"),
    ("player.ban.global", "player"),
    # permission
    ("permission.read", "permission"),
    ("permission.write", "permission"),
    # console
    ("console.view", "console"),
    ("console.command", "console"),
    # template
    ("template.list", "template"),
    ("template.view", "template"),
    ("template.capture", "template"),
    ("template.apply", "template"),
    ("template.delete", "template"),
    # scheduler
    ("task.list", "scheduler"),
    ("task.view", "scheduler"),
    ("task.create", "scheduler"),
    ("task.update", "scheduler"),
    ("task.delete", "scheduler"),
    ("task.run", "scheduler"),
    ("scheduler.task.create", "scheduler"),
    # iam
    ("iam.user.create", "iam"),
    ("iam.user.update", "iam"),
    ("iam.user.delete", "iam"),
    ("iam.user.role.assign", "iam"),
    ("iam.user.membership.assign", "iam"),
    ("iam.role.assign", "iam"),
    ("iam.audit.view", "iam"),
    ("iam.view", "iam"),
    ("iam.manage", "iam"),
    ("iam.apikey.create", "iam"),
    ("iam.apikey.manage", "iam"),
    # settings
    ("settings.view", "settings"),
    ("settings.update", "settings"),
)


@dataclass(frozen=True, slots=True)
class PermissionCode:
    """Código de permiso del catálogo (persistido en ``iam_permissions``)."""

    code: str
    category: str


ALL_PERMISSIONS: frozenset[str] = frozenset(code for code, _ in PERMISSION_CODES)

# Lectura (viewer): list/view/read/download/sessions/online + lecturas panel.
READ_ACTIONS: frozenset[str] = frozenset(
    {
        "server.list",
        "server.view",
        "server.status",
        "server.status.read",
"server.console.read",
        "server.config.read",
        "world.list",
        "world.view",
        "world.export",
        "backup.list",
        "backup.view",
        "backup.download",
        "player.list",
        "player.view",
        "player.sessions",
        "player.online",
        "permission.read",
        "console.view",
        "task.list",
        "task.view",
        "template.list",
        "template.view",
        "settings.view",
        "iam.view",
    }
)

# Acciones de ámbito panel (resource ``None``/``panel``): solo admin/super_admin.
PANEL_ACTIONS: frozenset[str] = frozenset(
    {
        "server.create",
        "player.ban.global",
        "iam.user.create",
        "iam.user.update",
        "iam.user.delete",
        "iam.user.role.assign",
        "iam.user.membership.assign",
        "iam.role.assign",
        "iam.manage",
        "iam.audit.view",
        "iam.apikey.create",
        "iam.apikey.manage",
        "settings.update",
    }
)

# Escritura sobre servidores (operator): todo el catálogo salvo panel-admin.
WRITE_ACTIONS: frozenset[str] = frozenset(
    action for action in ALL_PERMISSIONS if action not in READ_ACTIONS | PANEL_ACTIONS
)

# Matriz rol → permisos. Viewer solo lectura; operator lectura+escritura sobre
# servidores; admin/super_admin el catálogo completo.
ROLE_PERMISSIONS: dict[BuiltinRole, frozenset[str]] = {
    BuiltinRole.SUPER_ADMIN: ALL_PERMISSIONS,
    BuiltinRole.ADMIN: ALL_PERMISSIONS,
    BuiltinRole.OPERATOR: frozenset(READ_ACTIONS | WRITE_ACTIONS),
    BuiltinRole.VIEWER: READ_ACTIONS,
}

# Ids estables para sembrar las tablas (código como PK, mismo criterio que
# ``iam_user_roles`` usa el nombre del rol como clave natural).
PERMISSIONS_SEED: tuple[PermissionCode, ...] = tuple(
    PermissionCode(code=code, category=category) for code, category in PERMISSION_CODES
)


def permission_codes_for(role: BuiltinRole) -> frozenset[str]:
    """Permisos que concede un rol del catálogo base."""
    return ROLE_PERMISSIONS[role]
