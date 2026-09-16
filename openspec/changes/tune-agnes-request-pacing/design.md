## Context

见 `proposal.md` 的动机。当前约束：

- 生成 worker 按 `provider_id × media_type` 占槽。Agnes 注册表已声明 `default_concurrency={"video": 1}`，图像 lane 未声明，回落到全局 `IMAGE_MAX_WORKERS`（默认 5）。用户在设置页填写的 `image_max_workers` / `video_max_workers` 会覆盖出厂值。
- 视频提交与图像提交都走 `with_retry_async` + `should_retry_submit`，默认 `backoff_seconds=(2, 4, 8)` 外加 0–2 秒抖动。日志里 503 后约 2.7s / 5.3s 再打，第三次 429 把任务打成终态失败。
- 视频状态查询走共享 `poll_with_retry`，成功间隔默认 `VIDEO_POLL_INTERVAL_SECONDS = 5`；失败退避为 `interval × 2^k`，封顶 `VIDEO_POLL_MAX_BACKOFF_SECONDS = 60`。轮询计入同一账户 RPM。
- 成片二次查询 `_query_video` 另套一层 `with_retry_async`，同样是 2/4/8。
- 文本 lane 全局并发为 1，且走 OpenAI 兼容文本后端的独立重试；本次不改文本路径。

官方 429 说明：免费用户 RPM 20；等待 1 分钟后重试；控制并发；降低自动重试频率。本设计取 65 秒，略长于「1 分钟」以免卡在整分钟窗口边缘。

## Goals / Non-Goals

**Goals:**

- 出厂状态下 Agnes 图像与视频各 lane 串行提交。
- Agnes 视频成功轮询间隔固定 10 秒；创建成功后先等 10 秒再首查，之后每次进行中成功响应再等 10 秒。
- Agnes 图像/视频的可重试 HTTP 失败（含 429、503）等待 65 秒再打，与全局短退避隔离。
- 改动可测：时钟与抖动可注入，断言等待时长而不是墙钟睡眠。

**Non-Goals:**

- 不引入跨 lane 全局互斥（图像任务与视频任务仍可各占 1 槽并行）。文本生成也不并入该互斥。
- 不禁止用户在设置页把 Agnes `*_max_workers` 调高于 1；出厂值负责默认串行。
- 不按账户套餐动态探测 RPM，不读取 Token Plan。
- 不修改其他供应商的默认并发、轮询间隔或重试退避。
- 不把 429 从「任务失败」改成队列级延迟调度；重试仍发生在当前任务执行体内。
- 不改变 `submit_post` 对歧义传输错误的终态失败语义。

## Decisions

### 1. 只改 Agnes 注册表的 lane 出厂并发，不新增跨供应商锁

把 Agnes `default_concurrency` 设为 `{"image": 1, "video": 1}`。容量装载已有「注册表声明 → 否则全局默认 → 用户配置覆盖」三层，图像收口只需补声明。

不采用跨 lane 单槽：那要改 `CapacityTable` / `SlotTable` 的键空间，影响所有供应商装载路径，而本次故障是同 lane 视频提交重试过密叠加轮询 RPM。lane 内串行加上 10 秒轮询已把单任务稳态查询压到每分钟 6 次。

### 2. Agnes 专用节奏常量，不改全局默认

在 Agnes 视频（及图像提交共用处）声明：

- 成功轮询间隔：10 秒
- 可重试失败等待：65 秒
- 提交最大尝试次数保持现有 3 次

创建成功后，Agnes 先按同一 10 秒间隔等待，再进入 `poll_with_retry(..., poll_interval=10)`。共享辅助仍是「先查再等」，首查延迟放在进入循环之前，避免改所有供应商的「立即首查」。提交与成片查询的 `with_retry_async` 把 `backoff_seconds` 换成 `(65, 65)`，不再用 `(2, 4, 8)`。

保留现有 0–2 秒抖动：相对 65 秒可忽略，且避免多任务在整秒边界对齐；测试注入恒定 jitter。

### 3. 轮询失败等待与提交失败对齐为 65 秒

共享 `poll_with_retry` 的指数退避封顶是 60 秒，无法表达 65 秒，且第一次 429 只会等 10 秒。因此为 `poll_with_retry` 增加可选失败等待（例如 `retry_wait_seconds`）：传入时，可重试异常忽略指数退避，等待该值（若响应带合法 `Retry-After` 且更长则仍优先 `Retry-After`）。默认 `None`，其他供应商行为不变。

Agnes 传入 65。不把全局封顶从 60 改成 65，以免放宽所有供应商的失败退避。

### 4. 可重试判定沿用现有 HTTP 闸门

`should_retry_submit` / `should_retry_poll` 已经按 status code 区分 5xx/408/425/429 与确定性 4xx。本次只改等待，不放宽或收紧重试集合。400/401 等仍立即失败。

图像 `_submit` 与视频 `_create_task` / `_query_video` 使用同一套 65 秒退避，避免图像 429 把随后的视频提交打爆同一 RPM 窗口。

### 5. 用户覆盖并发仍然有效

设置页已暴露 Agnes 的 `image_max_workers` / `video_max_workers`。强制忽略用户配置会与 ADR 0043 的「用户契约面是 ≥1 的整数或留空」冲突。出厂串行满足「默认不并发」；若用户主动调高，自行承担 429 风险。实现不必写回或迁移已保存的大于 1 的值。

## Risks / Trade-offs

- [单任务变慢] 轮询从 5 秒改为 10 秒，且首查也推迟 10 秒；完成检测相对现状最多多延迟约 10 秒 → 可接受；生成本身通常数分钟。
- [失败后阻塞 worker 槽] 65 秒重试期间仍占用该 lane 的唯一槽 → 这是有意的：立刻放行下一条会继续打满 RPM。最多约 2 次等待（3 次尝试）。
- [图像与视频仍可能并行] 两 lane 各 1 会同时打 Agnes → 若仍出现 429，后续再考虑跨 lane 互斥；本次不预先做。
- [用户已配置 image_max_workers>1] 出厂声明不覆盖已有配置 → 在设计中明确；需要串行时手动改回 1。
- [测试时长] 必须用伪造时钟，禁止真实 sleep 65 秒。

## Migration Plan

- 无数据迁移、无 schema 变更。
- 部署后新进程按新注册表装载 Agnes 图像默认 1；已写入 DB 的 worker 覆盖值保持原样。
- 回滚：恢复注册表与 Agnes 后端等待参数即可。
