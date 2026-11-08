"""Criptografia do login: hash de senha (Argon2), token de acesso (JWT) e refresh token (opaco)."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from fatecorg_api.config import ApiSettings
from fatecorg_core.domain import Perfil, Usuario

ALGORITMO = "HS256"
SENHA_MINIMA = 12
PERFIS_DE_ENVIO = frozenset({Perfil.COORDENADOR, Perfil.ADMIN_POLO})

_hasher = PasswordHasher()


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def senha_confere(senha_hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False


def precisa_novo_hash(senha_hash: str) -> bool:
    return _hasher.check_needs_rehash(senha_hash)


@lru_cache(maxsize=1)
def _hash_falso() -> str:
    return gerar_hash(secrets.token_urlsafe(32))


def gastar_tempo_de_verificacao(senha: str) -> None:
    """E-mail inexistente ou conta bloqueada levam o mesmo tempo de uma senha errada."""
    senha_confere(_hash_falso(), senha)


@dataclass(frozen=True)
class Acesso:
    usuario_id: int
    perfil: Perfil


def emitir_acesso(settings: ApiSettings, usuario: Usuario, agora: datetime) -> str:
    return jwt.encode(
        {
            "sub": str(usuario.id),
            "perfil": usuario.perfil.value,
            "tipo": "acesso",
            "iat": agora,
            "exp": agora + timedelta(minutes=settings.jwt_minutos),
        },
        settings.jwt_segredo,
        algorithm=ALGORITMO,
    )


def ler_acesso(settings: ApiSettings, token: str) -> Acesso | None:
    """Confere assinatura e validade. Não vai ao banco: o middleware usa antes de ler o corpo."""
    if not settings.jwt_segredo:
        return None
    try:
        dados = jwt.decode(
            token,
            settings.jwt_segredo,
            algorithms=[ALGORITMO],
            options={"require": ["exp", "iat", "sub"]},
        )
        if dados.get("tipo") != "acesso":
            return None
        return Acesso(int(dados["sub"]), Perfil(dados["perfil"]))
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def novo_refresh() -> str:
    return secrets.token_urlsafe(32)


def sha256_do_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
