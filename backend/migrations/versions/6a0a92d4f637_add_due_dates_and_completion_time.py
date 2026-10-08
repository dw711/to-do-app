"""add task due dates and completion timestamps

Revision ID: 6a0a92d4f637
Revises: 3b5429632da0
"""
from alembic import op
import sqlalchemy as sa


revision = "6a0a92d4f637"
down_revision = "3b5429632da0"
branch_labels = None
depends_on = None


def upgrade():
    # Priority was added in the phase-2 baseline; normalize legacy rows and
    # provide the database-level default expected by the phase-3 task form.
    op.execute("UPDATE tasks SET priority = 'medium' WHERE priority IS NULL")
    op.alter_column(
        "tasks",
        "priority",
        existing_type=sa.Enum("low", "medium", "high", name="task_priority"),
        server_default="medium",
        nullable=False,
    )
    op.add_column("tasks", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "due_date")
    op.alter_column(
        "tasks",
        "priority",
        existing_type=sa.Enum("low", "medium", "high", name="task_priority"),
        server_default=None,
    )