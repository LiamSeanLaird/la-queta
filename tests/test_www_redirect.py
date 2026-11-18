"""www.<PUBLIC_BASE_URL host> 301-redirects to the same URL on PUBLIC_BASE_URL."""

import pytest

BASE = "https://la-queta.com"
WWW = {"Host": "www.la-queta.com"}


@pytest.fixture
def base_app(migrated_app):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE
    return migrated_app


@pytest.mark.parametrize(
    "path",
    ["/", "/lessons/ser-vs-estar", "/robots.txt", "/sitemap.xml", "/signin"],
)
def test_www_redirects_to_apex_with_same_path(base_app, migrated_client, path):
    response = migrated_client.get(path, headers=WWW)
    assert response.status_code == 301
    assert response.headers["Location"] == BASE + path


def test_www_redirect_keeps_query_string(base_app, migrated_client):
    response = migrated_client.get("/lessons/ser-vs-estar?tab=practice", headers=WWW)
    assert response.status_code == 301
    assert response.headers["Location"] == BASE + "/lessons/ser-vs-estar?tab=practice"


def test_www_host_match_ignores_case_and_trailing_slash(migrated_app, migrated_client):
    migrated_app.config["PUBLIC_BASE_URL"] = BASE + "/"
    response = migrated_client.get("/", headers={"Host": "WWW.La-Queta.com"})
    assert response.status_code == 301
    assert response.headers["Location"] == BASE + "/"


def test_www_post_keeps_method_with_308(base_app, migrated_client):
    response = migrated_client.post(
        "/api/auth/login", json={"handle": "x"}, headers=WWW
    )
    assert response.status_code == 308
    assert response.headers["Location"] == BASE + "/api/auth/login"


def test_health_is_never_redirected(base_app, migrated_client):
    response = migrated_client.get("/api/health", headers=WWW)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "host", ["la-queta.com", "localhost", "127.0.0.1:8000", "www.example.org"]
)
def test_other_hosts_are_served_directly(base_app, migrated_client, host):
    response = migrated_client.get("/robots.txt", headers={"Host": host})
    assert response.status_code == 200


def test_no_redirect_without_public_base_url(migrated_client):
    response = migrated_client.get("/robots.txt", headers=WWW)
    assert response.status_code == 200
