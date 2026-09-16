## Why

Agnes 免费账户的 RPM 上限为 20，官方对 429 的建议是「等待 1 分钟后重试、控制并发、降低轮询与自动重试频率」。当前实现与此冲突：视频提交后默认每 5 秒轮询一次；create 在 503/429 上按 2s / 4s / 8s 退避重试；图像 lane 仍走全局默认 5 并发。实测日志中，一次 503 后约 2.7s、5.3s 连续重试，第三次即 429 并把整条视频任务打成终态失败。

## What Changes

- Agnes **图像与视频** lane 出厂并发改为 1，同一 lane 同一时刻只向 Agnes 提交一条生成任务（视频 lane 已是 1；图像从全局默认 5 收口）。
- Agnes **视频状态轮询**间隔改为 10 秒：创建成功后先等 10 秒再首次查询；之后每次成功的进行中响应后再等 10 秒查下一次。
- Agnes **提交 / 轮询 / 成片查询**遇到可重试 HTTP 失败（含 429、503 及同类 5xx/408）后，等待 **1 分 05 秒**再重试，不再使用全局 2/4/8 秒退避。
- 上述节奏只作用于 Agnes 后端，不改其他供应商的默认并发、轮询或重试。

## Capabilities

### New Capabilities

- `agnes-request-pacing`: Agnes 生成请求的并发上限、任务状态轮询间隔，以及 429/503 等可重试失败的等待节奏。

### Modified Capabilities

- （无。主规格库尚无已归档能力。）

## Impact

- `lib/config/registry.py`：Agnes `default_concurrency` 增加 `image: 1`，与现有 `video: 1` 并列。
- `lib/generation_worker.py` 的容量装载会吃到新的图像默认；用户若已在设置页把 Agnes `image_max_workers` / `video_max_workers` 配成大于 1，仍会覆盖出厂值。
- `lib/video_backends/agnes.py`、`lib/image_backends/agnes.py`：提交与查询重试等待；视频 `poll_with_retry` 间隔与失败等待。
- `lib/retry.py` / `lib/video_backends/base.py` 的全局默认不变；若为 Agnes 失败等待需要可注入的等待策略，只加可选参数，不改其他供应商行为。
- 测试：registry 并发、Agnes 图像/视频重试等待、Agnes 视频轮询间隔；相关 backend 单测。
- 无对外 HTTP API 变更；用户可见效果是 Agnes 任务排队更慢、少因 429 直接失败。
