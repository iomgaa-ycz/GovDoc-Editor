"""文档对比 API 路由。"""

from __future__ import annotations

from asyncio import to_thread
from datetime import datetime
from typing import Any
import json
import logging
from pathlib import Path
from zipfile import BadZipFile

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from govdoc.api.deps import get_db_session
from govdoc.compare.service import create_compare_bundle, get_compare_download
from govdoc.db.models import CompareRun, Document, uid
from govdoc.schemas.compare import CompareResponse, CompareRunStatus


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_EXTENSIONS = {".docx", ".pdf"}


router = APIRouter(
    prefix="/api/v1/compare",
    tags=["compare"],
)
logger = logging.getLogger(__name__)


@router.get("")
def list_compare_runs() -> list[CompareRunStatus]:
    """列出所有文档对比任务。"""
    from sqlmodel import select

    with get_db_session() as session:
        runs = session.exec(
            select(CompareRun).order_by(CompareRun.created_at.desc())
        ).all()
        return [
            CompareRunStatus(
                review_id=run.id,
                status=run.status,
                file_count=run.file_count,
                file_names=_load_json_list(run.file_names_json),
                progress=_load_json_dict(run.progress_json),
                error=run.error,
                created_at=str(run.created_at),
                completed_at=str(run.completed_at) if run.completed_at else None,
            )
            for run in runs
        ]


def _ensure_supported(filename: str) -> None:
    """校验上传文件名是否为支持的文档格式。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 DOCX 和 PDF 文件。")


def _load_json_list(raw: str | None) -> list[str]:
    """从 DB JSON 字符串读取文件名列表，坏数据按空列表处理。"""
    if raw is None:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _load_json_dict(raw: str | None) -> dict | None:
    """从 DB JSON 字符串读取进度字典，坏数据按 None 处理。"""
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _set_compare_run_running(review_id: str) -> None:
    """把对比任务标记为运行中。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            logger.warning("CompareRun 不存在，无法标记 running: %s", review_id)
            return
        run.status = "running"
        run.error = None
        session.add(run)
        session.commit()


def _update_compare_progress(review_id: str, progress: dict) -> None:
    """更新后台对比任务进度。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            logger.warning("CompareRun 不存在，无法更新进度: %s", review_id)
            return
        run.progress_json = json.dumps(progress, ensure_ascii=False)
        session.add(run)
        session.commit()


def _set_compare_run_completed(review_id: str, result_path: str) -> None:
    """把对比任务标记为完成并记录结果路径。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            logger.warning("CompareRun 不存在，无法标记 completed: %s", review_id)
            return
        run.status = "completed"
        run.result_path = result_path
        run.completed_at = datetime.utcnow()
        session.add(run)
        session.commit()


def _set_compare_run_failed(review_id: str, error: str) -> None:
    """把对比任务标记为失败并记录错误信息。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            logger.warning("CompareRun 不存在，无法标记 failed: %s", review_id)
            return
        run.status = "failed"
        run.error = error
        run.completed_at = datetime.utcnow()
        session.add(run)
        session.commit()


@router.post("", status_code=202)
async def create_compare_run(
    payload: dict[str, Any],
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """基于已上传文档 ID 创建异步对比任务并立即返回任务 ID。"""
    document_ids = payload.get("document_ids", [])
    if len(document_ids) < 2:
        return JSONResponse(status_code=400, content={"detail": "至少需要 2 个文档"})

    with get_db_session() as session:
        docs: list[Document] = []
        for document_id in document_ids:
            document = session.get(Document, document_id)
            if document is None or document.status != "ready":
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"文档 {document_id} 不存在或未就绪"},
                )
            docs.append(document)

        file_names = [document.filename for document in docs]
        file_info_list = [
            (document.markdown_path or document.raw_path, document.filename)
            for document in docs
        ]
        review_id = uid()
        compare_run = CompareRun(
            id=review_id,
            status="pending",
            file_count=len(docs),
            file_names_json=json.dumps(file_names, ensure_ascii=False),
            document_ids=json.dumps(document_ids),
        )
        session.add(compare_run)
        session.commit()

    background_tasks.add_task(
        _run_compare_from_docs,
        review_id,
        file_info_list,
    )
    return {"reviewId": review_id, "status": "pending"}


async def _run_compare_from_docs(
    review_id: str,
    file_info_list: list[tuple[str, str]],
) -> None:
    """后台执行已上传文档对比任务。

    Args:
        review_id: 对比任务 ID。
        file_info_list: `(raw_path, filename)` 对列表，来自 Document 表。
    """

    def _execute_compare() -> None:
        _set_compare_run_running(review_id)
        try:
            payload = create_compare_bundle(
                files=[(Path(raw_path), filename) for raw_path, filename in file_info_list],
                on_progress=lambda progress: _update_compare_progress(review_id, progress),
            )
        except (BadZipFile, ValueError) as exc:
            _set_compare_run_failed(review_id, f"文件解析失败: {exc}")
            return
        except (RuntimeError, OSError) as exc:
            _set_compare_run_failed(review_id, f"文档转换失败: {exc}")
            return
        except Exception:
            logger.exception("后台对比执行失败: %s", review_id)
            _set_compare_run_failed(review_id, "后台任务异常退出")
            return

        result_path = Path(payload.artifacts.review_dir) / "review.json"
        _set_compare_run_completed(review_id, str(result_path))

    await to_thread(_execute_compare)


@router.get("/{review_id}/status", response_model=CompareRunStatus)
def get_compare_status(review_id: str) -> CompareRunStatus:
    """读取文档对比任务状态。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")

        return CompareRunStatus(
            review_id=run.id,
            status=run.status,
            file_count=run.file_count,
            file_names=_load_json_list(run.file_names_json),
            progress=_load_json_dict(run.progress_json),
            error=run.error,
            created_at=str(run.created_at),
            completed_at=str(run.completed_at) if run.completed_at else None,
        )


@router.get("/{review_id}/result", response_model=CompareResponse)
def get_compare_result(review_id: str) -> CompareResponse:
    """读取已完成文档对比任务的完整结果。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="对比任务尚未完成。")
        result_path = run.result_path

    if result_path is None:
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    path = Path(result_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    try:
        return CompareResponse.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="对比结果文件损坏。") from exc


@router.get("/{review_id}/download/{file_index}")
def download_compare_file(
    review_id: str,
    file_index: int,
) -> FileResponse:
    """下载指定 review 中某个文件的高亮 DOCX 副本。"""
    try:
        download = get_compare_download(review_id=review_id, file_index=file_index)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="对比结果不存在。") from exc

    return FileResponse(
        path=download.path,
        filename=download.filename,
        media_type=DOCX_MEDIA_TYPE,
    )
