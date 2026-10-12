"""Saída do crawler. Fase 1: JSONL em data/. Fase 2: RepoSink (Postgres + Garage), mesma API."""

import json
from pathlib import Path
from typing import Protocol

from fatecorg_core.domain import Coleta, PPCEncontrado


class Sink(Protocol):
    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool: ...
    def registrar_ppc(self, ppc: PPCEncontrado) -> None: ...
    def registrar_coleta(self, coleta: Coleta) -> None: ...


class JsonlSink:
    """data/ppcs.jsonl: uma linha por versão nova. data/coletas.jsonl: uma linha por resultado."""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.ppcs_path = data_dir / "ppcs.jsonl"
        self.coletas_path = data_dir / "coletas.jsonl"
        self._conhecidos: set[tuple[str, str, str]] = {
            (p.unidade_slug, p.curso_slug, p.sha256) for p in self.ler_ppcs()
        }

    def ler_ppcs(self) -> list[PPCEncontrado]:
        return _ler(self.ppcs_path, PPCEncontrado)

    def ler_coletas(self) -> list[Coleta]:
        return _ler(self.coletas_path, Coleta)

    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool:
        return (unidade_slug, curso_slug, sha256) in self._conhecidos

    def registrar_ppc(self, ppc: PPCEncontrado) -> None:
        _anexar(self.ppcs_path, ppc.model_dump_json())
        self._conhecidos.add((ppc.unidade_slug, ppc.curso_slug, ppc.sha256))

    def registrar_coleta(self, coleta: Coleta) -> None:
        _anexar(self.coletas_path, coleta.model_dump_json())


def _anexar(caminho: Path, linha: str) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def _ler[M: (PPCEncontrado, Coleta)](caminho: Path, modelo: type[M]) -> list[M]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return [modelo.model_validate(json.loads(linha)) for linha in f if linha.strip()]
