from main import app


def get_client():
    app.config["TESTING"] = True
    return app.test_client()


def test_health_endpoint_returns_200():
    client = get_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_health_endpoint_returns_ok_status():
    client = get_client()
    response = client.get("/health")
    assert response.get_json()["status"] == "ok"