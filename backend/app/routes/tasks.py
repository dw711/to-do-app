from flask import Blueprint, g, jsonify, request
from .. import db
from .auth import login_required
from ..models import tasks, task_status

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

@tasks_bp.get("") #Phase 1 get tasks by queries
@login_required
def get_tasks():
    user_id = g.current_user.id
    status = request.args.get("status", type=str)
    #q = request.args.get("q", type=str) #implement Phase 5. search by content of cards or title
    query = db.select(tasks).where(tasks.user_id==user_id)
    if status:
        try:
            status = task_status(status)
            query = query.where(tasks.status==status)
        except ValueError:
            return err("UNAUTHROISED", "Incorrect Status", 401)
    
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
    source_tasks = db.session.scalars(
        db.select(tasks)
        .where(tasks.user_id == task.user_id, tasks.status == source_status)
        .order_by(tasks.position, tasks.id)
    ).all()
    source_tasks.remove(task)

    if new_status == source_status:
        destination_tasks = source_tasks
    else:
        destination_tasks = db.session.scalars(
            db.select(tasks)
            .where(tasks.user_id == task.user_id, tasks.status == new_status)
            .order_by(tasks.position, tasks.id)
        ).all()

    if source_status != new_status:
        task.status = new_status

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
