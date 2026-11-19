import pytest
from flask_migrate import upgrade

from app import create_app
from app.config import TestConfig


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": TestConfig.TESTING,
            "SQLALCHEMY_DATABASE_URI": TestConfig.SQLALCHEMY_DATABASE_URI,
            # Unset unless a test sets it, so canonical URLs and the www redirect
            # do not depend on the production host or the PUBLIC_BASE_URL env var.
            "PUBLIC_BASE_URL": TestConfig.PUBLIC_BASE_URL,
        }
    )
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def migrated_app(app):
    with app.app_context():
        upgrade()
    yield app


@pytest.fixture
def migrated_client(migrated_app):
    return migrated_app.test_client()
