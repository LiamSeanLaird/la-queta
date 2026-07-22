from flask import Flask

from app.config import Config


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    from app.routes.health import bp as health_bp
    from app.routes.pages import bp as pages_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)

    return app
