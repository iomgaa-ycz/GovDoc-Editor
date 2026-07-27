"""Document API 路由：上传、CRUD、重转与批量标签。"""

from __future__ import annotations

import hashlib
import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile
from pydantic import Field
from sqlmodel import Session, select

from govdoc.db.models import Document, DocumentTag, Tag
from govdoc.db.session import get_session
from govdoc.runtime import get_document_store
from govdoc.schemas import GovDocModel

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)

_SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx", ".doc"})
# 同一时刻最多 2 个文档在 chunk/OCR 转换，防止大 PDF 并发转换耗尽内存（2026-07-24 OOM 事故防护）。
_CONVERT_SEMAPHORE = threading.Semaphore(2)
# 1GB 上传上限，与 nginx client_max_body_size 1g 一致。
_MAX_UPLOAD_BYTES = 1024**3


class BatchTagRequest(GovDocModel):
    """批量打标签请求。"""

    document_ids: list[str] = Field(default_factory=list)
    tag_ids: list[str] = Field(default_factory=list)


@contextmanager
def _session_scope() -> Iterator[Session]:
    """兼容 get_session 的生成器形态，提供局部上下文管理器。

    返回值:
        可用于数据库读写的 SQLModel Session。
    """
    session_source = get_session()
    if hasattr(session_source, "__enter__"):
        with session_source as session:
            yield session
        return

    session = next(session_source)
    try:
        yield session
    finally:
        close = getattr(session_source, "close", None)
        if close is not None:
            close()


def _now() -> datetime:
    """返回当前 UTC 时间，集中封装便于字段一致更新。"""
    return datetime.utcnow()


def _normalize_file_type(filename: str) -> str:
    """校验文件后缀并返回无点小写文件类型。

    参数:
        filename: 上传文件名。

    返回值:
        `pdf`、`docx` 或 `doc`。

    异常:
        HTTPException: 文件名为空或后缀不受支持。
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {suffix or '无后缀'}")
    return suffix.lstrip(".")


def _serialize_tag(tag: Tag) -> dict[str, Any]:
    """序列化标签记录。

    参数:
        tag: Tag 数据库模型。

    返回值:
        API 响应中的标签字典。
    """
    return {
        "id": tag.id,
        "name": tag.name,
        "color": tag.color,
        "created_at": str(tag.created_at),
    }


def _serialize_document(document: Document, tags: list[Tag] | None = None) -> dict[str, Any]:
    """序列化文档记录并附带标签列表。

    参数:
        document: Document 数据库模型。
        tags: 与文档关联的标签列表。

    返回值:
        API 响应中的文档字典。
    """
    return {
        "id": document.id,
        "filename": document.filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "sha256": document.sha256,
        "raw_path": document.raw_path,
        "markdown_path": document.markdown_path,
        "status": document.status,
        "error_message": document.error_message,
        "created_at": str(document.created_at),
        "updated_at": str(document.updated_at),
        "tags": [_serialize_tag(tag) for tag in (tags or [])],
    }


def _load_tags_by_document(session: Session, document_ids: list[str]) -> dict[str, list[Tag]]:
    """批量加载文档标签，避免列表接口逐条查询。

    参数:
        session: 当前数据库会话。
        document_ids: 需要加载标签的文档 ID 列表。

    返回值:
        以 document_id 为 key 的标签列表映射。
    """
    if not document_ids:
        return {}

    links = session.exec(select(DocumentTag).where(DocumentTag.document_id.in_(document_ids))).all()
    tag_ids = sorted({link.tag_id for link in links})
    tags = session.exec(select(Tag).where(Tag.id.in_(tag_ids))).all() if tag_ids else []
    tags_by_id = {tag.id: tag for tag in tags}
    result: dict[str, list[Tag]] = {document_id: [] for document_id in document_ids}
    for link in links:
        tag = tags_by_id.get(link.tag_id)
        if tag is not None:
            result.setdefault(link.document_id, []).append(tag)
    return result


def _delete_file(path: str | None) -> None:
    """尽力删除单个物理文件。

    参数:
        path: 文件路径，空值直接忽略。
    """
    if not path:
        return
    try:
        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
    except OSError:
        logger.warning("删除文档物理文件失败: %s", path, exc_info=True)


def _convert_document(doc_id: str) -> None:
    """后台转换 Document 原始文件为 Markdown。

    参数:
        doc_id: 待转换的 Document ID。

    关键实现:
        后台任务自行创建 Session，避免复用请求生命周期中的会话。
    """
    with _session_scope() as session:
        document = session.get(Document, doc_id)
        if document is None:
            return
        try:
            store = get_document_store()
            with _CONVERT_SEMAPHORE:
                markdown_path = store.get_or_convert(document.raw_path)
            document.markdown_path = str(markdown_path)
            document.status = "ready"
            document.error_message = None
        except Exception as exc:
            logger.exception("文档转换失败: %s", doc_id)
            document.status = "failed"
            document.error_message = str(exc)
        document.updated_at = _now()
        session.add(document)
        session.commit()


@router.post("/upload", status_code=201)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> list[dict[str, Any]]:
    """上传一个或多个文件，创建 Document 并提交后台转换。

    参数:
        background_tasks: FastAPI 后台任务队列。
        files: multipart 上传的文件列表。

    返回值:
        已创建或命中去重的文档列表。
    """
    store = get_document_store()
    responses: list[dict[str, Any]] = []

    with _session_scope() as session:
        for upload_file in files:
            filename = upload_file.filename or ""
            file_type = _normalize_file_type(filename)
            content = await upload_file.read()
            if len(content) > _MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"文件 {filename} 超过 1GB 上传上限，请拆分后重试",
                )
            sha256 = hashlib.sha256(content).hexdigest()

            existing = session.exec(select(Document).where(Document.sha256 == sha256)).first()
            if existing is not None:
                tags_by_document = _load_tags_by_document(session, [existing.id])
                responses.append(
                    _serialize_document(existing, tags_by_document.get(existing.id, []))
                )
                continue

            raw_path = store.save_raw(filename, content)
            document = Document(
                filename=filename,
                file_type=file_type,
                file_size=len(content),
                sha256=sha256,
                raw_path=str(raw_path),
                status="converting",
                updated_at=_now(),
            )
            session.add(document)
            session.commit()
            session.refresh(document)
            background_tasks.add_task(_convert_document, document.id)
            responses.append(_serialize_document(document, []))

    return responses


@router.get("/")
async def list_documents(
    status: str | None = None,
    file_type: str | None = None,
    tag_id: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """列出文档并支持状态、类型、标签和文件名关键字筛选。

    参数:
        status: 文档状态筛选。
        file_type: 文件类型筛选，支持带点或不带点。
        tag_id: 标签 ID 筛选。
        q: 文件名关键字。

    返回值:
        文档列表，每条记录附带 tags。
    """
    with _session_scope() as session:
        stmt = select(Document).order_by(Document.created_at.desc())
        if status:
            stmt = stmt.where(Document.status == status)
        if file_type:
            stmt = stmt.where(Document.file_type == file_type.lower().lstrip("."))
        if tag_id:
            stmt = stmt.join(DocumentTag).where(DocumentTag.tag_id == tag_id)
        if q:
            stmt = stmt.where(Document.filename.ilike(f"%{q}%"))

        documents = session.exec(stmt).all()
        tags_by_document = _load_tags_by_document(session, [doc.id for doc in documents])
        return [
            _serialize_document(document, tags_by_document.get(document.id, []))
            for document in documents
        ]


@router.post("/batch-tag", status_code=201)
async def batch_tag_documents(payload: BatchTagRequest) -> dict[str, int]:
    """批量创建 DocumentTag 关联，已存在的关联会跳过。

    参数:
        payload: 文档 ID 与标签 ID 列表。

    返回值:
        创建与跳过的关联数量。
    """
    with _session_scope() as session:
        missing_documents = [
            document_id
            for document_id in payload.document_ids
            if session.get(Document, document_id) is None
        ]
        if missing_documents:
            raise HTTPException(
                status_code=404,
                detail=f"Document 不存在: {', '.join(missing_documents)}",
            )

        missing_tags = [tag_id for tag_id in payload.tag_ids if session.get(Tag, tag_id) is None]
        if missing_tags:
            raise HTTPException(status_code=404, detail=f"Tag 不存在: {', '.join(missing_tags)}")

        created_count = 0
        skipped_count = 0
        for document_id in payload.document_ids:
            for tag_id in payload.tag_ids:
                existing = session.get(DocumentTag, (document_id, tag_id))
                if existing is not None:
                    skipped_count += 1
                    continue
                session.add(DocumentTag(document_id=document_id, tag_id=tag_id))
                created_count += 1
        session.commit()
        return {"created_count": created_count, "skipped_count": skipped_count}


@router.get("/{doc_id}")
async def get_document(doc_id: str) -> dict[str, Any]:
    """获取单个文档详情，包含标签列表。

    参数:
        doc_id: Document ID。

    返回值:
        文档详情。
    """
    with _session_scope() as session:
        document = session.get(Document, doc_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document 不存在")
        tags_by_document = _load_tags_by_document(session, [doc_id])
        return _serialize_document(document, tags_by_document.get(doc_id, []))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str) -> Response:
    """删除文档、标签关联与物理文件。

    参数:
        doc_id: Document ID。

    返回值:
        204 空响应。
    """
    with _session_scope() as session:
        document = session.get(Document, doc_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document 不存在")

        links = session.exec(select(DocumentTag).where(DocumentTag.document_id == doc_id)).all()
        for link in links:
            session.delete(link)

        raw_path = document.raw_path
        markdown_path = document.markdown_path
        session.delete(document)
        session.commit()

    _delete_file(raw_path)
    if markdown_path != raw_path:
        _delete_file(markdown_path)
    return Response(status_code=204)


@router.post("/{doc_id}/reconvert", status_code=202)
async def reconvert_document(doc_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """重置文档转换状态并重新提交后台转换任务。

    参数:
        doc_id: Document ID。
        background_tasks: FastAPI 后台任务队列。

    返回值:
        文档 ID 与当前状态。
    """
    with _session_scope() as session:
        document = session.get(Document, doc_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document 不存在")
        document.status = "converting"
        document.markdown_path = None
        document.error_message = None
        document.updated_at = _now()
        session.add(document)
        session.commit()

    background_tasks.add_task(_convert_document, doc_id)
    return {"id": doc_id, "status": "converting"}


@router.delete("/{doc_id}/tags/{tag_id}", status_code=204)
async def remove_document_tag(doc_id: str, tag_id: str) -> Response:
    """移除单个文档上的单个标签。

    参数:
        doc_id: Document ID。
        tag_id: Tag ID。

    返回值:
        204 空响应。
    """
    with _session_scope() as session:
        if session.get(Document, doc_id) is None:
            raise HTTPException(status_code=404, detail="Document 不存在")
        link = session.get(DocumentTag, (doc_id, tag_id))
        if link is not None:
            session.delete(link)
            session.commit()
    return Response(status_code=204)
