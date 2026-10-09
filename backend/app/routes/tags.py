import re

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import tags
from .auth import login_required
from .tasks import err

tags_bp = Blueprint("tags", __name__, url_prefix="/api/tags")

COLOUR_RE = re.compile(r"^#[0-9a-f]{6}$")


@tags_bp.get("")
@login_required
def get_tags():
    user_tags = db.session.scalars(
        db.select(tags).where(tags.user_id == g.current_user.id).order_by(tags.name, tags.id)
    ).all()
    return jsonify([tag.to_dict() for tag in user_tags]), 200


@tags_bp.post("")
@login_required
def create_tag():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("VALIDATION_ERROR", "A JSON object is required", 400)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return err("VALIDATION_ERROR", "Tag name required", 400)
    name = name.strip()
    if len(name) > 50:
        return err("VALIDATION_ERROR", "Tag name must be 50 characters or fewer", 400)
    colour = data.get("colour")
    if not isinstance(colour, str) or not COLOUR_RE.fullmatch(colour.lower()):
        return err("VALIDATION_ERROR", "colour must be a hex value like #6c8ebf", 400)
    colour = colour.lower()

    tag = tags(user_id=g.current_user.id, name=name, colour=colour)
    try:
        db.session.add(tag)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return err("CONFLICT", "A tag with that name already exists", 409)
    except Exception as exc:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)
    return jsonify(tag.to_dict()), 201


@tags_bp.delete("/<int:tag_id>")
@login_required
def delete_tag(tag_id):
    tag = db.session.scalar(
        db.select(tags).where(tags.id == tag_id, tags.user_id == g.current_user.id)
    )
    if not tag:
        return err("NOT_FOUND", "Tag not found", 404)
    try:
        db.session.delete(tag)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)
    return jsonify({}), 204
