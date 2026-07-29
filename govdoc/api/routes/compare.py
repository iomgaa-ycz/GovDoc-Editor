"""文档对比 API 路由。"""

from __future__ import annotations

from asyncio import to_thread
from contextlib import contextmanager
from datetime import datetime
from typing import Any
import json
import logging
import multiprocessing
import resource
from pathlib import Path
from zipfile import BadZipFile

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlmodel import Session, create_engine

from govdoc.api.deps import get_db_session
from govdoc.compare.service import create_compare_bundle, get_compare_download
from govdoc.compare.simhash import CompareTooComplexError
from govdoc.db.models import CompareRun, Document, uid
from govdoc.runtime import get_config
from govdoc.schemas.compare import CompareResponse, CompareRunStatus


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_EXTENSIONS = {".docx", ".pdf"}
# 正常 9 文件真实对比实测峰值 <1GB；16GB 给文档转换和序列化保留安全余量。
COMPARE_CHILD_MEMORY_LIMIT_BYTES = 16 * 1024**3
COMPARE_SAFE_ABORT_ERROR = "对比规模过大或文件异常，已安全终止，请减少文件数量后重试"


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
        runs = session.exec(select(CompareRun).order_by(CompareRun.created_at.desc())).all()
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


def _validate_compare_file_count(count: int) -> JSONResponse | None:
    """校验对比文件数量是否超过后端部署上限。

    参数:
        count: 本次对比的文档数量。

    返回值:
        超限时返回 400 JSONResponse；未超限返回 None。
    """
    max_files = get_config().compare.max_files
    if max_files is not None and count > max_files:
        return JSONResponse(
            status_code=400,
            content={"detail": f"当前部署最多支持 {max_files} 份文件。"},
        )
    return None


def _collect_markdown_file_info(
    documents: list[Document],
) -> tuple[list[str], list[tuple[str, str]]] | JSONResponse:
    """校验文档转换结果并提取对比输入文件。

    参数:
        documents: 已校验就绪的 Document 记录。

    返回值:
        成功时返回 ``(file_names, file_info_list)``；转换结果缺失时返回 400。

    关键实现细节:
        对比只消费 markdown_path，禁止回退 raw_path，避免绕过文件转换状态。
    """
    file_names: list[str] = []
    file_info_list: list[tuple[str, str]] = []
    for document in documents:
        if not document.markdown_path or not Path(document.markdown_path).exists():
            return JSONResponse(
                status_code=400,
                content={
                    "detail": f"文档「{document.filename}」转换结果缺失，请在文件管理中重新转换后再对比"
                },
            )
        file_names.append(document.filename)
        file_info_list.append((document.markdown_path, document.filename))
    return file_names, file_info_list


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
    file_count_error = _validate_compare_file_count(len(document_ids))
    if file_count_error is not None:
        return file_count_error

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

        collected = _collect_markdown_file_info(docs)
        if isinstance(collected, JSONResponse):
            return collected
        file_names, file_info_list = collected
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


def _bind_child_db_session(database_url: str) -> None:
    """在子进程内把本模块 DB 会话绑定到父进程传入的 SQLite URL。

    参数:
        database_url: 父进程解析出的应用数据库 URL。

    关键实现细节:
        spawn 子进程不会继承 pytest monkeypatch 或父进程 lru_cache，因此显式传入
        database_url，并只替换本模块全局 get_db_session，沿用现有状态写入辅助函数。
    """
    engine = create_engine(database_url, connect_args={"check_same_thread": False})

    @contextmanager
    def _child_session() -> Any:
        with Session(engine) as session:
            yield session

    globals()["get_db_session"] = _child_session


def _execute_compare_process(
    review_id: str,
    file_info_list: list[tuple[str, str]],
    database_url: str,
    memory_limit_bytes: int = COMPARE_CHILD_MEMORY_LIMIT_BYTES,
) -> None:
    """子进程入口：设置内存上限并执行文档对比。

    参数:
        review_id: CompareRun ID。
        file_info_list: ``(markdown_path, filename)`` 列表。
        database_url: 应用 SQLite URL，供子进程写状态。
        memory_limit_bytes: RLIMIT_AS 上限，默认 16GB。

    关键实现细节:
        子进程内负责 running/progress/completed/failed 全部 DB 状态写入；父进程只在
        超时或非零退出且 DB 未进入终态时兜底标记失败。
    """
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
    _bind_child_db_session(database_url)

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
    except CompareTooComplexError as exc:
        _set_compare_run_failed(review_id, str(exc))
        return
    except Exception:
        logger.exception("后台对比子进程执行失败: %s", review_id)
        _set_compare_run_failed(review_id, "后台任务异常退出")
        return

    result_path = Path(payload.artifacts.review_dir) / "review.json"
    _set_compare_run_completed(review_id, str(result_path))


def _compare_run_in_terminal_state(review_id: str) -> bool:
    """判断 CompareRun 是否已进入 completed/failed 终态。

    参数:
        review_id: CompareRun ID。

    返回值:
        已完成或失败返回 True；缺失或非终态返回 False。
    """
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        return run is not None and run.status in {"completed", "failed"}


async def _run_compare_from_docs(
    review_id: str,
    file_info_list: list[tuple[str, str]],
) -> None:
    """后台执行已上传文档对比任务，并用子进程隔离内存风险。"""
    from govdoc.compare.concurrency import get_compare_semaphore

    cfg = get_config()
    sem = get_compare_semaphore(cfg.compare.max_concurrent)

    async with sem:
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(
            target=_execute_compare_process,
            args=(
                review_id,
                file_info_list,
                cfg.app.database_url,
                COMPARE_CHILD_MEMORY_LIMIT_BYTES,
            ),
        )
        process.start()
        await to_thread(process.join, cfg.compare.pdf_timeout_s)

        if process.is_alive():
            process.terminate()
            await to_thread(process.join, 5)
            if not _compare_run_in_terminal_state(review_id):
                _set_compare_run_failed(review_id, "对比任务超时，请减少文件数量后重试")
            return

        if process.exitcode != 0 and not _compare_run_in_terminal_state(review_id):
            _set_compare_run_failed(review_id, COMPARE_SAFE_ABORT_ERROR)


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


@router.get("/{review_id}/summary")
def get_compare_summary(
    review_id: str,
    category: str | None = None,
    min_length: int = 0,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """读取对比摘要，支持按类别筛选和分页。

    - category: paragraph / sentence / similar，不传则默认 paragraph
    - min_length: 最小匹配文本长度，过滤小于该值的匹配项
    - page: 页码（从 1 开始）
    - page_size: 每页条数（默认 100）
    """
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="对比任务尚未完成。")
        result_path = run.result_path

    if result_path is None:
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    review_dir = Path(result_path).parent
    summary_path = review_dir / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="摘要文件不存在，请重新对比。")

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    all_matches = data.get("matches", [])
    threshold = max(0, min_length)
    length_filtered = [m for m in all_matches if int(m.get("length") or 0) >= threshold]

    active_category = category or "paragraph"
    filtered = [m for m in length_filtered if m.get("category") == active_category]

    category_counts = {}
    for m in length_filtered:
        cat = m.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_matches = filtered[start:end]

    data["matches"] = page_matches
    data["matchPagination"] = {
        "category": active_category,
        "page": page,
        "pageSize": page_size,
        "minLength": threshold,
        "totalInCategory": total,
        "totalPages": (total + page_size - 1) // page_size,
        "categoryCounts": category_counts,
    }
    return data


@router.get("/{review_id}/context")
def get_compare_context(review_id: str, matchId: str, surrounding: int = 3) -> dict:
    """按需加载指定匹配项的上下文段落。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "completed":
            raise HTTPException(status_code=409, detail="对比任务尚未完成。")
        result_path = run.result_path

    if result_path is None:
        raise HTTPException(status_code=404, detail="对比结果不存在。")

    review_dir = Path(result_path).parent
    from govdoc.compare.context_loader import load_match_context

    try:
        return load_match_context(review_dir, matchId, surrounding=surrounding)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="拆分文件缺失，请重新对比。") from exc


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


def _load_failed_run_document_ids(review_id: str) -> list[str]:
    """从失败的 CompareRun 中提取 document_ids。"""
    with get_db_session() as session:
        run = session.get(CompareRun, review_id)
        if run is None:
            raise HTTPException(status_code=404, detail="对比任务不存在。")
        if run.status != "failed":
            raise HTTPException(status_code=409, detail="仅失败任务可重试。")
        document_ids = json.loads(run.document_ids) if run.document_ids else []
    if len(document_ids) < 2:
        raise HTTPException(status_code=400, detail="原始文档信息丢失，无法重试。")
    return document_ids


def _create_retry_run(document_ids: list[str]) -> tuple[str, list[tuple[str, str]]]:
    """校验文档并创建重试用的 CompareRun。"""
    with get_db_session() as session:
        docs = []
        for doc_id in document_ids:
            doc = session.get(Document, doc_id)
            if doc is None or doc.status != "ready":
                raise HTTPException(status_code=400, detail=f"文档 {doc_id} 不存在或未就绪。")
            docs.append(doc)

        collected = _collect_markdown_file_info(docs)
        if isinstance(collected, JSONResponse):
            detail = json.loads(collected.body).get("detail", "文档转换结果缺失。")
            raise HTTPException(status_code=400, detail=detail)
        file_names, file_info_list = collected
        new_id = uid()
        new_run = CompareRun(
            id=new_id,
            status="pending",
            file_count=len(docs),
            file_names_json=json.dumps(file_names, ensure_ascii=False),
            document_ids=json.dumps(document_ids),
        )
        session.add(new_run)
        session.commit()
    return new_id, file_info_list


@router.post("/{review_id}/retry", status_code=202)
async def retry_compare_run(
    review_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """重试失败的对比任务（创建新任务）。"""
    document_ids = _load_failed_run_document_ids(review_id)
    new_id, file_info_list = _create_retry_run(document_ids)
    background_tasks.add_task(_run_compare_from_docs, new_id, file_info_list)
    return {"reviewId": new_id, "status": "pending"}
