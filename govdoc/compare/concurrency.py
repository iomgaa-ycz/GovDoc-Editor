"""对比任务并发控制。"""
from __future__ import annotations

import asyncio
from functools import lru_cache


@lru_cache
def get_compare_semaphore(max_concurrent: int = 1) -> asyncio.Semaphore:
    """获取对比任务信号量（进程级单例）。"""
    return asyncio.Semaphore(max_concurrent)
