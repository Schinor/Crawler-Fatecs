"""Orquestra a coleta: página do curso → candidatos → download → dedup por SHA → texto → sink."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import yaml

from fatecorg_core.domain import Coleta, PPCEncontrado, StatusColeta, Unidade
from fatecorg_crawler.config import CrawlerSettings
from fatecorg_crawler.discover import LinkCandidato, encontrar_links_ppc
from fatecorg_crawler.download import ErroDownload, baixar
from fatecorg_crawler.extract import extrair_texto
from fatecorg_crawler.fetch import BloqueadoPorRobots, Fetcher
from fatecorg_crawler.sink import Sink
from fatecorg_crawler.sources import PaginaCurso, adaptador_para

SEEDS = Path(__file__).resolve().parents[2] / "seeds" / "unidades.yaml"


def carregar_unidades(caminho: Path = SEEDS) -> list[Unidade]:
    dados = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    return [Unidade.model_validate(u) for u in dados["unidades"]]


def dominio_permitido(url: str, unidade: Unidade, settings: CrawlerSettings) -> bool:
    host = urlsplit(url).netloc.lower()
    host_unidade = urlsplit(str(unidade.site_url)).netloc.lower()
    return host == host_unidade or host in settings.dominios_arquivos


class Coletor:
    def __init__(
        self,
        settings: CrawlerSettings,
        fetcher: Fetcher,
        sink: Sink,
        *,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.settings = settings
        self.fetcher = fetcher
        self.sink = sink
        self.agora = agora

    def coletar_unidade(self, unidade: Unidade) -> list[Coleta]:
        try:
            paginas = adaptador_para(unidade.plataforma).paginas_de_curso(unidade, self.fetcher)
        except (BloqueadoPorRobots, httpx.HTTPError) as e:
            coleta = Coleta(
                unidade_slug=unidade.slug, curso_slug="-", curso_nome="-",
                iniciada_em=self.agora(), status=StatusColeta.ERRO_HTTP,
                detalhe={"erro": f"home: {e.__class__.__name__}"},
            )  # fmt: skip
            self.sink.registrar_coleta(coleta)
            return [coleta]
        coletas: list[Coleta] = []
        for pagina in paginas:
            coletas.extend(self.coletar_curso(unidade, pagina))
        return coletas

    def coletar_curso(self, unidade: Unidade, pagina: PaginaCurso) -> list[Coleta]:
        iniciada = self.agora()

        def registrar(status: StatusColeta, **detalhe: str | int | bool | None) -> Coleta:
            coleta = Coleta(
                unidade_slug=unidade.slug, curso_slug=pagina.curso_slug,
                curso_nome=pagina.curso_nome, iniciada_em=iniciada, status=status,
                detalhe={"pagina_url": pagina.url, **detalhe},
            )  # fmt: skip
            self.sink.registrar_coleta(coleta)
            return coleta

        try:
            resp = self.fetcher.get(pagina.url, unidade=unidade.slug)
        except BloqueadoPorRobots:
            return [registrar(StatusColeta.ERRO_HTTP, erro="página bloqueada pelo robots.txt")]
        except httpx.HTTPError as e:
            return [registrar(StatusColeta.ERRO_HTTP, erro=e.__class__.__name__)]
        if not resp.ok:
            return [registrar(StatusColeta.ERRO_HTTP, erro=f"HTTP {resp.status}")]

        candidatos = [
            c
            for c in encontrar_links_ppc(resp.texto(), resp.url)
            if dominio_permitido(c.url, unidade, self.settings)
        ]
        if not candidatos:
            return [registrar(StatusColeta.SEM_PPC)]

        coletas = []
        for candidato in candidatos:
            status, detalhe = self._processar_candidato(unidade, pagina, candidato)
            coletas.append(registrar(status, **detalhe))
        return coletas

    def _processar_candidato(
        self, unidade: Unidade, pagina: PaginaCurso, candidato: LinkCandidato
    ) -> tuple[StatusColeta, dict[str, str | int | bool | None]]:
        detalhe: dict[str, str | int | bool | None] = {
            "arquivo_url": candidato.url,
            "tipo_documento": candidato.tipo.value,
            "titulo_link": candidato.texto[:200],
        }
        try:
            arquivo = baixar(candidato, self.fetcher)
        except ErroDownload as e:
            return e.status, {**detalhe, "erro": e.detalhe}

        detalhe["sha256"] = arquivo.sha256
        if self.sink.sha_conhecido(unidade.slug, pagina.curso_slug, arquivo.sha256):
            return StatusColeta.SEM_MUDANCA, detalhe

        # Mesmas chaves que o object storage usará na Fase 2
        chave = f"ppcs/{unidade.slug}/{pagina.curso_slug}/{arquivo.sha256}.{arquivo.formato}"
        caminho = self.settings.data_dir / chave
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(arquivo.conteudo)

        chave_texto, paginas, precisa_ocr = None, None, False
        if arquivo.formato == "pdf":
            texto = extrair_texto(caminho, min_chars=self.settings.min_chars_texto)
            chave_texto = chave.removesuffix(".pdf") + ".txt"
            (self.settings.data_dir / chave_texto).write_text(texto.texto, encoding="utf-8")
            paginas, precisa_ocr = texto.paginas, texto.precisa_ocr

        self.sink.registrar_ppc(
            PPCEncontrado.model_validate(
                {
                    "unidade_slug": unidade.slug,
                    "curso_slug": pagina.curso_slug,
                    "curso_nome": pagina.curso_nome,
                    "tipo_documento": candidato.tipo,
                    "pagina_url": pagina.url,
                    "arquivo_url": candidato.url,
                    "titulo_link": candidato.texto[:200],
                    "formato": arquivo.formato,
                    "sha256": arquivo.sha256,
                    "caminho_local": chave,
                    "caminho_texto": chave_texto,
                    "tamanho_bytes": len(arquivo.conteudo),
                    "paginas": paginas,
                    "precisa_ocr": precisa_ocr,
                    "coletado_em": self.agora(),
                }
            )
        )
        return StatusColeta.NOVO_PPC, {**detalhe, "formato": arquivo.formato}
