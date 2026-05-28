"""add document tag tables replace tenderdoc

Revision ID: 20b48994c587
Revises: d08dafa25255
Create Date: 2026-05-26 07:40:20.252938
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20b48994c587"
down_revision = "d08dafa25255"
branch_labels = None
depends_on = None


FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}
DOCUMENT_REF = sa.Table(
    "document", sa.MetaData(), sa.Column("id", sa.String(), primary_key=True)
)
TENDERDOC_REF = sa.Table(
    "tenderdoc", sa.MetaData(), sa.Column("id", sa.String(), primary_key=True)
)


def upgrade() -> None:
    op.create_table(
        "document",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("raw_path", sa.String(), nullable=False),
        sa.Column("markdown_path", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tag",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "documenttag",
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("tag_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )

    try:
        conn = op.get_bind()
        rows = conn.execute(
            sa.text(
                "SELECT id, filename, storage_path, markdown_path, uploaded_at "
                "FROM tenderdoc"
            )
        ).fetchall()
        for row in rows:
            file_type = (
                row.filename.rsplit(".", 1)[-1].lower()
                if "." in row.filename
                else "unknown"
            )
            conn.execute(
                sa.text(
                    "INSERT INTO document "
                    "(id, filename, file_type, file_size, sha256, raw_path, "
                    "markdown_path, status, created_at, updated_at) "
                    "VALUES (:id, :filename, :file_type, 0, '', :raw_path, "
                    ":markdown_path, 'ready', :created_at, :created_at)"
                ),
                {
                    "id": row.id,
                    "filename": row.filename,
                    "file_type": file_type,
                    "raw_path": row.storage_path,
                    "markdown_path": row.markdown_path,
                    "created_at": row.uploaded_at,
                },
            )
    except Exception:
        pass

    with op.batch_alter_table(
        "auditrun",
        naming_convention=FK_NAMING_CONVENTION,
        table_args=(
            sa.ForeignKeyConstraint(["tender_doc_id"], [DOCUMENT_REF.c.id]),
        ),
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_auditrun_tender_doc_id_tenderdoc", type_="foreignkey"
        )
        batch_op.alter_column(
            "tender_doc_id",
            new_column_name="main_document_id",
            existing_type=sa.String(),
            existing_nullable=False,
        )

    with op.batch_alter_table("comparerun") as batch_op:
        batch_op.add_column(sa.Column("document_ids", sa.String(), nullable=True))

    op.drop_table("tenderdoc")


def downgrade() -> None:
    op.create_table(
        "tenderdoc",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("markdown_path", sa.String(), nullable=False),
        sa.Column("qmd_collection", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("uploaded_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT d.id, d.filename, d.raw_path, d.markdown_path, d.created_at, "
            "COALESCE("
            "(SELECT ar.project_id FROM auditrun ar "
            "WHERE ar.main_document_id = d.id LIMIT 1), "
            "(SELECT p.id FROM project p LIMIT 1), "
            "'') AS project_id "
            "FROM document d"
        )
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO tenderdoc "
                "(id, project_id, filename, storage_path, markdown_path, "
                "qmd_collection, uploaded_at, uploaded_by) "
                "VALUES (:id, :project_id, :filename, :storage_path, "
                ":markdown_path, :qmd_collection, :uploaded_at, NULL)"
            ),
            {
                "id": row.id,
                "project_id": row.project_id,
                "filename": row.filename,
                "storage_path": row.raw_path,
                "markdown_path": row.markdown_path or row.raw_path,
                "qmd_collection": f"tender_{row.id}",
                "uploaded_at": row.created_at,
            },
        )

    with op.batch_alter_table(
        "auditrun",
        naming_convention=FK_NAMING_CONVENTION,
        table_args=(
            sa.ForeignKeyConstraint(["main_document_id"], [TENDERDOC_REF.c.id]),
        ),
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_auditrun_main_document_id_document", type_="foreignkey"
        )
        batch_op.alter_column(
            "main_document_id",
            new_column_name="tender_doc_id",
            existing_type=sa.String(),
            existing_nullable=False,
        )

    with op.batch_alter_table("comparerun") as batch_op:
        batch_op.drop_column("document_ids")

    op.drop_table("documenttag")
    op.drop_table("tag")
    op.drop_table("document")
