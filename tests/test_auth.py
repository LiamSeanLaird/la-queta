"""Auth — name + email + password (no email verification)."""

from __future__ import annotations


def test_register_creates_user_and_sets_session(migrated_client):
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["handle"] == "liam"
    assert body["email"] == "liam@example.com"
    assert "password" not in body
    assert "password_hash" not in body

    me = migrated_client.get("/api/me")
    assert me.status_code == 200
    assert me.get_json()["handle"] == "liam"


def test_login_across_sessions(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    with migrated_client.session_transaction() as sess:
        sess.clear()

    bad = migrated_client.post(
        "/api/auth/login",
        json={"email": "liam@example.com", "password": "wrongpass"},
    )
    assert bad.status_code == 401

    ok = migrated_client.post(
        "/api/auth/login",
        json={"email": "liam@example.com", "password": "password1"},
    )
    assert ok.status_code == 200
    assert ok.get_json()["handle"] == "liam"
    assert migrated_client.get("/api/me").status_code == 200


def test_logout_clears_session(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    assert migrated_client.post("/api/auth/logout").status_code == 204
    assert migrated_client.get("/api/me").status_code == 401


def test_register_rejects_duplicate_email(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    with migrated_client.session_transaction() as sess:
        sess.clear()
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "other",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 409
    assert response.get_json() == {"error": "Email already used"}


def test_register_rejects_duplicate_handle(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "a@example.com",
            "password": "password1",
        },
    )
    with migrated_client.session_transaction() as sess:
        sess.clear()
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "Liam",
            "email": "b@example.com",
            "password": "password1",
        },
    )
    assert response.status_code == 409
    assert response.get_json() == {"error": "That name is already taken"}


def test_register_rejects_weak_password(migrated_client):
    response = migrated_client.post(
        "/api/auth/register",
        json={"handle": "liam", "email": "liam@example.com", "password": "short"},
    )
    assert response.status_code == 400


def test_register_rejects_invalid_email(migrated_client):
    response = migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "not-an-email",
            "password": "password1",
        },
    )
    assert response.status_code == 400


def test_me_requires_session(migrated_client):
    response = migrated_client.get("/api/me")
    assert response.status_code == 401


def test_patch_me_updates_handle_and_email(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    response = migrated_client.patch(
        "/api/me",
        json={"handle": "Liam Q", "email": "liam.q@example.com"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["handle"] == "Liam Q"
    assert body["email"] == "liam.q@example.com"
    assert migrated_client.get("/api/me").get_json()["handle"] == "Liam Q"


def test_patch_me_rejects_taken_email(migrated_client):
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "liam",
            "email": "liam@example.com",
            "password": "password1",
        },
    )
    with migrated_client.session_transaction() as sess:
        sess.clear()
    migrated_client.post(
        "/api/auth/register",
        json={
            "handle": "other",
            "email": "other@example.com",
            "password": "password1",
        },
    )
    response = migrated_client.patch(
        "/api/me",
        json={"handle": "other", "email": "liam@example.com"},
    )
    assert response.status_code == 409
    assert response.get_json() == {"error": "Email already used"}
