"""Initial GovDoc schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-19 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rulesource",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("rule_library_entry_id", sa.String(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "extractrun",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rule_source_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("workspace_archive_path", sa.String(), nullable=True),
        sa.Column("workspace_failed_path", sa.String(), nullable=True),
        sa.Column("total_usage_json", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_source_id"], ["rulesource.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tenderdoc",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("markdown_path", sa.String(), nullable=False),
        sa.Column("qmd_collection", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpointdraft",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rule_source_id", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("extract_run_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_source_id"], ["rulesource.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkpointfinal",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auditrun",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("tender_doc_id", sa.String(), nullable=False),
        sa.Column("checkpoint_final_ids", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("workspace_archive_path", sa.String(), nullable=True),
        sa.Column("workspace_failed_path", sa.String(), nullable=True),
        sa.Column("total_usage_json", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["tender_doc_id"], ["tenderdoc.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auditpointrun",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("audit_run_id", sa.String(), nullable=False),
        sa.Column("checkpoint_final_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("workspace_archive_path", sa.String(), nullable=True),
        sa.Column("workspace_failed_path", sa.String(), nullable=True),
        sa.Column("usage_json", sa.String(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("finding_json", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["audit_run_id"], ["auditrun.id"]),
        sa.ForeignKeyConstraint(["checkpoint_final_id"], ["checkpointfinal.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "workpaperdraft",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("audit_run_id", sa.String(), nullable=False),
        sa.Column("workpaper_json", sa.String(), nullable=False),
        sa.Column("docx_path", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["audit_run_id"], ["auditrun.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "workpaperfinal",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("audit_run_id", sa.String(), nullable=False),
        sa.Column("workpaper_json", sa.String(), nullable=False),
        sa.Column("docx_path", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.Column("case_library_entry_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["audit_run_id"], ["auditrun.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "comment",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("comment")
    op.drop_table("workpaperfinal")
    op.drop_table("workpaperdraft")
    op.drop_table("auditpointrun")
    op.drop_table("auditrun")
    op.drop_table("checkpointfinal")
    op.drop_table("checkpointdraft")
    op.drop_table("tenderdoc")
    op.drop_table("extractrun")
    op.drop_table("user")
    op.drop_table("rulesource")
    op.drop_table("project")
