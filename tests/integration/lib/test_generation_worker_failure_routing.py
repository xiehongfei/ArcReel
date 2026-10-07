"""GenerationWorker 的失败路由：可重试失败回队、终态失败的编码与落库。"""

from datetime import UTC, datetime
from typing import Any

import pytest

from lib.generation_worker import GenerationWorker
from lib.script_editor import ScriptEditError

_EXECUTE = "server.services.generation_tasks.execute_generation_task"


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

    async def mark_task_cancelled(self, task_id, *, cancelled_by="user"):
        return 1


class TestGenerationWorkerFailureRouting:
    @pytest.mark.asyncio
    async def test_process_task_moves_to_back_after_two_retryable_failures(self, monkeypatch):
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise(_task, **_kwargs):
            raise TimeoutError("gateway timeout")

        monkeypatch.setattr(_EXECUTE, _raise)
        await worker._process_task({"task_id": "t-retry", "fail_count": 1})
        assert queue.requeued == [("t-retry", "gateway timeout", 2, True, None)]
        assert queue.failed == []

    @pytest.mark.asyncio
    async def test_process_task_agnes_failure_sets_thirty_second_retry_after(self, monkeypatch):
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise(_task, **_kwargs):
            raise TimeoutError("agnes busy")

        monkeypatch.setattr(_EXECUTE, _raise)
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
        worker = GenerationWorker(queue=queue)

        async def _raise(_task, **_kwargs):
            raise ScriptEditError("bad script", key="script_edit_error")

        monkeypatch.setattr(_EXECUTE, _raise)
        await worker._process_task({"task_id": "t-edit"})
        assert queue.failed
        assert queue.failed[0][0] == "t-edit"
        assert queue.requeued == []

    @pytest.mark.asyncio
    async def test_process_task_keeps_terminal_failure_when_provider_job_exists(self, monkeypatch):
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise(_task, **_kwargs):
            raise RuntimeError("poll failed")

        monkeypatch.setattr(_EXECUTE, _raise)
        await worker._process_task({"task_id": "t-job", "provider_job_id": "job-1"})
        assert queue.failed
        assert queue.failed[0][0] == "t-job"
        assert queue.requeued == []

    @pytest.mark.asyncio
    async def test_process_task_script_edit_error_encodes_key_and_params(self, monkeypatch):
        """apply_unit_video_assets 经异步任务队列（非 upload_unit_video 同步路由）抛出时，
        error_message 落成可翻译的 [key] {params} 结构而非 str(exc) 的固定中文，任务状态
        接口按 Accept-Language 渲染时才不会给 en/vi 用户漏出中文；params 一并落库才能在
        渲染侧还原成完整的翻译占位符替换（如 resolve_items 的 kind/type_name）。"""
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise_script_edit_error(_task):
            raise ScriptEditError(
                "segments 必须是列表，当前为 dict",
                key="script_edit_items_not_list",
                kind="segments",
                type_name="dict",
            )

        monkeypatch.setattr(_EXECUTE, _raise_script_edit_error)
        await worker._process_task({"task_id": "t_script_edit"})
        assert queue.failed
        assert queue.failed[0] == (
            "t_script_edit",
            '[script_edit_items_not_list] {"kind": "segments", "type_name": "dict"}',
        )

    @pytest.mark.asyncio
    async def test_process_task_script_edit_error_unregistered_key_falls_back(self, monkeypatch):
        """两份登记（errors.py 的翻译 key、task_failure.FAILURE_CODE_KEYS 的 worker 编码表）
        靠约定同步，非运行时校验——新 raise 点忘了同步登记时，encode_failure 对未登记 key
        抛 KeyError 不能打断 mark_task_failed，否则任务会卡在 running 而非落终态。"""
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise_unregistered(_task):
            raise ScriptEditError("尚未登记的错误", key="script_edit_not_yet_registered")

        monkeypatch.setattr(_EXECUTE, _raise_unregistered)
        await worker._process_task({"task_id": "t_unregistered"})
        assert queue.failed
        assert queue.failed[0] == ("t_unregistered", "[script_edit_error]")

    @pytest.mark.asyncio
    async def test_process_task_script_edit_error_circular_params_falls_back(self, monkeypatch):
        """params 含循环引用时 json.dumps 抛 ValueError（而非 TypeError）——同一条降级路径
        也要接住这个分支，否则序列化失败照样打断 mark_task_failed，任务卡在 running。"""
        queue = _RoutingQueue()
        worker = GenerationWorker(queue=queue)

        async def _raise_circular_params(_task):
            circular: dict[str, Any] = {}
            circular["self"] = circular
            raise ScriptEditError(
                "generated_assets 必须是 dict",
                key="script_edit_generated_assets_invalid",
                circular=circular,
            )

        monkeypatch.setattr(_EXECUTE, _raise_circular_params)
        await worker._process_task({"task_id": "t_circular"})
        assert queue.failed
        assert queue.failed[0] == ("t_circular", "[script_edit_error]")
