"""Contas de acesso e sessões de login. Hashes entram prontos: o core não conhece a criptografia."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from fatecorg_core.db import SessaoLoginDB, UnidadeDB, UsuarioDB
from fatecorg_core.domain import Perfil, Usuario

MAX_FALHAS = 5
TEMPO_BLOQUEIO = timedelta(minutes=15)
# Duas abas renovando juntas apresentam o mesmo token: não é roubo se foi há instantes
CARENCIA_GIRO = timedelta(seconds=10)


class EmailJaCadastrado(ValueError):
    pass


class UnidadeObrigatoria(ValueError):
    pass


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def _utc(momento: datetime) -> datetime:
    """O SQLite (testes) não guarda o fuso; o Postgres devolve em UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


@dataclass
class Credenciais:
    usuario: Usuario
    senha_hash: str
    bloqueado: bool


def _para_usuario(u: UsuarioDB) -> Usuario:
    return Usuario(
        id=u.id,
        email=u.email,
        nome=u.nome,
        perfil=u.perfil,
        unidade_slug=u.unidade.slug if u.unidade else None,
        ativo=u.ativo,
    )


class UsuarioRepo:
    def __init__(self, s: Session):
        self.s = s

    def _por_email(self, email: str) -> UsuarioDB | None:
        q = (
            select(UsuarioDB)
            .options(joinedload(UsuarioDB.unidade))
            .where(UsuarioDB.email == normalizar_email(email))
        )
        return self.s.scalar(q)

    def criar(
        self,
        email: str,
        nome: str,
        senha_hash: str,
        perfil: Perfil,
        unidade_slug: str | None = None,
    ) -> Usuario:
        if self._por_email(email) is not None:
            raise EmailJaCadastrado(email)
        if perfil is Perfil.COORDENADOR and not unidade_slug:
            raise UnidadeObrigatoria("coordenador precisa de uma unidade")
        unidade = None
        if unidade_slug:
            unidade = self.s.scalar(select(UnidadeDB).where(UnidadeDB.slug == unidade_slug))
            if unidade is None:
                raise LookupError(f"unidade '{unidade_slug}' não está no banco")
        db = UsuarioDB(
            email=normalizar_email(email),
            nome=nome,
            senha_hash=senha_hash,
            perfil=perfil,
            unidade=unidade,
            ativo=True,
            falhas_login=0,
        )
        self.s.add(db)
        self.s.flush()
        return _para_usuario(db)

    def por_id(self, usuario_id: int) -> Usuario | None:
        db = self.s.get(UsuarioDB, usuario_id, options=[joinedload(UsuarioDB.unidade)])
        return _para_usuario(db) if db else None

    def credenciais(self, email: str, agora: datetime) -> Credenciais | None:
        db = self._por_email(email)
        if db is None:
            return None
        bloqueado = db.bloqueado_ate is not None and _utc(db.bloqueado_ate) > agora
        return Credenciais(_para_usuario(db), db.senha_hash, bloqueado)

    def registrar_falha(self, usuario_id: int, agora: datetime) -> None:
        """Conta uma senha errada. Na quinta seguida, bloqueia a conta por 15 minutos."""
        db = self.s.get_one(UsuarioDB, usuario_id, with_for_update=True)
        db.falhas_login += 1
        if db.falhas_login >= MAX_FALHAS:
            db.falhas_login = 0
            db.bloqueado_ate = agora + TEMPO_BLOQUEIO
        self.s.flush()

    def registrar_sucesso(self, usuario_id: int, novo_hash: str | None = None) -> None:
        db = self.s.get_one(UsuarioDB, usuario_id, with_for_update=True)
        db.falhas_login, db.bloqueado_ate = 0, None
        if novo_hash:
            db.senha_hash = novo_hash
        self.s.flush()

    def redefinir_senha(self, email: str, senha_hash: str) -> bool:
        """Troca a senha, desbloqueia a conta e encerra todas as sessões abertas."""
        db = self._por_email(email)
        if db is None:
            return False
        db.senha_hash, db.falhas_login, db.bloqueado_ate = senha_hash, 0, None
        SessaoLoginRepo(self.s).encerrar_todas(db.id)
        self.s.flush()
        return True


@dataclass
class Giro:
    usuario_id: int
    girou: bool  # False: outra aba acabou de girar; o cookie novo já está no navegador


class SessaoLoginRepo:
    def __init__(self, s: Session):
        self.s = s

    def _limpar_vencidas(self, usuario_id: int, agora: datetime) -> None:
        self.s.execute(
            delete(SessaoLoginDB).where(
                SessaoLoginDB.usuario_id == usuario_id, SessaoLoginDB.expira_em <= agora
            ),
            execution_options={"synchronize_session": False},  # só linhas que ninguém está usando
        )

    def abrir(self, usuario_id: int, token_sha256: str, agora: datetime, expira_em: datetime):
        self._limpar_vencidas(usuario_id, agora)
        self.s.add(
            SessaoLoginDB(
                usuario_id=usuario_id,
                token_sha256=token_sha256,
                criada_em=agora,
                expira_em=expira_em,
            )
        )
        self.s.flush()

    def girar(
        self, atual_sha256: str, novo_sha256: str, agora: datetime, expira_em: datetime
    ) -> Giro | None:
        """Troca o refresh token. Reapresentar um token já trocado encerra todas as sessões."""
        q = select(SessaoLoginDB).where(SessaoLoginDB.token_sha256 == atual_sha256)
        db = self.s.scalar(q.with_for_update())
        if db is None:
            return None
        if _utc(db.expira_em) <= agora:
            self.s.delete(db)
            self.s.flush()
            return None
        if db.girada_em is not None:
            if agora - _utc(db.girada_em) <= CARENCIA_GIRO:
                return Giro(db.usuario_id, girou=False)
            self.encerrar_todas(db.usuario_id)
            return None
        db.girada_em = agora
        self._limpar_vencidas(db.usuario_id, agora)  # quem nunca reloga também não acumula
        self.s.add(
            SessaoLoginDB(
                usuario_id=db.usuario_id,
                token_sha256=novo_sha256,
                criada_em=agora,
                expira_em=expira_em,
            )
        )
        self.s.flush()
        return Giro(db.usuario_id, girou=True)

    def encerrar(self, token_sha256: str) -> None:
        self.s.execute(delete(SessaoLoginDB).where(SessaoLoginDB.token_sha256 == token_sha256))

    def encerrar_todas(self, usuario_id: int) -> None:
        self.s.execute(delete(SessaoLoginDB).where(SessaoLoginDB.usuario_id == usuario_id))
