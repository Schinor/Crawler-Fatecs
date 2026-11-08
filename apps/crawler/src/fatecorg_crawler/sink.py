"""Saída do crawler. Fase 1: JSONL em data/. Fase 2: RepoSink (Postgres + Garage), mesma API."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import Engine

from fatecorg_core.db import sessao
from fatecorg_core.domain import Aviso, Coleta, PPCEncontrado, Unidade
from fatecorg_core.repositories import AvisoRepo, CatalogoRepo, ColetaRepo, VersaoRepo
from fatecorg_core.storage import LocalStorage, Storage
from fatecorg_crawler.avisos import Atualizacao, AvisoStore, avisos_da_rodada, cursos_lidos


class Sink(Protocol):
    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool: ...
    def guardar_arquivo(self, chave: str, conteudo: bytes, content_type: str) -> None: ...
    def registrar_ppc(self, ppc: PPCEncontrado) -> None: ...
    def registrar_coleta(self, coleta: Coleta) -> None: ...
    def atualizar_avisos(self, coletas: list[Coleta]) -> Atualizacao: ...
    def avisos_abertos(self) -> list[Aviso]: ...


class JsonlSink:
    """data/ppcs.jsonl: uma linha por versão nova. data/coletas.jsonl: uma linha por resultado.

    Arquivos em data/ppcs/... e avisos em data/avisos.json.
    """

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.ppcs_path = data_dir / "ppcs.jsonl"
        self.coletas_path = data_dir / "coletas.jsonl"
        self.arquivos = LocalStorage(data_dir)
        self.avisos = AvisoStore(data_dir)
        self._conhecidos: set[tuple[str, str, str]] = {
            (p.unidade_slug, p.curso_slug, p.sha256) for p in self.ler_ppcs()
        }

    def ler_ppcs(self) -> list[PPCEncontrado]:
        return _ler(self.ppcs_path, PPCEncontrado)

    def ler_coletas(self) -> list[Coleta]:
        return _ler(self.coletas_path, Coleta)

    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool:
        return (unidade_slug, curso_slug, sha256) in self._conhecidos

    def guardar_arquivo(self, chave: str, conteudo: bytes, content_type: str) -> None:
        self.arquivos.guardar(chave, conteudo, content_type)

    def registrar_ppc(self, ppc: PPCEncontrado) -> None:
        _anexar(self.ppcs_path, ppc.model_dump_json())
        self._conhecidos.add((ppc.unidade_slug, ppc.curso_slug, ppc.sha256))

    def registrar_coleta(self, coleta: Coleta) -> None:
        _anexar(self.coletas_path, coleta.model_dump_json())

    def atualizar_avisos(self, coletas: list[Coleta]) -> Atualizacao:
        return self.avisos.atualizar(coletas)

    def avisos_abertos(self) -> list[Aviso]:
        return self.avisos.ler()


class RepoSink:
    """Fase 2: metadados no Postgres, arquivos no Garage. Uma transação por operação, para que
    uma falha no meio da rodada não desfaça o que já foi gravado."""

    def __init__(self, engine: Engine, storage: Storage, unidades: list[Unidade]):
        self.engine = engine
        self.storage = storage
        with sessao(engine) as s:
            CatalogoRepo(s).sincronizar(unidades)

    def sha_conhecido(self, unidade_slug: str, curso_slug: str, sha256: str) -> bool:
        with sessao(self.engine) as s:
            return VersaoRepo(s).sha_conhecido(unidade_slug, curso_slug, sha256)

    def guardar_arquivo(self, chave: str, conteudo: bytes, content_type: str) -> None:
        self.storage.guardar(chave, conteudo, content_type)

    def registrar_ppc(self, ppc: PPCEncontrado) -> None:
        with sessao(self.engine) as s:
            VersaoRepo(s).registrar(ppc)

    def registrar_coleta(self, coleta: Coleta) -> None:
        with sessao(self.engine) as s:
            ColetaRepo(s).registrar(coleta)

    def atualizar_avisos(self, coletas: list[Coleta]) -> Atualizacao:
        with sessao(self.engine) as s:
            repo = AvisoRepo(s)
            r = repo.atualizar(avisos_da_rodada(coletas), cursos_lidos(coletas), datetime.now(UTC))
            return Atualizacao(abertos=repo.abertos(), novos=r.novos, resolvidos=r.resolvidos)

    def avisos_abertos(self) -> list[Aviso]:
        with sessao(self.engine) as s:
            return AvisoRepo(s).abertos()


def _anexar(caminho: Path, linha: str) -> None:
    with caminho.open("a", encoding="utf-8") as f:
        f.write(linha + "\n")


def _ler[M: (PPCEncontrado, Coleta)](caminho: Path, modelo: type[M]) -> list[M]:
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        return [modelo.model_validate(json.loads(linha)) for linha in f if linha.strip()]
