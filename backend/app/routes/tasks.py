from multiprocessing.sharedctypes import Value
from flask import Blueprint, jsonify, request
from .. import db
from ..models import tasks, task_status, task_priority, users

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

DEV_USER_ID = 1

@tasks_bp.get("") #Phase 1 get tasks by queries
def get_tasks():
    user_id = DEV_USER_ID #get user id (from auth?) after login is implemented
    status = request.args.get("status", type=str)
    #q = request.args.get("q", type=str) #implement Phase 5. search by content of cards or title
    query = db.select(tasks).where(tasks.user_id==user_id)
    if status:
        try:
            status = task_status(status)
            query = query.where(tasks.status==status)
        except ValueError:
            return err("UNAUTHROISED", "Incorrect Status", 401)
    
    query = query.order_by(tasks.status, tasks.position)
    tasks_list = db.session.scalars(query).all()
    if not tasks_list:
        return err("NOT_FOUND", "Task(s) not found, please change your parameters", 404)
    return jsonify({
        "tasks": [task.to_dict() for task in tasks_list]
    }), 200

@tasks_bp.post("") #Phase 1 add data to databse, need to add other data like dates later
def create_task():
    data = request.get_json(silent=True) or {}
    user_id = DEV_USER_ID #temporary dev user id, change after login system

    print("Content-Type:", request.content_type)
    print("Raw body:", request.get_data(as_text=True))
    if not data.get("title"):
        return err("VALIDATION ERROR", "Title required", 400)
    new_task = tasks(
        user_id=user_id,
        title=data.get("title").strip(),
        description=data.get("description", ""),
        status=task_status[data.get("status", "todo")],
        priority=task_priority[data.get("priority", "medium")],
        position=data.get("position", 0)
    )
    
    try:
        print(new_task)
        db.session.add(new_task)
        db.session.commit()
        return jsonify(new_task.to_dict()), 201
    except ValueError:
        return err("UNAUTHORISED", "Invalid status or priority", 401)
    except Exception as e:
        db.session.rollback()
        print(repr(e))
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.get("/<int:task_id>") #Phase 1, get task by id
def get_task_by_id(task_id):
    user_id = DEV_USER_ID #Change this phase 2
    task = return_task_by_id(task_id=task_id)
    if not task:
        return err("NOT_FOUND", "Task not found", 404)
    return jsonify({"task": task.to_dict()}), 200

@tasks_bp.patch("/<int:task_id>")#Phase 1, update task by id
def change_card(task_id):
    user_id = DEV_USER_ID
    task = return_task_by_id(task_id=task_id) # get task first from helper 
    if not task or task.user_id != user_id: 
        return err("NOT_FOUND", "Task not found", 404)
    data = request.get_json(silent=True) or {}
    #patch after this
    try:
        task.title = data.get("title") or task.title
        task.description = data.get("description") or task.description
        task.priority = task_priority(data.get("priority")or task.priority)
        db.session.commit()
        return jsonify({"task": task.to_dict()}), 200
    except ValueError:
        return err("UNAUTHROISED", "One or more incorrect fields", 401)
    except Exception as e:
        db.session.rollback()
        print(repr(e))
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.patch("/<int:task_id>/move") #Phase 1, moving. changes status and position
def move_task(task_id):
    user_id = DEV_USER_ID
    task = return_task_by_id(task_id=task_id) # get task first from helper
    if not task or task.user_id != user_id: 
        return err("NOT_FOUND", "Task not found", 404)
    data = request.get_json(silent=True) or {}
    #patch after this
    try:
        task.status = task_status(data.get("status", task.status))
        task.position = data.get("position", task.position)
        db.session.commit()
        return jsonify({"task": task.to_dict()}), 200
    except ValueError:
        return err("UNAUTHROISED", "One or more incorrect fields", 401)
    except Exception as e:
        db.session.rollback()
        print(repr(e))
        return err("INTERNAL_ERROR", "Something went wrong", 500)

@tasks_bp.delete("/<int:task_id>")#Phase 1, delete task by id
def delete_task(task_id):
    user_id = DEV_USER_ID #Change this Phase 2
    task = return_task_by_id(task_id=task_id)
    if not task or task.user_id != user_id:
        return err("NOT_FOUND", "Task not found", 404)
    try:
        db.session.delete(task)
        db.session.commit()
        return jsonify({}), 204
    except Exception as e:
        db.session.rollback()
        print(repr(e))
        return err("INTERNAL_ERROR", "Something went wrong", 500)

def err(code: str, message: str, status: int):
    return jsonify({
        "error": {
            "code": code,
            "message": message
        }
    }), status

def return_task_by_id(task_id):
    '''
    helper function to return task by id
    '''
    query = db.select(tasks).where(tasks.id==task_id)
    task = db.session.scalar(query)
    return task
