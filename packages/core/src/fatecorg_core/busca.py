"""Busca no texto dos documentos: trechos destacados e a versão simples usada fora do Postgres.

No Postgres, a busca usa o índice full-text (`websearch_to_tsquery` + `ts_headline`) com a
configuração `fatecorg_pt` (português sem acento, criada na migration 0002). Nos testes em
SQLite e em bancos sem esse índice, `buscar_simples` faz o mesmo papel em Python.

Os trechos saem como dados (`Trecho(texto, destaque)`), nunca como HTML: o front-end monta o
`<mark>` por conta própria (docs/seguranca.md, A-8).
"""

import re
import unicodedata
from dataclasses import dataclass

# Marcadores que o ts_headline põe em volta dos termos achados. Caracteres raros em PPCs;
# se aparecerem no texto original, só deixam de ser destacados.
INICIO, FIM = "⟦", "⟧"  # ⟦ ⟧
OPCOES_HEADLINE = (
    f"StartSel={INICIO}, StopSel={FIM}, MaxFragments=2, MaxWords=30, MinWords=12, "
    'FragmentDelimiter=" … "'
)
_CONTEXTO = 120  # caracteres em volta do termo na busca simples


@dataclass(frozen=True)
class Trecho:
    texto: str
    destaque: bool = False


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def termos(consulta: str) -> list[str]:
    """Palavras da consulta, sem acento. Ignora operadores (`-`, `or`) e palavras de 1 letra."""
    palavras = re.findall(r"\w+", sem_acento(consulta))
    return [p for p in palavras if len(p) > 1 and p != "or"]


def trechos_do_headline(headline: str) -> list[Trecho]:
    """Converte a saída do ts_headline (`...⟦termo⟧...`) em trechos."""
    partes = re.split(f"({re.escape(INICIO)}.*?{re.escape(FIM)})", " ".join(headline.split()))
    trechos = []
    for parte in partes:
        if not parte:
            continue
        if parte.startswith(INICIO) and parte.endswith(FIM):
            trechos.append(Trecho(parte[1:-1], True))
        else:
            trechos.append(Trecho(parte))
    return trechos


def buscar_simples(texto: str, consulta: str) -> tuple[float, list[Trecho]] | None:
    """Todos os termos precisam aparecer (sem acento, sem maiúsculas). Devolve a relevância
    (ocorrências) e um trecho em volta da primeira ocorrência, ou None se não combinar."""
    alvo = termos(consulta)
    if not alvo:
        return None
    plano = " ".join(texto.split())
    normal = sem_acento(plano)
    if not all(t in normal for t in alvo):
        return None
    if len(normal) != len(plano):  # raro (ex.: ligaduras): as posições não batem mais
        plano = normal
    relevancia = float(sum(normal.count(t) for t in alvo))
    primeiro = min(normal.find(t) for t in alvo)
    inicio = max(0, primeiro - _CONTEXTO)
    fim = min(len(plano), primeiro + _CONTEXTO)
    janela, janela_normal = plano[inicio:fim], normal[inicio:fim]

    padrao = re.compile("|".join(re.escape(t) for t in sorted(alvo, key=len, reverse=True)))
    trechos, pos = [], 0
    for m in padrao.finditer(janela_normal):
        if m.start() > pos:
            trechos.append(Trecho(janela[pos : m.start()]))
        trechos.append(Trecho(janela[m.start() : m.end()], True))
        pos = m.end()
    if pos < len(janela):
        trechos.append(Trecho(janela[pos:]))
    if inicio > 0:
        trechos.insert(0, Trecho("… "))
    if fim < len(plano):
        trechos.append(Trecho(" …"))
    return relevancia, trechos
