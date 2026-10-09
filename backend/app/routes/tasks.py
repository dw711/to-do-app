from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_
from .. import db
from .auth import login_required
from ..models import tags, tasks, task_status, task_priority
from datetime import datetime, timezone, date

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

@tasks_bp.get("") #Phase 1 get tasks by queries; Phase 5 adds q, tag_id, due_from, due_before
@login_required
def get_tasks():
    user_id = g.current_user.id
    query = db.select(tasks).where(tasks.user_id==user_id)

    status = request.args.get("status", type=str)
    if status:
        try:
            status = task_status(status)
            query = query.where(tasks.status==status)
        except ValueError:
            return err("VALIDATION_ERROR", "Invalid status", 400)

    # Phase 5 — search: case-insensitive substring on title or description.
    q = (request.args.get("q") or "").strip()
    if q:
        query = query.where(
            or_(tasks.title.ilike(f"%{q}%"), tasks.description.ilike(f"%{q}%"))
        )

    # Phase 5 — tag filter: tasks carrying any of the given tag ids.
    try:
        tag_ids = [int(tag) for tag in request.args.getlist("tag_id")]
    except ValueError:
        return err("VALIDATION_ERROR", "tag_id must be an integer", 400)
    if tag_ids:
        query = query.where(tasks.tags.any(tags.id.in_(tag_ids)))

    # Phase 5 — due-date filters (inclusive range over tasks that have a due date).
    due_before = request.args.get("due_before")
    if due_before is not None:
        try:
            due_before = date.fromisoformat(due_before)
        except ValueError:
            return err("VALIDATION_ERROR", "due_before must be a date in YYYY-MM-DD form", 400)
        query = query.where(tasks.due_date.is_not(None), tasks.due_date <= due_before)

    due_from = request.args.get("due_from")
    if due_from is not None:
        try:
            due_from = date.fromisoformat(due_from)
        except ValueError:
            return err("VALIDATION_ERROR", "due_from must be a date in YYYY-MM-DD form", 400)
        query = query.where(tasks.due_date.is_not(None), tasks.due_date >= due_from)

    query = query.order_by(tasks.status, tasks.position, tasks.id)
    tasks_list = db.session.scalars(query).all()
    return jsonify([
        task.to_dict() for task in tasks_list
    ]), 200

@tasks_bp.post("") #Phase 1 add data to databse, need to add other data like dates later
@login_required
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("VALIDATION_ERROR", "A JSON object is required", 400)
    user_id = g.current_user.id

    try:
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return err("VALIDATION_ERROR", "Title required", 400)
        status = parse_enum(task_status, data.get("status", "todo"), "status")
        due_date = data.get("due_date")
        if due_date is not None: #getting dates
            due_date = parse_due_date(due_date)

        priority = parse_enum(task_priority, data.get("priority", "medium"), "priority")
        existing_positions = db.session.scalars(
            db.select(tasks.position).where(
                tasks.user_id == user_id,
                tasks.status == status,
            )
        ).all()
        new_task = tasks(
            user_id=user_id,
            title=title.strip(),
            description=data.get("description", ""),
            status=status,
            position=max(existing_positions, default=-1) + 1,
            due_date=due_date,
            priority=priority
        )
        db.session.add(new_task)
        db.session.commit()
        return jsonify(new_task.to_dict()), 201
    except ValueError as exc:
        db.session.rollback()
        return err("VALIDATION_ERROR", str(exc), 400)
    except Exception as e:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.get("/<int:task_id>") #Phase 1, get task by id
@login_required
def get_task_by_id(task_id):
    task = return_task_by_id(task_id=task_id, user_id=g.current_user.id)
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    return jsonify(task.to_dict()), 200

@tasks_bp.patch("/<int:task_id>")#Phase 1, update task by id
@login_required
def change_card(task_id):
    task = return_task_by_id(task_id=task_id, user_id=g.current_user.id)  # get task first from helper
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("VALIDATION_ERROR", "A JSON object is required", 400)
    try:
        if "title" in data:
            title = data["title"]
            if not isinstance(title, str) or not title.strip():
                return err("VALIDATION_ERROR", "Title required", 400)
            task.title = title.strip()
        if "description" in data:
            description = data["description"]
            if description is not None and not isinstance(description, str):
                db.session.rollback()
                return err("VALIDATION_ERROR", "Description must be text", 400)
            task.description = description
        if "status" in data:
            new_status = parse_enum(task_status, data["status"], "status")
            if new_status != task.status:
                reposition_task(task, new_status, None)
        if "priority" in data:
            new_priority = parse_enum(task_priority, data["priority"], "priority")
            task.priority = new_priority
        if "due_date" in data:
            due_date = data["due_date"]
            if due_date is not None:
                    due_date = parse_due_date(due_date)
            task.due_date = due_date
        db.session.commit()
        return jsonify(task.to_dict()), 200
    except ValueError as exc:
        db.session.rollback()
        return err("VALIDATION_ERROR", str(exc), 400)
    except Exception as e:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.patch("/<int:task_id>/move") #Phase 1, moving. changes status and position
@login_required
def move_task(task_id):
    task = return_task_by_id(task_id=task_id, user_id=g.current_user.id)  # get task first from helper
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("VALIDATION_ERROR", "A JSON object is required", 400)
    try:
        position = data.get("position", task.position)
        if isinstance(position, bool) or not isinstance(position, int) or position < 0:
            return err("VALIDATION_ERROR", "Position must be a non-negative integer", 400)
        new_status = parse_enum(task_status, data.get("status", task.status.value), "status")
        reposition_task(task, new_status, position)
        db.session.commit()
        return jsonify(task.to_dict()), 200
    except ValueError as exc:
        db.session.rollback()
        return err("VALIDATION_ERROR", str(exc), 400)
    except Exception as e:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.put("/<int:task_id>/tags") #Phase 4, replace the tag set on a task
@login_required
def set_task_tags(task_id):
    task = return_task_by_id(task_id=task_id, user_id=g.current_user.id)
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return err("VALIDATION_ERROR", "A JSON object is required", 400)
    tag_ids = data.get("tag_ids")
    if not isinstance(tag_ids, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in tag_ids):
        return err("VALIDATION_ERROR", "tag_ids must be a list of integers", 400)
    if len(set(tag_ids)) != len(tag_ids):
        return err("VALIDATION_ERROR", "tag_ids must not contain duplicates", 400)
    try:
        selected_tags = db.session.scalars(
            db.select(tags).where(tags.id.in_(tag_ids), tags.user_id == g.current_user.id)
        ).all()
        if len(selected_tags) != len(tag_ids):
            return err("NOT_FOUND", "One or more tags were not found", 404)
        # Preserve the order the client sent.
        by_id = {tag.id: tag for tag in selected_tags}
        task.tags = [by_id[tag_id] for tag_id in tag_ids]
        db.session.commit()
        return jsonify(task.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.delete("/<int:task_id>")#Phase 1, delete task by id
@login_required
def delete_task(task_id):
    task = return_task_by_id(task_id=task_id, user_id=g.current_user.id)
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({}), 204
    except Exception as e:
        db.session.rollback()
        return err("INTERNAL_ERROR", "Something went wrong", 500)

def err(code: str, message: str, status: int):
    return jsonify({
        "error": {
            "code": code,
            "message": message
        }
    }), status

def return_task_by_id(task_id, user_id):
    '''
    helper function to return task by id
    '''
    query = db.select(tasks).where(tasks.id == task_id, tasks.user_id == user_id)
    task = db.session.scalar(query)
    return task


def reposition_task(task, new_status, position):
    """Move a task and renumber the affected columns in one transaction."""
    source_status = task.status
    source_tasks = list(db.session.scalars(
        db.select(tasks)
        .where(tasks.user_id == task.user_id, tasks.status == source_status)
        .order_by(tasks.position, tasks.id)
    ).all())
    source_tasks.remove(task)

    if new_status == source_status:
        destination_tasks = source_tasks
    else:
        destination_tasks = list(db.session.scalars(
            db.select(tasks)
            .where(tasks.user_id == task.user_id, tasks.status == new_status)
            .order_by(tasks.position, tasks.id)
        ).all())

    if source_status != new_status:
        task.status = new_status
        task.completed_at = datetime.now(timezone.utc) if new_status == task_status.done else None

    insert_at = len(destination_tasks) if position is None else min(position, len(destination_tasks))
    destination_tasks.insert(insert_at, task)
    for index, item in enumerate(destination_tasks):
        item.position = index
    if source_status != new_status:
        for index, item in enumerate(source_tasks):
            item.position = index


def parse_enum(enum_type, value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"Invalid {field_name}")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}") from exc

def parse_due_date(value):
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("due_date must be YYYY-MM-DD or null")

    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must be a valid YYYY-MM-DD date") from exc

    if parsed.isoformat() != value:
        raise ValueError("due_date must use YYYY-MM-DD")

    return parsed
