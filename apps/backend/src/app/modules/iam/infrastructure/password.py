"""Hasher de contraseñas argon2id (technical-design §14.1).

Envoltorio fino sobre ``argon2-cffi``. ``verify`` nunca lanza: devuelve ``False``
ante contraseña incorrecta o hash malformado. El parámetro de tiempo del
argon2 se deja por defecto (Fase H: hardening de parámetros vía Settings).
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.modules.iam.application.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Hashea y verifica contraseñas con argon2id."""

    def __init__(self) -> None:
        self._hasher = _Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            return self._hasher.verify(hashed, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
