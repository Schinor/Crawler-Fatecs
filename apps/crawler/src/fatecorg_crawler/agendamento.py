"""Coleta agendada (C9): o que acontece quando a rodada semanal falha sem ninguém olhando.

O agendamento em si fica fora do Python: `scripts/agendar.sh` instala um timer do systemd (ou
uma linha no cron) que chama `scripts/coleta-semanal.sh`. Se a rodada termina com erro, o script
chama `fatecorg-crawler notificar-falha`, que manda ao responsável o fim do log por e-mail.

O log vai por e-mail, então antes ele passa por `redigir`: valores secretos do ambiente e do
`.env` e senhas embutidas em URLs viram `***`.
"""

import os
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values

from fatecorg_core.domain import Coleta, StatusColeta

# Código de saída do `run` quando nenhuma página foi lida (sem rede, sites fora do ar)
CODIGO_NADA_LIDO = 2

_NOMES_SECRETOS = ("SENHA", "PASSWORD", "SECRET", "TOKEN", "KEY", "DATABASE_URL")
_URL_COM_SENHA = re.compile(r"(?P<inicio>[a-z][a-z0-9+.-]*://[^:/@\s]+:)[^@\s]+(?P<fim>@)", re.I)
_MIN_CHARS_SEGREDO = 6  # valores curtos (ex.: "ppcs") gerariam *** no meio do texto comum


def nada_lido(coletas: Iterable[Coleta]) -> bool:
    """A rodada não conseguiu ler nenhuma página: tudo terminou em erro HTTP ou de rede."""
    lista = list(coletas)
    return bool(lista) and all(c.status is StatusColeta.ERRO_HTTP for c in lista)


def segredos(ambiente: Mapping[str, str | None]) -> set[str]:
    """Valores das variáveis cujo nome indica segredo (senha, token, chave, URL do banco)."""
    return {
        valor
        for nome, valor in ambiente.items()
        if valor
        and len(valor) >= _MIN_CHARS_SEGREDO
        and any(parte in nome.upper() for parte in _NOMES_SECRETOS)
    }


def segredos_conhecidos(env_file: Path = Path(".env")) -> set[str]:
    arquivo = dotenv_values(env_file) if env_file.exists() else {}
    return segredos(dict(os.environ)) | segredos(arquivo)


def redigir(texto: str, valores_secretos: Iterable[str]) -> str:
    """Troca por `***` os segredos conhecidos e a senha de URLs como `postgresql://u:s@h`."""
    for valor in sorted(valores_secretos, key=len, reverse=True):
        texto = texto.replace(valor, "***")
    return _URL_COM_SENHA.sub(r"\g<inicio>***\g<fim>", texto)


def fim_do_log(caminho: Path, linhas: int = 60) -> str:
    if not caminho.exists():
        return f"(log não encontrado: {caminho})"
    conteudo = caminho.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(conteudo[-linhas:])


def montar_email_falha(
    codigo: int, log: Path, trecho: str, agora: datetime, maquina: str
) -> tuple[str, str]:
    motivo = (
        "nenhuma página foi lida (sem rede ou sites fora do ar)"
        if codigo == CODIGO_NADA_LIDO
        else f"o crawler terminou com o código {codigo}"
    )
    assunto = f"[FatecOrg] Coleta semanal falhou em {maquina}"
    corpo = "\n".join(
        [
            f"A coleta agendada de {agora:%d/%m/%Y %H:%M} falhou: {motivo}.",
            "",
            f"Log completo na máquina {maquina}: {log}",
            "Para repetir à mão: bash scripts/coleta-semanal.sh",
            "",
            "Últimas linhas do log (segredos trocados por ***):",
            "",
            trecho,
        ]
    )
    return assunto, corpo
