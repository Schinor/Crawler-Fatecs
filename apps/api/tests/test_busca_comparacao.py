import io
import zipfile

import pymupdf
import pytest

PERFIL = "Perfil do egresso: o tecnólogo atua no desenvolvimento de sistemas inteligentes."
ANTES = [PERFIL, "Carga horária total: 2400 horas.", "Estágio supervisionado de 240 horas."]
DEPOIS = [PERFIL, "Carga horária total: 2800 horas.", "Estágio supervisionado de 240 horas."]


def pdf_paragrafos(paragrafos: list[str]) -> bytes:
    doc = pymupdf.open()
    pagina = doc.new_page()
    y = 72
    for p in paragrafos * 8:  # texto suficiente para não cair em "precisa de OCR"
        pagina.insert_textbox(pymupdf.Rect(72, y, 520, y + 40), p)  # type: ignore[attr-defined]
        y += 22
        if y > 780:
            pagina, y = doc.new_page(), 72
    return doc.tobytes()


@pytest.fixture
def duas_versoes(cliente, auth):
    shas = []
    for paragrafos in (ANTES, DEPOIS):
        resp = cliente.post(
            "/ppcs",
            data={"unidade": "pompeia", "curso": "big-data", "tipo_documento": "ppc"},
            files={"arquivo": ("ppc.pdf", pdf_paragrafos(paragrafos))},
            headers=auth,
        )
        assert resp.status_code == 201, resp.text
        shas.append(resp.json()["sha256"])
    return shas


def test_busca_acha_o_texto_do_upload_sem_acento(cliente, duas_versoes):
    resp = cliente.get("/busca", params={"q": "estagio supervisionado"})
    assert resp.status_code == 200
    resultados = resp.json()
    assert {r["versao"]["sha256"] for r in resultados} == set(duas_versoes)
    destaques = [t["texto"] for t in resultados[0]["trechos"] if t["destaque"]]
    assert "Estágio" in destaques


def test_busca_filtra_por_tipo_e_unidade(cliente, duas_versoes):
    assert cliente.get("/busca", params={"q": "estagio", "tipo": "matriz"}).json() == []
    assert cliente.get("/busca", params={"q": "estagio", "unidade": "marilia"}).json() == []
    assert len(cliente.get("/busca", params={"q": "2800 horas"}).json()) == 1


@pytest.mark.parametrize(
    "params",
    [{}, {"q": "a"}, {"q": "x" * 201}, {"q": "ok", "limite": 51}, {"q": "ok", "tipo": "x"}],
)
def test_busca_valida_a_consulta(cliente, params):
    assert cliente.get("/busca", params=params).status_code == 422


def test_comparar_mostra_a_palavra_que_mudou(cliente, duas_versoes):
    de, para = duas_versoes
    resp = cliente.get("/ppcs/pompeia/big-data/comparar", params={"de": de, "para": para})
    assert resp.status_code == 200, resp.text
    r = resp.json()
    assert (r["de"]["sha256"], r["para"]["sha256"]) == (de, para)
    trechos = [t for b in r["blocos"] if b["tipo"] == "alterado" for t in b["trechos"]]
    assert {"tipo": "removido", "texto": "2400"} in trechos
    assert {"tipo": "adicionado", "texto": "2800"} in trechos
    assert r["palavras_removidas"] == r["palavras_adicionadas"] == 8  # 1 palavra × 8 repetições
    assert 0.9 < r["semelhanca"] < 1


def test_comparar_versao_sem_texto_ou_de_outro_curso(cliente, auth, duas_versoes, sha):
    de, _ = duas_versoes
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("ementas.txt", "ementas")
    resp = cliente.post(
        "/ppcs",
        data={"unidade": "pompeia", "curso": "big-data", "tipo_documento": "ementario"},
        files={"arquivo": ("ementas.zip", buffer.getvalue())},
        headers=auth,
    )
    zip_sha = resp.json()["sha256"]
    url = "/ppcs/pompeia/big-data/comparar"
    resp = cliente.get(url, params={"de": de, "para": zip_sha})
    assert resp.status_code == 422
    assert "não tem texto extraído (zip)" in resp.json()["detail"]
    # SHA de outro curso (ads) não vale aqui
    assert cliente.get(url, params={"de": de, "para": sha}).status_code == 404
    assert cliente.get(url, params={"de": "xyz", "para": de}).status_code == 422


def test_a_rota_comparar_nao_e_confundida_com_um_sha(cliente):
    resp = cliente.get("/ppcs/pompeia/ads/comparar")
    assert resp.status_code == 422
    assert {e["loc"][-1] for e in resp.json()["detail"]} == {"de", "para"}
