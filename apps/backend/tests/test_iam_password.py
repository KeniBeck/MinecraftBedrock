"""Tests del hasher de contraseñas argon2id (technical-design §14.1)."""

from __future__ import annotations

from app.modules.iam.infrastructure.password import Argon2PasswordHasher


class TestArgon2PasswordHasher:
    def setup_method(self) -> None:
        self.hasher = Argon2PasswordHasher()

    def test_hash_roundtrip(self) -> None:
        hashed = self.hasher.hash("s3cret!")
        assert hashed != "s3cret!"
        assert self.hasher.verify("s3cret!", hashed) is True

    def test_hash_es_salado(self) -> None:
        assert self.hasher.hash("same") != self.hasher.hash("same")

    def test_password_incorrecta(self) -> None:
        hashed = self.hasher.hash("correcta")
        assert self.hasher.verify("incorrecta", hashed) is False

    def test_hash_malformado_no_lanza(self) -> None:
        assert self.hasher.verify("cualquiera", "no-es-un-hash") is False
