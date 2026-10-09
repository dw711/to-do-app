from datetime import UTC
import os
from datetime import datetime, timedelta

import jwt
from dotenv import load_dotenv
from flask import Flask, g
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

# Shared database and migration objects for the app factory pattern.
db = SQLAlchemy()
migrate = Migrate()


def create_app():
    """Build the Flask application and register the application blueprints."""
    app = Flask(__name__)
    load_dotenv()

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    app.config["JWT_ALGORITHM"] = os.environ.get("JWT_ALGORITHM", "HS256")
    app.config["JWT_TOKEN_TTL_MINUTES"] = int(os.environ.get("JWT_TOKEN_TTL_MINUTES", "60"))

    db.init_app(app)
    migrate.init_app(app, db)

    # Import the models once so SQLAlchemy can register metadata.
    from . import models
    from .routes.auth import auth_bp
    from .routes.tasks import tasks_bp
    from .routes.tags import tags_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(tags_bp)

    @app.before_request
    def _prepare_request():
        # Current user is used by the login-required decorator.
        g.current_user = None

    return app


def create_token(user):
    """Create a signed JWT for the current authenticated user."""
    from flask import current_app

    payload = {
        "sub": str(user.id),
        "exp": datetime.now(UTC) + timedelta(minutes=current_app.config["JWT_TOKEN_TTL_MINUTES"]),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token):
    """Decode and validate a JWT, raising a runtime error on invalid input."""
    from flask import current_app

    return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=[current_app.config["JWT_ALGORITHM"]])