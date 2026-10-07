import asyncio
from datetime import datetime
from typing import Any

from lib.generation_worker import CapacityTable, GenerationWorker


class _WakeQueue:
    def __init__(self) -> None:
        self.idle = asyncio.Event()
        self.completed = asyncio.Event()
        self.claimed = False
        self.succeeded: list[tuple[str, dict[str, Any]]] = []

    async def acquire_or_renew_worker_lease(self, **_kwargs: Any) -> bool:
        return True

    async def release_worker_lease(self, **_kwargs: Any) -> None:
        return None

    async def list_orphan_tasks_on_start(self) -> list[dict[str, Any]]:
        return []

    async def claim_next_task(self, media_type: str, **_kwargs: Any) -> dict[str, str] | None:
        assert media_type == "text"
        if self.idle.is_set() and not self.claimed:
            self.claimed = True
            return {"task_id": "wake-task", "media_type": "text", "provider_id": "text"}
        self.idle.set()
        return None

    async def mark_task_succeeded(self, task_id: str, result: dict[str, Any]) -> int:
        self.succeeded.append((task_id, result))
        self.completed.set()
        return 1


async def test_wake_claims_task_without_waiting_for_poll_interval() -> None:
    queue = _WakeQueue()

    async def text_provider(_task: dict[str, Any]) -> str:
        return "text"

    async def execute(_task: dict[str, Any], *, claimed_provider_id: str) -> dict[str, bool]:
        assert claimed_provider_id == "text"
        return {"ok": True}

    async def no_settle(*, taskless_started_before: datetime | None) -> int:
        return 0

    worker = GenerationWorker(
        queue=queue,
        capacity=CapacityTable(_limits={}, _defaults={"text": 1}),
        provider_projection=text_provider,
        executor=execute,
        lanes=("text",),
        settle_interrupted_calls=no_settle,
    )
    worker.poll_interval = 60
    await worker.start()
    try:
        await asyncio.wait_for(queue.idle.wait(), timeout=1)
        worker.wake()
        await asyncio.wait_for(queue.completed.wait(), timeout=1)
        assert queue.succeeded == [("wake-task", {"ok": True})]
    finally:
        await worker.stop()


def test_pool_full_requeue_log_is_throttled_per_provider_lane(caplog, monkeypatch) -> None:
    """池满回队日志每 (provider, media_type) 1 分钟最多一条，claim/requeue 本身不节流。"""
    import logging

    from lib.generation_worker import _POOL_FULL_LOG_INTERVAL_SECONDS

    clock = {"now": 1000.0}
    monkeypatch.setattr("lib.generation_worker.time.monotonic", lambda: clock["now"])
    worker = GenerationWorker(
        queue=_WakeQueue(),
        capacity=CapacityTable(_limits={}, _defaults={"video": 1}),
        lanes=("video",),
    )

    with caplog.at_level(logging.INFO, logger="lib.generation_worker"):
        worker._log_pool_full_requeue("agnes", "video", "task-a")
        worker._log_pool_full_requeue("agnes", "video", "task-b")
        clock["now"] += _POOL_FULL_LOG_INTERVAL_SECONDS - 0.1
        worker._log_pool_full_requeue("agnes", "video", "task-c")
        worker._log_pool_full_requeue("ark", "video", "task-d")
        clock["now"] += 0.1
        worker._log_pool_full_requeue("agnes", "video", "task-e")

    messages = [r.getMessage() for r in caplog.records if "池满" in r.getMessage()]
    assert messages == [
        "供应商 agnes 的 video 池满，task task-a 回队等待下一 cycle",
        "供应商 ark 的 video 池满，task task-d 回队等待下一 cycle",
        "供应商 agnes 的 video 池满，task task-e 回队等待下一 cycle",
    ]


def test_should_auto_requeue_after_failure_for_transient_errors() -> None:
    from lib.generation_worker import should_auto_requeue_after_failure
    from lib.retry import NonRetryableError
    from lib.script_editor import ScriptEditError

    assert should_auto_requeue_after_failure(RuntimeError("boom"), {}) is True
    assert should_auto_requeue_after_failure(TimeoutError("timed out"), {"fail_count": 1}) is True
    assert should_auto_requeue_after_failure(RuntimeError("boom"), {"provider_job_id": "job-1"}) is False
    assert should_auto_requeue_after_failure(ScriptEditError("bad script"), {}) is False
    assert should_auto_requeue_after_failure(NonRetryableError("no"), {}) is False


def test_should_auto_requeue_after_failure_respects_generation_problem_action() -> None:
    from lib.generation_result import GenerationAction, GenerationProblem, encode_generation_problem
    from lib.generation_worker import should_auto_requeue_after_failure

    fix_input = encode_generation_problem(
        GenerationProblem(code="generation_refused", detail="资产名未登记", action=GenerationAction.FIX_INPUT)
    )
    assert should_auto_requeue_after_failure(RuntimeError(fix_input), {"fail_count": 3}) is False
    retry = encode_generation_problem(
        GenerationProblem(code="generation_task_failed", detail="provider 5xx", action=GenerationAction.RETRY)
    )
    assert should_auto_requeue_after_failure(RuntimeError(retry), {"fail_count": 3}) is True


def test_agnes_retry_after_is_thirty_seconds() -> None:
    from datetime import UTC, datetime

    from lib.generation_worker import retry_after_for_failed_provider
    from lib.providers import AGNES_RETRY_MIN_INTERVAL_SEC

    now = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    assert retry_after_for_failed_provider("ark", now=now) is None
    retry_after = retry_after_for_failed_provider("agnes", now=now)
    assert retry_after is not None
    assert (retry_after - now).total_seconds() == AGNES_RETRY_MIN_INTERVAL_SEC
