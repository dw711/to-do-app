import enum
# pyrefly: ignore [missing-import]
from app import db

class task_status(enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"

class task_priority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class users(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)


class tasks(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(task_status), default=task_status.todo, nullable=False)
    priority = db.Column(db.Enum(task_priority), default=task_priority.medium, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": str(self.status),
            "priority": str(self.priority),
            #due date later
            "position": self.position
        }