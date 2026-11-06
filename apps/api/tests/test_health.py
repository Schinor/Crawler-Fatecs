def test_health(cliente):
    resp = cliente.get("/health")
    assert resp.json() == {"status": "ok"}
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
