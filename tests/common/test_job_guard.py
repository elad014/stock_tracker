import asyncio

import pytest
from fastapi import HTTPException

from llm_guard import JobRunGuard


def _guard() -> JobRunGuard:
    return JobRunGuard(
        900,
        busy_detail="busy",
        cooldown_detail="cooldown",
        skip_log="skip",
    )


@pytest.mark.asyncio
async def test_second_http_run_hits_cooldown() -> None:
    guard: JobRunGuard = _guard()
    calls: list[int] = []

    async def job() -> None:
        calls.append(1)

    await guard.run_from_http(job)
    with pytest.raises(HTTPException) as exc_info:
        await guard.run_from_http(job)

    assert exc_info.value.status_code == 429
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_force_skips_cooldown() -> None:
    guard: JobRunGuard = _guard()
    calls: list[int] = []

    async def job() -> None:
        calls.append(1)

    await guard.run_from_http(job)
    await guard.run_from_http(job, force=True)

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_force_still_blocks_when_job_is_running() -> None:
    guard: JobRunGuard = _guard()
    started: asyncio.Event = asyncio.Event()
    release: asyncio.Event = asyncio.Event()

    async def slow_job() -> None:
        started.set()
        await release.wait()

    async def quick_job() -> None:
        return None

    running: asyncio.Task[None] = asyncio.create_task(guard.run_from_http(slow_job))
    await started.wait()

    with pytest.raises(HTTPException) as exc_info:
        await guard.run_from_http(quick_job, force=True)
    assert exc_info.value.status_code == 409

    release.set()
    await running


@pytest.mark.asyncio
async def test_schedule_ignores_http_cooldown() -> None:
    guard: JobRunGuard = _guard()
    calls: list[int] = []

    async def job() -> None:
        calls.append(1)

    await guard.run_from_http(job)
    await guard.run_from_schedule(job)

    assert len(calls) == 2
