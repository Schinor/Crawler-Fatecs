"""Avisos: documentos que o crawler achou mas não pôde baixar e que precisam de ação humana.

Hoje o único caso é o Drive de Pompeia, cujo robots.txt proíbe o download direto (`/uc`). O
crawler não contorna o bloqueio: abre um aviso, notifica o responsável na primeira vez que ele
aparece e mantém o aviso em `data/avisos.json` até sumir. Na Fase 2 o front-end mostra esses
avisos (via API). Ver `docs/decisoes.md`.
"""

import json
import smtplib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from pydantic import TypeAdapter
from pydantic_settings import BaseSettings, SettingsConfigDict

from fatecorg_core.domain import Aviso, Coleta, StatusColeta, TipoAviso

MENSAGENS = {
    TipoAviso.DRIVE_BLOQUEADO: (
        "O documento está no Google Drive e o robots.txt do Drive proíbe o download "
        "automático. Carregue o arquivo manualmente ou peça à unidade que o publique no site."
    ),
}

_LISTA = TypeAdapter(list[Aviso])
Chave = tuple[str, str, str]


def _chave(a: Aviso) -> Chave:
    return (a.unidade_slug, a.curso_slug, str(a.arquivo_url))


def avisos_da_rodada(coletas: Iterable[Coleta]) -> list[Aviso]:
    """Converte em avisos as coletas que pedem ação humana."""
    avisos = []
    for c in coletas:
        erro = str(c.detalhe.get("erro") or "")
        if c.status is not StatusColeta.ERRO_DRIVE or "robots" not in erro:
            continue
        avisos.append(
            Aviso.model_validate(
                {
                    "tipo": TipoAviso.DRIVE_BLOQUEADO,
                    "unidade_slug": c.unidade_slug,
                    "curso_slug": c.curso_slug,
                    "curso_nome": c.curso_nome,
                    "tipo_documento": c.detalhe.get("tipo_documento") or "ppc",
                    "pagina_url": c.detalhe["pagina_url"],
                    "arquivo_url": c.detalhe["arquivo_url"],
                    "titulo_link": c.detalhe.get("titulo_link") or "",
                    "mensagem": MENSAGENS[TipoAviso.DRIVE_BLOQUEADO],
                    "detectado_em": c.iniciada_em,
                    "visto_em": c.iniciada_em,
                }
            )
        )
    return avisos


@dataclass
class Atualizacao:
    abertos: list[Aviso]  # todos os avisos abertos depois da rodada
    novos: list[Aviso]  # apareceram nesta rodada: são os que geram notificação
    resolvidos: list[Aviso]  # estavam abertos e não apareceram mais


class AvisoStore:
    """`data/avisos.json`: a lista dos avisos abertos (estado atual, não histórico)."""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.caminho = data_dir / "avisos.json"

    def ler(self) -> list[Aviso]:
        if not self.caminho.exists():
            return []
        return _LISTA.validate_json(self.caminho.read_bytes())

    def atualizar(self, coletas: list[Coleta]) -> Atualizacao:
        """Junta os avisos da rodada aos abertos.

        Um aviso antigo só é fechado se a página do curso foi lida nesta rodada; erro de rede
        ou unidade fora da rodada não conta como "resolvido".
        """
        anteriores = {_chave(a): a for a in self.ler()}
        atuais = {_chave(a): a for a in avisos_da_rodada(coletas)}
        cursos_lidos = {
            (c.unidade_slug, c.curso_slug)
            for c in coletas
            if c.status is not StatusColeta.ERRO_HTTP
        }

        novos, abertos = [], []
        for chave, aviso in atuais.items():
            antigo = anteriores.get(chave)
            if antigo is None:
                novos.append(aviso)
            else:
                aviso = aviso.model_copy(update={"detectado_em": antigo.detectado_em})
            abertos.append(aviso)

        resolvidos = []
        for chave, antigo in anteriores.items():
            if chave in atuais:
                continue
            if (antigo.unidade_slug, antigo.curso_slug) in cursos_lidos:
                resolvidos.append(antigo)
            else:
                abertos.append(antigo)

        abertos.sort(key=_chave)
        self.caminho.write_text(
            json.dumps([a.model_dump(mode="json") for a in abertos], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return Atualizacao(abertos=abertos, novos=novos, resolvidos=resolvidos)


class NotificacaoSettings(BaseSettings):
    """Variáveis `NOTIFICACAO_*` do `.env`. Sem SMTP configurado, o e-mail não é enviado."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="NOTIFICACAO_", extra="ignore")

    destinatarios: str = ""  # separados por vírgula
    remetente: str = ""
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = ""

    @property
    def lista_destinatarios(self) -> list[str]:
        return [d.strip() for d in self.destinatarios.split(",") if d.strip()]

    @property
    def email_configurado(self) -> bool:
        return bool(self.smtp_host and self.lista_destinatarios)


def montar_email(novos: list[Aviso], agora: datetime) -> tuple[str, str]:
    unidades = sorted({a.unidade_slug for a in novos})
    assunto = f"[FatecOrg] {len(novos)} documento(s) precisam de ação ({', '.join(unidades)})"
    linhas = [
        f"Rodada de {agora:%d/%m/%Y %H:%M} UTC. O crawler encontrou documentos que não pode "
        "baixar sozinho:",
        "",
    ]
    for a in novos:
        linhas += [
            f"- {a.unidade_slug} / {a.curso_nome} ({a.tipo_documento}, {a.tipo})",
            f"  {a.titulo_link}".rstrip(),
            f"  arquivo: {a.arquivo_url}",
            f"  página:  {a.pagina_url}",
        ]
    linhas += ["", MENSAGENS[TipoAviso.DRIVE_BLOQUEADO]]
    if len(unidades) > 1:
        linhas += [
            "",
            "Mais de uma unidade tem o mesmo problema: hora de mapear uma solução "
            "(ver docs/decisoes.md).",
        ]
    return assunto, "\n".join(linhas)


def enviar_email(settings: NotificacaoSettings, assunto: str, corpo: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.remetente or settings.smtp_usuario
    msg["To"] = ", ".join(settings.lista_destinatarios)
    msg.set_content(corpo)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=30) as smtp:
        smtp.starttls()
        if settings.smtp_usuario:
            smtp.login(settings.smtp_usuario, settings.smtp_senha)
        smtp.send_message(msg)
