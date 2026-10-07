from functools import wraps

import jwt
from flask import Blueprint, g, jsonify, request
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from .. import create_token, db, decode_token
from ..models import users

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def error(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def login_required(view):
    """Reject requests without a valid token and expose the user via g."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("UNAUTHORIZED", "Authentication required", 401)
        try:
            payload = decode_token(header[7:])
            user_id = int(payload["sub"])
        except (ValueError, KeyError, jwt.InvalidTokenError):
            return error("UNAUTHORIZED", "Authentication required", 401)

        user = db.session.get(users, user_id)
        if user is None:
            return error("UNAUTHORIZED", "Authentication required", 401)
        g.current_user = user
        return view(*args, **kwargs)
    return wrapped


def user_response(user):
    return {"token": create_token(user), "user": user.to_dict()}


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    display_name = str(data.get("display_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    if not display_name or len(display_name) > 100:
        return error("VALIDATION_ERROR", "Display name is required", 400)
    if "@" not in email or len(email) > 255:
        return error("VALIDATION_ERROR", "Enter a valid email address", 400)
    if not isinstance(password, str) or len(password) < 8:
        return error("VALIDATION_ERROR", "Password must be at least 8 characters", 400)
    if db.session.query(users).filter(func.lower(users.email) == email).first():
        return error("CONFLICT", "That email is already registered", 409)

    user = users(
        display_name=display_name,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user_response(user)), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    user = db.session.query(users).filter(func.lower(users.email) == email).first()
    if user is None or not isinstance(password, str) or not check_password_hash(user.password_hash, password):
        return error("UNAUTHORIZED", "Incorrect email or password", 401)
    return jsonify(user_response(user)), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.current_user.to_dict()}), 200