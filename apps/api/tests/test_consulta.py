def test_unidades_com_cursos(cliente):
    (pompeia,) = cliente.get("/unidades").json()
    assert pompeia["slug"] == "pompeia"
    assert [c["slug"] for c in pompeia["cursos"]] == ["ads", "big-data"]


def test_lista_versoes_com_filtro_e_links(cliente, sha):
    (versao,) = cliente.get("/ppcs", params={"unidade": "pompeia", "curso": "ads"}).json()
    assert versao["origem"] == "crawler"
    assert versao["links"] == {
        "arquivo": f"/ppcs/pompeia/ads/{sha}/arquivo",
        "texto": f"/ppcs/pompeia/ads/{sha}/texto",
    }
    assert "caminho_local" not in versao  # chave interna do storage não vaza
    assert cliente.get("/ppcs", params={"curso": "big-data"}).json() == []


def test_parametros_invalidos_sao_recusados(cliente):
    assert cliente.get("/ppcs", params={"limite": 0}).status_code == 422
    assert cliente.get("/ppcs", params={"limite": 201}).status_code == 422
    assert cliente.get("/ppcs", params={"unidade": "../etc"}).status_code == 422
    assert cliente.get("/ppcs/pompeia/ads/nao-e-sha").status_code == 422
    assert cliente.get(f"/ppcs/pompeia/ads/{'b' * 64}").status_code == 404


def test_baixa_arquivo_e_texto(cliente, sha):
    arquivo = cliente.get(f"/ppcs/pompeia/ads/{sha}/arquivo")
    assert arquivo.content == b"%PDF-1.7 teste"
    assert arquivo.headers["content-type"] == "application/pdf"
    assert (
        arquivo.headers["content-disposition"] == f'attachment; filename="ads-ppc-{sha[:12]}.pdf"'
    )
    texto = cliente.get(f"/ppcs/pompeia/ads/{sha}/texto")
    assert texto.text == "texto extraído"


def test_avisos_abertos_para_o_banner(cliente):
    (aviso,) = cliente.get("/avisos", params={"unidade": "pompeia"}).json()
    assert aviso["tipo"] == "drive_bloqueado"
    assert aviso["curso_slug"] == "big-data"
    assert cliente.get("/avisos", params={"curso": "ads"}).json() == []


def test_cors_so_libera_o_front_configurado(cliente):
    def preflight(origem: str):
        return cliente.options(
            "/ppcs", headers={"Origin": origem, "Access-Control-Request-Method": "GET"}
        )

    assert preflight("http://localhost:4200").headers["access-control-allow-origin"] == (
        "http://localhost:4200"
    )
    assert "access-control-allow-origin" not in preflight("https://malicioso.example").headers
