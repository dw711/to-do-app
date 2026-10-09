import enum
import datetime

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
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now(datetime.timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class tasks(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(task_status), default=task_status.todo, nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)
    priority = db.Column(db.Enum(task_priority), default=task_priority.medium, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    tags = db.relationship("tags", secondary="task_tags", lazy="selectin")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "status": str(self.status.value),
            "position": self.position,
            "priority": str(self.priority.value),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tags": [tag.to_dict() for tag in self.tags],
        }


class tags(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    colour = db.Column(db.String(7), nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "name"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "colour": self.colour,
        }


class task_tags(db.Model):
    __tablename__ = "task_tags"

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)