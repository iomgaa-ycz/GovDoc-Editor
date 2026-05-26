"""Projects routes — 项目 CRUD + 文书上传。"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.middleware import log_activity
from govdoc.api.schemas import CreateProjectRequest
from govdoc.db.models import Document, Project
from govdoc.runtime import get_document_store

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", status_code=201)
async def create_project(payload: CreateProjectRequest):
    with get_db_session() as session:
        project = Project(name=payload.name, created_by=payload.created_by)
        session.add(project)
        session.commit()
        session.refresh(project)
        return {"id": project.id, "name": project.name, "created_at": str(project.created_at)}


@router.get("")
async def list_projects():
    with get_db_session() as session:
        projects = session.exec(select(Project)).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "created_at": str(p.created_at),
                "created_by": p.created_by,
            }
            for p in projects
        ]


@router.get("/{project_id}")
async def get_project(project_id: str):
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {
            "id": project.id,
            "name": project.name,
            "created_at": str(project.created_at),
            "created_by": project.created_by,
        }


@router.get("/{project_id}/tender-docs")
async def list_tender_docs(project_id: str):
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        docs = session.exec(select(Document).order_by(Document.created_at.desc())).all()
        return [
            {
                "id": d.id,
                "project_id": project_id,
                "filename": d.filename,
                "storage_path": d.raw_path,
                "markdown_path": d.markdown_path,
            }
            for d in docs
        ]


@router.post("/{project_id}/tender-doc", status_code=201)
async def upload_tender_doc(project_id: str, file: UploadFile = File(...)):
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")

    store = get_document_store()
    content = await file.read()
    raw_path = store.save_raw(
        file.filename or "tender.docx", content, subdir=f"projects/{project_id}"
    )
    warnings_stack: list[str] = []
    md_path = store.get_or_convert(raw_path, warnings_stack=warnings_stack)

    with get_db_session() as session:
        document = Document(
            filename=file.filename or "tender",
            file_type=(file.filename or "tender").rsplit(".", 1)[-1].lower(),
            file_size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            raw_path=str(raw_path),
            markdown_path=str(md_path),
            status="ready",
        )
        session.add(document)
        log_activity(
            session,
            actor="system",
            action="upload_tender_doc",
            target_type="Document",
            target_id=document.id,
            after={"filename": document.filename, "project_id": project_id},
        )
        session.commit()
        session.refresh(document)
        return {
            "id": document.id,
            "filename": document.filename,
            "markdown_path": document.markdown_path,
            "warnings": warnings_stack,
        }
