"""phase 4: tags and the task_tags join table

Revision ID: 7f4a0c92d1b3
Revises: 6a0a92d4f637
"""
from alembic import op
import sqlalchemy as sa


revision = "7f4a0c92d1b3"
down_revision = "6a0a92d4f637"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("colour", sa.String(length=7), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="tags_user_name_unique"),
    )
    op.create_table(
        "task_tags",
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("idx_tags_user", "tags", ["user_id"])
    op.create_index("idx_task_tags_tag", "task_tags", ["tag_id"])

    # Align tasks.user_id with the design DDL: deleting a user cascades to
    # their tasks. There is no account-deletion endpoint today, so this is
    # dormant, but it keeps the schema matching Design.md.
    op.drop_constraint("tasks_user_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key(
        "tasks_user_id_fkey", "tasks", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade():
    op.drop_constraint("tasks_user_id_fkey", "tasks", type_="foreignkey")
    op.create_foreign_key("tasks_user_id_fkey", "tasks", "users", ["user_id"], ["id"])
    op.drop_index("idx_task_tags_tag", table_name="task_tags")
    op.drop_index("idx_tags_user", table_name="tags")
    op.drop_table("task_tags")
    op.drop_table("tags")
