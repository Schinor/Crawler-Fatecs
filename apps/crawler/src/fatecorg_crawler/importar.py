"""Importa a saída da Fase 1 (`data/`) para o banco e o Garage. Pode rodar mais de uma vez."""

from collections import Counter
from datetime import UTC, datetime

from fatecorg_core.db import sessao
from fatecorg_core.repositories import AvisoRepo, ColetaRepo
from fatecorg_crawler.sink import JsonlSink, RepoSink

TIPOS = {"pdf": "application/pdf", "txt": "text/plain; charset=utf-8"}


def importar(origem: JsonlSink, destino: RepoSink) -> Counter[str]:
    """Versões (com arquivo e texto), coletas mais novas que as do banco e avisos abertos."""
    total: Counter[str] = Counter()

    for ppc in origem.ler_ppcs():
        if destino.sha_conhecido(ppc.unidade_slug, ppc.curso_slug, ppc.sha256):
            total["versoes_ja_no_banco"] += 1
            continue
        for chave in filter(None, [ppc.caminho_local, ppc.caminho_texto]):
            if not origem.arquivos.existe(chave):
                raise FileNotFoundError(f"{chave} está no ppcs.jsonl mas não em data/")
            if not destino.storage.existe(chave):
                tipo = TIPOS.get(chave.rsplit(".", 1)[-1], "application/octet-stream")
                destino.guardar_arquivo(chave, origem.arquivos.ler(chave), tipo)
                total["arquivos_enviados"] += 1
        destino.registrar_ppc(ppc)
        total["versoes_importadas"] += 1

    with sessao(destino.engine) as s:
        repo = ColetaRepo(s)
        ultimas = {c.unidade_slug: repo.ultima_rodada(c.unidade_slug) for c in origem.ler_coletas()}
        for c in origem.ler_coletas():
            ultima = ultimas[c.unidade_slug]
            if ultima is not None and c.iniciada_em <= ultima:
                total["coletas_ja_no_banco"] += 1
                continue
            repo.registrar(c)
            total["coletas_importadas"] += 1

    abertos = origem.avisos_abertos()
    with sessao(destino.engine) as s:
        # Sem cursos lidos: nada é resolvido, só abre (ou renova) os avisos do arquivo
        r = AvisoRepo(s).atualizar(abertos, set(), datetime.now(UTC))
    total["avisos_importados"] = len(r.novos)
    return total
