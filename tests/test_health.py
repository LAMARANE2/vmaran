def test_health_returns_200_and_db_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"db": "ok", "status": "ok"}
