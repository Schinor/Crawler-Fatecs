import httpx

from fatecorg_core.domain import StatusColeta, Unidade
from fatecorg_crawler.pipeline import Coletor, carregar_unidades
from fatecorg_crawler.sink import JsonlSink

PAGINA = """<html><body>
  <a href="https://b.net/Grade-C31.pdf">Grade C31 – 2014-2 até atual</a>
  <a href="https://b.net/HORARIO-2026.pdf">Horário de aulas</a>
  <a href="https://dominio-estranho.com/PPC.pdf">PPC espelhado</a>
</body></html>"""

UNIDADE = Unidade.model_validate(
    {
        "slug": "marilia",
        "nome": "Fatec Marília",
        "cidade": "Marília",
        "site_url": "https://fatec.br",
        "plataforma": "wordpress",
        "cursos": [
            {"slug": "alimentos", "nome": "Alimentos", "url": "https://fatec.br/alimentos/"},
            {"slug": "vazio", "nome": "Sem documentos", "url": "https://fatec.br/vazio/"},
        ],
    }
)


def handler(pdf: bytes):
    def responder(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/alimentos/":
            return httpx.Response(200, text=PAGINA, headers={"content-type": "text/html"})
        if req.url.path == "/vazio/":
            return httpx.Response(200, text="<p>nada</p>", headers={"content-type": "text/html"})
        if req.url.host == "b.net":
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        raise AssertionError(f"acesso inesperado: {req.url}")

    return responder


def rodar(settings, fazer_fetcher, pdf: bytes):
    settings.dominios_arquivos = ["b.net"]
    sink = JsonlSink(settings.data_dir)
    with fazer_fetcher(handler(pdf)) as f:
        return Coletor(settings, f, sink).coletar_unidade(UNIDADE), sink


def test_primeira_rodada_guarda_documento_texto_e_jsonl(settings, fazer_fetcher, pdf_com_texto):
    coletas, sink = rodar(settings, fazer_fetcher, pdf_com_texto("Matriz curricular " * 50))
    status = {(c.curso_slug, c.status) for c in coletas}
    assert status == {("alimentos", StatusColeta.NOVO_PPC), ("vazio", StatusColeta.SEM_PPC)}

    (ppc,) = sink.ler_ppcs()
    assert ppc.tipo_documento == "matriz"
    assert ppc.caminho_local == f"ppcs/marilia/alimentos/{ppc.sha256}.pdf"
    assert (settings.data_dir / ppc.caminho_local).exists()
    assert ppc.caminho_texto is not None
    assert "Matriz curricular" in (settings.data_dir / ppc.caminho_texto).read_text()


def test_segunda_rodada_seguida_so_registra_sem_mudanca(settings, fazer_fetcher, pdf_com_texto):
    pdf = pdf_com_texto("Matriz curricular " * 50)
    rodar(settings, fazer_fetcher, pdf)
    coletas, sink = rodar(settings, fazer_fetcher, pdf)
    assert {c.status for c in coletas} == {StatusColeta.SEM_MUDANCA, StatusColeta.SEM_PPC}
    assert len(sink.ler_ppcs()) == 1  # nada duplicado


def test_arquivo_novo_gera_nova_versao(settings, fazer_fetcher, pdf_com_texto):
    rodar(settings, fazer_fetcher, pdf_com_texto("versao 1 " * 80))
    _, sink = rodar(settings, fazer_fetcher, pdf_com_texto("versao 2 " * 80))
    assert len(sink.ler_ppcs()) == 2


def test_seed_real_tem_pompeia_e_marilia():
    unidades = {u.slug: u for u in carregar_unidades()}
    assert set(unidades) == {"pompeia", "marilia"}
    assert len(unidades["pompeia"].cursos) == 3
    assert len(unidades["marilia"].cursos) == 3
