## 1. Agnes 出厂并发

- [x] 1.1 将 Agnes 注册表 `default_concurrency` 设为 `{"image": 1, "video": 1}`；在 `tests/unit/lib/config/test_config_registry_models.py` 断言出厂值，并更新 `tests/integration/lib/test_generation_worker_module.py` 中「未声明 image 回落到全局 5」的断言为图像默认 1、其他供应商出厂并发不变。

## 2. 共享轮询失败等待

- [x] 2.1 为 `poll_with_retry` 增加可选失败等待参数（未传入时保持 `interval × 2^k` 封顶 60 秒）；传入时对可重试错误使用该固定等待，合法且更长的 `Retry-After` 仍优先。在 `tests/unit/lib/video_backends/test_video_backend_base.py` 用伪造时钟验证：默认路径不变；传入 65 时 429/503 等待 65 秒而非 10 秒指数第一步。

## 3. Agnes 视频节奏

- [x] 3.1 在 Agnes 视频后端声明 10 秒轮询间隔与 65 秒可重试等待常量；创建成功后先等待 10 秒再进入 `poll_with_retry`，并将间隔与失败等待传入。用伪造时钟验证：创建成功后 10 秒才发出首次状态查询；进行中成功响应后再等 10 秒；状态查询 429 等待 65 秒。
- [x] 3.2 将 Agnes `_create_task` 与 `_query_video` 的 `with_retry_async` 退避改为 65 秒（尝试次数仍为 3）。在 `tests/unit/lib/video_backends/test_agnes_video_backend.py` 用伪造时钟与恒定 jitter 验证 429、503 等待 65 秒后才第二次提交；400/401 立即失败且不等待。

## 4. Agnes 图像节奏

- [x] 4.1 将 Agnes 图像 `_submit` 的可重试退避改为同一 65 秒常量。在 `tests/unit/lib/image_backends/test_agnes_image_backend.py` 用伪造时钟验证 429 等待 65 秒再提交、确定性 4xx 立即失败。

## 5. 回归

- [x] 5.1 运行相关测试选择，至少覆盖 `tests/unit/lib/config/test_config_registry_models.py`、`tests/integration/lib/test_generation_worker_module.py`、`tests/unit/lib/video_backends/test_video_backend_base.py`、`tests/unit/lib/video_backends/test_agnes_video_backend.py`、`tests/unit/lib/image_backends/test_agnes_image_backend.py`，确认非零用例且全部通过。
- [x] 5.2 因测试文件发生修改，运行 `uv run python scripts/audit_tests.py --check` 并修复全部审计问题。
- [x] 5.3 运行后端受影响域全量闸门：`uv run ruff check . && uv run ruff format . && uv run basedpyright --warnings && uv run lint-imports && uv run deptry lib server alembic scripts tests && uv run python -m pytest -n 4 --dist loadfile`，确认全部通过。
