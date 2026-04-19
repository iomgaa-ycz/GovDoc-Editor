"""GovDoc FastAPI app factory."""

from __future__ import annotations

import os

# SentenceTransformer 默认选 cuda:0（local_rank=0），
# GPU 0 被 VLLM 占满，强制 embedding 模型落到 GPU 2。
os.environ.setdefault("LOCAL_RANK", "2")

# MonkeyOCR 内网服务不走代理
_no_proxy = os.environ.get("no_proxy", "")
if "100.81.95.44" not in _no_proxy:
    os.environ["no_proxy"] = f"{_no_proxy},100.81.95.44"

from fastapi import FastAPI

from govdoc.api.routes.audit import router as audit_router
from govdoc.api.routes.checkpoints import router as checkpoints_router
from govdoc.api.routes.projects import router as projects_router
from govdoc.api.routes.rules import router as rules_router
from govdoc.api.routes.workpapers import router as workpapers_router
from govdoc.db.session import init_db


def create_app() -> FastAPI:
    from govdoc.config import load_config

    cfg = load_config()
    cfg.ensure_directories()
    init_db()
    app = FastAPI(title="GovDoc Auditor V3", version="0.1.0")

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

    app.include_router(projects_router)
    app.include_router(rules_router)
    app.include_router(checkpoints_router)
    app.include_router(audit_router)
    app.include_router(workpapers_router)
    return app


app = create_app()
