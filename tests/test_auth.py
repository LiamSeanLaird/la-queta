"""Phase 2 — handle auth + cookie session."""

from __future__ import annotations


def test_register_creates_user_and_sets_session(migrated_client):
    response = migrated_client.post(
        "/api/auth/register",
        json={"handle": "liam"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["handle"] == "liam"
    assert body["id"] >= 1
    assert body["current_level_id"] is None

    me = migrated_client.get("/api/me")
    assert me.status_code == 200
    assert me.get_json()["handle"] == "liam"


def test_register_rejects_duplicate_handle(migrated_client):
    assert (
        migrated_client.post("/api/auth/register", json={"handle": "liam"}).status_code
        == 201
    )
    # Fresh client so we exercise the uniqueness check, not "already logged in".
    response = migrated_client.post("/api/auth/register", json={"handle": "liam"})
    assert response.status_code == 409
    assert response.get_json() == {"error": "Handle already taken"}


def test_register_rejects_invalid_handle(migrated_client):
    response = migrated_client.post("/api/auth/register", json={"handle": "ab"})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_me_requires_session(migrated_client):
    response = migrated_client.get("/api/me")
    assert response.status_code == 401
    assert response.get_json() == {"error": "Not authenticated"}


def test_me_returns_current_user_after_register(migrated_client):
    migrated_client.post("/api/auth/register", json={"handle": "queta"})
    response = migrated_client.get("/api/me")
    assert response.status_code == 200
    body = response.get_json()
    assert body["handle"] == "queta"
    assert body["current_level_id"] is None
