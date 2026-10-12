"""Linha de comando do crawler: `uv run fatecorg-crawler --help`."""

import json
import time
from collections import Counter
from datetime import date
from typing import Annotated

import typer

from fatecorg_core.domain import Coleta, StatusColeta, Unidade
from fatecorg_crawler.config import CrawlerSettings
from fatecorg_crawler.discover import encontrar_links_ppc
from fatecorg_crawler.fetch import Fetcher
from fatecorg_crawler.pipeline import Coletor, carregar_unidades
from fatecorg_crawler.sink import JsonlSink
from fatecorg_crawler.sources import adaptador_para

app = typer.Typer(help="Crawler do FatecOrg: coleta os documentos curriculares das Fatecs.")


def _escolher(unidade: str | None, todas: bool) -> list[Unidade]:
    unidades = carregar_unidades()
    if todas:
        return [u for u in unidades if u.ativa]
    escolhidas = [u for u in unidades if u.slug == unidade]
    if not escolhidas:
        slugs = ", ".join(u.slug for u in unidades)
        raise typer.BadParameter(f"unidade '{unidade}' não está no seed ({slugs})")
    return escolhidas


@app.command()
def unidades() -> None:
    """Lista as unidades cadastradas no seed."""
    for u in carregar_unidades():
        typer.echo(f"{u.slug:<20} {u.plataforma:<14} {u.site_url}  ({len(u.cursos)} cursos)")


@app.command()
def inventario(unidade: Annotated[str, typer.Option(help="slug da unidade")]) -> None:
    """Visita as páginas de curso e mostra os documentos candidatos, sem baixar nada."""
    settings = CrawlerSettings()
    (u,) = _escolher(unidade, False)
    with Fetcher(settings) as fetcher:
        for pagina in adaptador_para(u.plataforma).paginas_de_curso(u, fetcher):
            resp = fetcher.get(pagina.url, unidade=u.slug)
            typer.secho(f"\n{pagina.curso_nome}  [{resp.status}] {pagina.url}", bold=True)
            candidatos = encontrar_links_ppc(resp.texto(), resp.url)
            if not candidatos:
                typer.echo("  (nenhum documento curricular encontrado)")
            for c in candidatos:
                typer.echo(f"  {c.tipo:<10} {c.pontos:>3}  {c.origem:<6} {c.texto[:70]}")
                typer.echo(f"  {'':<10} {'':>3}  {'':<6} {c.url}")


@app.command()
def run(
    unidade: Annotated[str | None, typer.Option(help="slug da unidade, ex.: pompeia")] = None,
    todas: Annotated[bool, typer.Option("--todas", help="todas as unidades ativas")] = False,
) -> None:
    """Coleta completa: páginas → documentos → download → versões novas em data/."""
    if not unidade and not todas:
        raise typer.BadParameter("use --unidade <slug> ou --todas")
    settings = CrawlerSettings()
    sink = JsonlSink(settings.data_dir)
    inicio = time.monotonic()
    coletas: list[Coleta] = []
    with Fetcher(settings) as fetcher:
        coletor = Coletor(settings, fetcher, sink)
        for u in _escolher(unidade, todas):
            typer.secho(f"== {u.nome}", bold=True)
            for c in coletor.coletar_unidade(u):
                coletas.append(c)
                extra = c.detalhe.get("tipo_documento") or ""
                erro = c.detalhe.get("erro") or ""
                typer.echo(f"  {c.status:<12} {c.curso_nome[:45]:<45} {extra:<10} {erro}")
    resumo = Counter(c.status.value for c in coletas)
    typer.echo(f"\n{dict(resumo)} em {time.monotonic() - inicio:.0f}s")


@app.command()
def reprocessar(
    data: Annotated[str, typer.Option(help="dia da coleta, AAAA-MM-DD")] = str(date.today()),
) -> None:
    """Roda o parser sobre o HTML salvo em data/raw/<unidade>/<data>/, sem acessar a rede."""
    settings = CrawlerSettings()
    metas = sorted((settings.data_dir / "raw").glob(f"*/{data}/*.meta.json"))
    if not metas:
        typer.echo(f"Nenhum HTML salvo em {data}.")
        raise typer.Exit(1)
    for meta_path in metas:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = meta_path.with_name(meta_path.name.removesuffix(".meta.json") + ".html")
        html = html_path.read_text(encoding="utf-8", errors="replace")
        candidatos = encontrar_links_ppc(html, meta["url_final"])
        typer.secho(f"\n{meta['url']}  ({meta_path.parts[-3]})", bold=True)
        for c in candidatos:
            typer.echo(f"  {c.tipo:<10} {c.pontos:>3}  {c.texto[:70]}")
        if not candidatos:
            typer.echo("  (nenhum documento curricular)")


@app.command()
def relatorio() -> None:
    """Resume data/coletas.jsonl: situação de cada curso na última rodada e versões guardadas."""
    settings = CrawlerSettings()
    sink = JsonlSink(settings.data_dir)
    coletas = sink.ler_coletas()
    if not coletas:
        typer.echo("Nenhuma coleta registrada ainda. Rode: fatecorg-crawler run --todas")
        raise typer.Exit(1)

    ultima: dict[tuple[str, str], list[Coleta]] = {}
    for c in coletas:
        chave = (c.unidade_slug, c.curso_slug)
        if chave not in ultima or c.iniciada_em > ultima[chave][0].iniciada_em:
            ultima[chave] = [c]
        elif c.iniciada_em == ultima[chave][0].iniciada_em:
            ultima[chave].append(c)

    versoes = Counter((p.unidade_slug, p.curso_slug) for p in sink.ler_ppcs())
    com_documento = {StatusColeta.NOVO_PPC, StatusColeta.SEM_MUDANCA}
    cobertos = 0
    for (u_slug, c_slug), lista in sorted(ultima.items()):
        achou = any(c.status in com_documento for c in lista)
        cobertos += achou
        status = ", ".join(sorted({c.status.value for c in lista}))
        cor = typer.colors.GREEN if achou else typer.colors.RED
        nome = lista[0].curso_nome[:50]
        typer.secho(
            f"{u_slug:<10} {nome:<50} {status:<28} {versoes[(u_slug, c_slug)]} versões", fg=cor
        )
    typer.echo(f"\nCobertura: {cobertos}/{len(ultima)} cursos com documento encontrado")


if __name__ == "__main__":
    app()
