"""一次性静默补转：把卡在 ``converting`` 的文档强制用 MonkeyOCR 重转并翻成 ready。

背景：glm 云端 OCR 调用挂死导致一批文档长期卡在 ``converting``。本脚本以独立进程、
**强制只用 MonkeyOCR**（绕开会挂死的 glm 兜底）逐个补转，成功才把状态翻 ready；失败则
保持 ``converting`` 不动（不暴露 failed 错误态）。按文件体积从小到大处理，先让中小文件见效。

用法（4090 服务器, govdoc-auditor-v3 环境，须先 export NO_PROXY + HF_HUB_OFFLINE=1）::

    python scripts/recover_stuck_docs.py
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from sqlmodel import select

from govdoc.api.deps import get_db_session
from govdoc.config import load_config
from govdoc.db.models import Document
from govdoc.storage.files import DocumentStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("recover")


def _build_monkey_only_store() -> DocumentStore:
    """构建强制只用 MonkeyOCR 的 DocumentStore（绕开会挂死的 glm 兜底）。

    Returns:
        api_backends 被覆盖为 ``["monkey"]`` 的 DocumentStore。
    """
    cfg = load_config()
    converter_kwargs = dict(cfg.app.converter or {})
    converter_kwargs["api_backends"] = ["monkey"]  # 关键：只走本地 MonkeyOCR
    logger.info("MonkeyOCR 端点: %s", converter_kwargs.get("monkey_endpoints"))
    return DocumentStore(cfg.storage_root, converter_kwargs=converter_kwargs)


def main() -> None:
    """入口：对生产库中所有 converting 文档执行 MonkeyOCR 补转。"""
    store = _build_monkey_only_store()
    with get_db_session() as session:
        session.connection().exec_driver_sql("PRAGMA busy_timeout=30000")
        docs = session.exec(
            select(Document)
            .where(Document.status == "converting")
            .order_by(Document.file_size)
        ).all()
        logger.info("待补转 %d 个文档（按体积升序）", len(docs))

        ok: list[str] = []
        fail: list[str] = []
        for doc in docs:
            size_mb = (doc.file_size or 0) / 1e6
            logger.info("开始 %s %s (%.1fMB)", doc.id[:8], doc.filename, size_mb)
            started = time.time()
            try:
                markdown_path = store.get_or_convert(doc.raw_path)
                doc.markdown_path = str(markdown_path)
                doc.status = "ready"
                doc.error_message = None
                doc.updated_at = datetime.utcnow()
                session.add(doc)
                session.commit()
                logger.info(
                    "✓ 成功 %s 用时%.0fs -> %s",
                    doc.id[:8],
                    time.time() - started,
                    markdown_path,
                )
                ok.append(doc.id)
            except Exception:  # noqa: BLE001 — 单个失败不影响其余，且保持 converting 不暴露错误
                session.rollback()
                logger.exception(
                    "✗ 失败 %s 用时%.0fs，保持 converting 不动",
                    doc.id[:8],
                    time.time() - started,
                )
                fail.append(doc.id)

        logger.info(
            "完成：成功 %d，失败 %d；失败列表=%s",
            len(ok),
            len(fail),
            [f[:8] for f in fail],
        )


if __name__ == "__main__":
    main()
