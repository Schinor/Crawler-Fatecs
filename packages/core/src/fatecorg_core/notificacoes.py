"""E-mails do sistema. Hoje só o responsável recebe (`NOTIFICACAO_DESTINATARIOS`, decisões.md).

Versões novas viram uma linha em `notificacao` na mesma transação do registro: uma falha de SMTP
não perde o aviso, e a próxima rodada (ou o próximo upload) tenta de novo. Vários documentos
saem num e-mail só.
"""

import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine

from fatecorg_core.db import sessao
from fatecorg_core.repositories import NotificacaoRepo, VersaoNotificavel

MAX_VERSOES_POR_EMAIL = 100


class NotificacaoSettings(BaseSettings):
    """Variáveis `NOTIFICACAO_*` do `.env`. Sem SMTP configurado, o e-mail não é enviado."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NOTIFICACAO_", extra="ignore")

    destinatarios: str = ""  # separados por vírgula
    remetente: str = ""
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""
    smtp_tls: bool = True  # false só para o Mailpit do desenvolvimento

    @property
    def lista_destinatarios(self) -> list[str]:
        return [d.strip() for d in self.destinatarios.split(",") if d.strip()]

    @property
    def email_configurado(self) -> bool:
        return bool(self.smtp_host and self.lista_destinatarios)


def enviar_email(settings: NotificacaoSettings, assunto: str, corpo: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.remetente or settings.smtp_usuario
    msg["To"] = ", ".join(settings.lista_destinatarios)
    msg.set_content(corpo)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=30) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_usuario:
            smtp.login(settings.smtp_usuario, settings.smtp_senha)
        smtp.send_message(msg)


def montar_email_versoes(itens: list[VersaoNotificavel]) -> tuple[str, str]:
    unidades = sorted({i.ppc.unidade_slug for i in itens})
    assunto = f"[FatecOrg] {len(itens)} documento(s) atualizado(s) ({', '.join(unidades)})"
    linhas = ["Documentos curriculares com conteúdo novo no FatecOrg:", ""]
    for i in itens:
        p = i.ppc
        origem = str(p.arquivo_url) if p.arquivo_url else "enviado manualmente"
        linhas += [
            f"- {p.unidade_slug} / {p.curso_nome} ({p.tipo_documento})",
            f"  {'Documento novo' if i.documento_novo else 'Nova versão'}"
            f" em {p.coletado_em:%d/%m/%Y %H:%M} UTC",
            f"  {p.titulo_link}".rstrip(),
            f"  origem: {origem}",
        ]
    return assunto, "\n".join(linhas)


@dataclass(frozen=True)
class Despacho:
    enviadas: int = 0
    erro: str | None = None


def despachar_pendentes(engine: Engine, settings: NotificacaoSettings) -> Despacho:
    """Manda num e-mail só as versões pendentes. Duas execuções juntas não repetem o aviso."""
    if not settings.email_configurado:
        return Despacho()
    with sessao(engine) as s:
        repo = NotificacaoRepo(s)
        pendentes = repo.pendentes(MAX_VERSOES_POR_EMAIL)
        if not pendentes:
            return Despacho()
        ids = [p.id for p in pendentes]
        assunto, corpo = montar_email_versoes(pendentes)
        try:
            enviar_email(settings, assunto, corpo)
        except OSError as e:  # smtplib.SMTPException herda de OSError
            erro = e.__class__.__name__  # só o tipo: a mensagem pode trazer dados do servidor
            repo.marcar_erro(ids, erro)
            return Despacho(erro=erro)
        repo.marcar_enviadas(ids, datetime.now(UTC))
        return Despacho(enviadas=len(ids))
