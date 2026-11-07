"""Comparação entre duas versões de um documento, a partir do texto extraído.

O texto dos PDFs vem com as quebras de linha da página: uma frase justificada pode virar várias
linhas (ou uma palavra por linha). Comparar linha a linha mostraria ruído, e comparar por
parágrafo é grosso demais (num ementário, um "parágrafo" pode ser uma página inteira). A unidade
é a **linha lógica**: as linhas que continuam a frase anterior são juntadas de volta.

- linhas iguais nas duas versões viram blocos `igual`;
- um trecho pouco alterado (poucas linhas, texto parecido) é marcado **palavra a palavra**;
- um trecho reescrito aparece inteiro: o texto antigo como removido e o novo como adicionado.
  Intercalar palavras de textos diferentes deixaria a leitura impossível.
"""

import difflib
import re
from dataclasses import dataclass, field
from typing import Literal

TipoTrecho = Literal["igual", "removido", "adicionado"]

MAX_LINHAS_POR_PALAVRA = 12  # acima disso, o trecho é tratado como reescrito
MIN_SEMELHANCA_POR_PALAVRA = 0.5

_FIM_DE_FRASE = re.compile(r"[.:;!?)]$")
_CONECTIVOS = (",", "-", "–", " e", " de", " da", " do", " das", " dos", " a", " o", " em")
_SIMBOLOS_PDF = re.compile(r"[-•▪●◦]")  # marcadores de lista (fontes de símbolos)


@dataclass(frozen=True)
class TrechoDiff:
    tipo: TipoTrecho
    texto: str


@dataclass(frozen=True)
class Bloco:
    """`igual`: linhas sem mudança (em `trechos`, um só); `alterado`: com trechos marcados."""

    tipo: Literal["igual", "alterado"]
    trechos: list[TrechoDiff]


@dataclass
class Comparacao:
    blocos: list[Bloco] = field(default_factory=list)
    palavras_adicionadas: int = 0
    palavras_removidas: int = 0
    semelhanca: float = 1.0  # 0 a 1, pelas palavras


def _continua(atual: str, proxima: str) -> bool:
    """A próxima linha continua a frase da atual (quebra feita pela largura da página)?"""
    if _FIM_DE_FRASE.search(atual):
        return False
    return proxima[0].islower() or atual.endswith(_CONECTIVOS)


def linhas_logicas(texto: str) -> list[str]:
    linhas: list[str] = []
    for bloco in texto.replace("\r", "").split("\n\n"):
        atual = ""
        for bruta in bloco.split("\n"):
            linha = " ".join(_SIMBOLOS_PDF.sub(" ", bruta).split())
            if not linha:
                continue
            if atual and _continua(atual, linha):
                atual = f"{atual} {linha}"
            else:
                if atual:
                    linhas.append(atual)
                atual = linha
        if atual:
            linhas.append(atual)
    return linhas


def _por_palavra(antes: str, depois: str) -> list[TrechoDiff]:
    a, b = antes.split(), depois.split()
    trechos: list[TrechoDiff] = []
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            trechos.append(TrechoDiff("igual", " ".join(a[i1:i2])))
            continue
        if i2 > i1:
            trechos.append(TrechoDiff("removido", " ".join(a[i1:i2])))
        if j2 > j1:
            trechos.append(TrechoDiff("adicionado", " ".join(b[j1:j2])))
    return trechos


def _trechos_alterados(antes: list[str], depois: list[str]) -> list[TrechoDiff]:
    texto_antes, texto_depois = "\n".join(antes), "\n".join(depois)
    pequeno = max(len(antes), len(depois)) <= MAX_LINHAS_POR_PALAVRA
    if antes and depois and pequeno:
        parecido = difflib.SequenceMatcher(
            a=texto_antes.split(), b=texto_depois.split(), autojunk=False
        ).ratio()
        if parecido >= MIN_SEMELHANCA_POR_PALAVRA:
            return _por_palavra(texto_antes, texto_depois)
    trechos = []
    if antes:
        trechos.append(TrechoDiff("removido", texto_antes))
    if depois:
        trechos.append(TrechoDiff("adicionado", texto_depois))
    return trechos


def comparar(antes: str, depois: str) -> Comparacao:
    la, lb = linhas_logicas(antes), linhas_logicas(depois)
    resultado = Comparacao()
    matcher = difflib.SequenceMatcher(a=la, b=lb, autojunk=False)
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            resultado.blocos.append(Bloco("igual", [TrechoDiff("igual", "\n".join(la[i1:i2]))]))
        else:
            resultado.blocos.append(Bloco("alterado", _trechos_alterados(la[i1:i2], lb[j1:j2])))

    contagem = {"igual": 0, "removido": 0, "adicionado": 0}
    for bloco in resultado.blocos:
        for t in bloco.trechos:
            contagem[t.tipo] += len(t.texto.split())
    resultado.palavras_removidas = contagem["removido"]
    resultado.palavras_adicionadas = contagem["adicionado"]
    total = 2 * contagem["igual"] + contagem["removido"] + contagem["adicionado"]
    resultado.semelhanca = round(2 * contagem["igual"] / total, 4) if total else 1.0
    return resultado
