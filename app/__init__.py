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
    from app.routes.crawl import bp as crawl_bp
    from app.routes.health import bp as health_bp
    from app.routes.pages import bp as pages_bp

    application.register_blueprint(health_bp)
    application.register_blueprint(pages_bp)
    application.register_blueprint(crawl_bp)
    application.register_blueprint(api_auth_bp)
    application.register_blueprint(api_levels_bp)
    application.register_blueprint(api_lessons_bp)
    application.register_blueprint(api_vocab_bp)

    from app.www_redirect import register_www_redirect

    register_www_redirect(application)

    from app.text_filters import keep_affixes

    application.add_template_filter(keep_affixes)

    @application.context_processor
    def inject_shell():
        from flask import current_app
        from urllib.parse import quote
        from app.services.auth import current_user

        email = current_app.config.get("FEEDBACK_EMAIL") or ""
        feedback_href = ""
        if email:
            subject = quote("La Queta feedback")
            feedback_href = f"mailto:{email}?subject={subject}"
        return {
            "current_user": current_user(),
            "feedback_href": feedback_href,
        }

    register_not_found(application)

    return application


def register_not_found(application: Flask) -> None:
    """404s: JSON under /api/, a branded noindex page everywhere else."""
    from flask import jsonify, render_template, request, url_for

    @application.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        brand_href = url_for("pages.index")
        return render_template("not_found.html", brand_href=brand_href), 404


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
