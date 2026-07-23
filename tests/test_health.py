def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_style_guide_renders(client):
    response = client.get("/style-guide")
    assert response.status_code == 200
    assert b"Style guide" in response.data
    assert b"btn--primary" in response.data
    assert b"flashcard" in response.data
    assert b"senyera-bar" not in response.data
    assert b"--senyera-gold" in response.data
