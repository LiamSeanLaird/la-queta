from flask import Flask
from sqlalchemy.pool import StaticPool

from app.config import Config
from app.extensions import db, migrate


def create_app(config_overrides: dict | None = None) -> Flask:
    application = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    application.config.from_object(Config)
    if config_overrides:
        application.config.update(config_overrides)

    _configure_sqlite_memory(application)

    db.init_app(application)
    migrate.init_app(application, db)

    # Register model metadata for Alembic (local name must not shadow package `app`).
    import app.models  # noqa: F401

    from app.routes.api_auth import bp as api_auth_bp
    from app.routes.api_lessons import bp as api_lessons_bp
    from app.routes.api_levels import bp as api_levels_bp
    from app.routes.api_vocab import bp as api_vocab_bp
    from app.routes.health import bp as health_bp
    from app.routes.pages import bp as pages_bp

    application.register_blueprint(health_bp)
    application.register_blueprint(pages_bp)
    application.register_blueprint(api_auth_bp)
    application.register_blueprint(api_levels_bp)
    application.register_blueprint(api_lessons_bp)
    application.register_blueprint(api_vocab_bp)

    @application.context_processor
    def inject_current_user():
        from app.services.auth import current_user

        return {"current_user": current_user()}

    return application


def _configure_sqlite_memory(application: Flask) -> None:
    """Share one in-memory SQLite DB across connections (needed for Alembic)."""
    uri = application.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not isinstance(uri, str) or uri != "sqlite:///:memory:":
        return
    application.config.setdefault(
        "SQLALCHEMY_ENGINE_OPTIONS",
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
