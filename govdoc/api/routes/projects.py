"""Projects routes — 项目 CRUD + 文书上传。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.api.schemas import CreateProjectRequest
from govdoc.db.models import Project, TenderDoc
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
            {"id": p.id, "name": p.name, "created_at": str(p.created_at), "created_by": p.created_by}
            for p in projects
        ]


@router.get("/{project_id}")
async def get_project(project_id: str):
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {"id": project.id, "name": project.name, "created_at": str(project.created_at), "created_by": project.created_by}


@router.get("/{project_id}/tender-docs")
async def list_tender_docs(project_id: str):
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        docs = session.exec(
            select(TenderDoc).where(TenderDoc.project_id == project_id)
        ).all()
        return [
            {
                "id": d.id,
                "project_id": d.project_id,
                "filename": d.filename,
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
    raw_path = store.save_raw(file.filename or "tender.docx", content, subdir=f"projects/{project_id}")
    warnings_stack: list[str] = []
    md_path = store.get_or_convert(raw_path, warnings_stack=warnings_stack)

    with get_db_session() as session:
        tender = TenderDoc(
            project_id=project_id,
            filename=file.filename or "tender",
            storage_path=str(raw_path),
            markdown_path=str(md_path),
            qmd_collection=f"project_{project_id}_tender",
        )
        session.add(tender)
        session.commit()
        session.refresh(tender)
        return {
            "id": tender.id,
            "filename": tender.filename,
            "markdown_path": tender.markdown_path,
            "warnings": warnings_stack,
        }
