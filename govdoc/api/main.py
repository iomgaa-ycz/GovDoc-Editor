"""GovDoc FastAPI app factory."""

from __future__ import annotations

import os

# SentenceTransformer 默认选 cuda:0（local_rank=0）。
# 部署机 GPU 0 可能被 VLLM 占满时，通过环境变量 LOCAL_RANK=2 外部指定。
os.environ.setdefault("LOCAL_RANK", "0")

# MonkeyOCR 内网服务不走代理
_no_proxy = os.environ.get("no_proxy", "")
if "100.81.95.44" not in _no_proxy:
    os.environ["no_proxy"] = f"{_no_proxy},100.81.95.44"

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from govdoc.api.deps import get_db_session
from govdoc.api.routes.audit import router as audit_router
from govdoc.api.routes.checkpoints import router as checkpoints_router
from govdoc.api.routes.compare import router as compare_router
from govdoc.api.routes.comments import router as comments_router
from govdoc.api.routes.projects import router as projects_router
from govdoc.api.routes.rules import router as rules_router
from govdoc.api.routes.workpapers import router as workpapers_router
from govdoc.db.session import init_db


def create_app() -> FastAPI:
    from govdoc.config import load_config

    cfg = load_config()
    cfg.ensure_directories()
    init_db()

    from govdoc.runtime import configure_logging

    configure_logging()
    _logger = logging.getLogger("govdoc.api")
    app = FastAPI(title="GovDoc Auditor V3", version="0.1.0")

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        tb = traceback.format_exc()
        _logger.error(
            "Unhandled %s on %s %s:\n%s", type(exc).__name__, request.method, request.url.path, tb
        )
        return JSONResponse(
            status_code=500, content={"detail": str(exc), "type": type(exc).__name__}
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/runtime/diagnostics")
    async def runtime_diagnostics():
        from govdoc.runtime import collect_diagnostics

        return collect_diagnostics()

    @app.get("/runtime/trajectories/{run_id}")
    async def get_runtime_trajectory(run_id: str):
        from govdoc.runtime import get_trajectory_store

        store = get_trajectory_store()
        record = store.get_run(run_id)
        if record is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"未找到 trajectory: {run_id}")
        return {
            "run_id": record.run_id,
            "status": record.status,
            "phases": [
                {
                    "phase": p.phase,
                    "started_at": str(p.started_at) if p.started_at else None,
                    "ended_at": str(p.ended_at) if p.ended_at else None,
                    "error": p.error,
                }
                for p in record.phases
            ],
        }

    @app.on_event("startup")
    def _sweep_orphaned_runs():
        """启动时将无心跳的 running 状态 AuditRun/ExtractRun 标记为 interrupted。"""
        from datetime import datetime, timedelta

        from govdoc.db.models import AuditRun, ExtractRun
        from sqlmodel import select

        cutoff = datetime.utcnow() - timedelta(minutes=10)
        with get_db_session() as session:
            for ar in session.exec(select(AuditRun).where(AuditRun.status == "running")).all():
                if ar.heartbeat_at is None or ar.heartbeat_at < cutoff:
                    ar.status = "interrupted"
                    ar.error = "服务重启时检测到孤儿任务"
                    session.add(ar)
                    _logger.warning("标记孤儿 AuditRun: %s", ar.id)
            for er in session.exec(
                select(ExtractRun).where(ExtractRun.status.in_(["pending", "running"]))
            ).all():
                if er.heartbeat_at is None or er.heartbeat_at < cutoff:
                    er.status = "interrupted"
                    er.error = "服务重启时检测到孤儿任务"
                    session.add(er)
                    _logger.warning("标记孤儿 ExtractRun: %s", er.id)
            session.commit()
        _logger.info("孤儿任务扫描完成")

    app.include_router(projects_router)
    app.include_router(rules_router)
    app.include_router(checkpoints_router)
    app.include_router(audit_router)
    app.include_router(workpapers_router)
    app.include_router(compare_router)
    app.include_router(comments_router)
    return app


app = create_app()
