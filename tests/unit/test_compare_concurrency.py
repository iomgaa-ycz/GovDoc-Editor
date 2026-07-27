"""并发控制单元测试。"""

from __future__ import annotations

import asyncio

import pytest

from govdoc.compare.concurrency import get_compare_semaphore


class TestCompareSemaphore:
    def test_default_limit_is_1(self) -> None:
        sem = get_compare_semaphore(max_concurrent=1)
        assert isinstance(sem, asyncio.Semaphore)

    @pytest.mark.asyncio
    async def test_limits_concurrency(self) -> None:
        sem = get_compare_semaphore(max_concurrent=1)
        running = []

        async def task(task_id: int) -> None:
            async with sem:
                running.append(task_id)
                await asyncio.sleep(0.05)
                assert len(running) <= 1
                running.remove(task_id)

        await asyncio.gather(task(1), task(2), task(3))
