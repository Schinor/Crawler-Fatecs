from fastapi.testclient import TestClient

from bd_ppcs_api.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
