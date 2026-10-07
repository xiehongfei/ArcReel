"""GenerationWorker 的失败路由：可重试失败回队、终态失败的编码与落库。"""

from datetime import UTC, datetime

import pytest

from lib.generation.generation_worker import GenerationWorker
from lib.script.script_editor import ScriptEditError
from tests.integration.lib.generation.worker_support import stub_executors


class _RoutingQueue:
    """只覆盖 _process_task 失败路由写入口的队列替身。"""

    def __init__(self):
        self.failed = []
        self.requeued = []

    async def mark_task_failed(self, task_id, error):
        self.failed.append((task_id, error))
        return 1

    async def requeue_after_failure(self, task_id, error, *, fail_count, to_back, retry_after=None):
        self.requeued.append((task_id, error, fail_count, to_back, retry_after))
        return 1

    async def mark_task_interrupted(self, task_id):
        return 1


def _worker(queue: _RoutingQueue) -> GenerationWorker:
    return GenerationWorker(queue=queue, executor=stub_executors.execute, resume_executor=stub_executors.execute_resume)


class TestGenerationWorkerFailureRouting:
    @pytest.mark.asyncio
    async def test_process_task_moves_to_back_after_two_retryable_failures(self, monkeypatch):
        queue = _RoutingQueue()
        worker = _worker(queue)

        async def _raise(_task, **_kwargs):
            raise TimeoutError("gateway timeout")

        monkeypatch.setattr(stub_executors, "generation", _raise)
        await worker._process_task({"task_id": "t-retry", "fail_count": 1})
        assert queue.requeued == [("t-retry", "gateway timeout", 2, True, None)]
        assert queue.failed == []

    @pytest.mark.asyncio
    async def test_process_task_agnes_failure_sets_thirty_second_retry_after(self, monkeypatch):
        queue = _RoutingQueue()
        worker = _worker(queue)

        async def _raise(_task, **_kwargs):
            raise TimeoutError("agnes busy")

        monkeypatch.setattr(stub_executors, "generation", _raise)
        before = datetime.now(UTC)
        await worker._process_task({"task_id": "t-agnes"}, claimed_provider_id="agnes")
        assert queue.failed == []
        task_id, error, fail_count, to_back, retry_after = queue.requeued[0]
        assert (task_id, error, fail_count, to_back) == ("t-agnes", "agnes busy", 1, False)
        assert retry_after is not None
        assert 29.5 <= (retry_after - before).total_seconds() <= 31

    @pytest.mark.asyncio
    async def test_process_task_keeps_terminal_failure_for_script_edit_error(self, monkeypatch):
        queue = _RoutingQueue()
        worker = _worker(queue)

        async def _raise(_task, **_kwargs):
            raise ScriptEditError("bad script", key="script_edit_error")

        monkeypatch.setattr(stub_executors, "generation", _raise)
        await worker._process_task({"task_id": "t-edit"})
        assert queue.failed
        assert queue.failed[0][0] == "t-edit"
        assert queue.requeued == []

    @pytest.mark.asyncio
    async def test_process_task_keeps_terminal_failure_when_provider_job_exists(self, monkeypatch):
        queue = _RoutingQueue()
        worker = _worker(queue)

        async def _raise(_task, **_kwargs):
            raise RuntimeError("poll failed")

        monkeypatch.setattr(stub_executors, "generation", _raise)
        await worker._process_task({"task_id": "t-job", "provider_job_id": "job-1"})
        assert queue.failed
        assert queue.failed[0][0] == "t-job"
        assert queue.requeued == []
