"""Regressões dos achados do pentest (docs/seguranca.md)."""

from botocore.exceptions import EndpointConnectionError


class CorpoNaoLido:
    """Corpo que falha se alguém tentar ler: prova que o 401 sai antes do upload."""

    def __iter__(self):
        raise AssertionError("o servidor leu o corpo antes de conferir o token")


def test_a1_upload_sem_token_e_recusado_antes_de_ler_o_corpo(cliente):
    resp = cliente.post(
        "/ppcs",
        content=CorpoNaoLido(),
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "300000000"},
    )
    assert resp.status_code == 401


def test_a1_content_length_acima_do_limite_e_recusado_antes_de_ler(cliente, auth):
    resp = cliente.post(
        "/ppcs",
        content=CorpoNaoLido(),
        headers={
            **auth,
            "Content-Type": "multipart/form-data; boundary=x",
            "Content-Length": str(60 * 1024 * 1024),
        },
    )
    assert resp.status_code == 413


def test_a2_deslocamento_gigante_e_recusado_na_validacao(cliente):
    assert cliente.get("/ppcs", params={"deslocamento": 10**21}).status_code == 422


def test_a3_storage_fora_do_ar_vira_503_sem_detalhes(cliente, storage, sha, monkeypatch):
    def falhar(chave):
        raise EndpointConnectionError(endpoint_url="http://garage-interno:3900")

    monkeypatch.setattr(storage, "existe", falhar)
    resp = cliente.get(f"/ppcs/pompeia/ads/{sha}/arquivo")
    assert resp.status_code == 503
    assert "garage-interno" not in resp.text


def test_a5_docs_podem_ser_desligados(fazer_cliente):
    cliente = fazer_cliente(docs=False)
    assert cliente.get("/docs").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
