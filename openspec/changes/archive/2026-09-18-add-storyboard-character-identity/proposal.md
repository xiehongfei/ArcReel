## Why

普通分镜图把 `@[角色名]` 换成「图N」，只声明「图N为角色参考图」，不携带项目角色描述、本镜人数或禁止换脸的约束。多角色同框时模型要把身份完全从参考图猜出来，容易复制、融合或互换人物。宫格路径已经用身份表解决同一问题，普通分镜仍是默认重生入口，需要同一套约束。

## What Changes

- 普通分镜图提示词为该分镜引用字段中的角色补充四层约束：保留「角色名（图N）」、注入项目角色描述、列出本镜角色且各恰好一人、声明不得复制/融合/替换/互换身份。
- 角色 mention 渲染改为「角色名（图N）」；没有实发参考图时退化为角色名，不得虚构图N。场景、道具、商品 mention 仍按现有「图N」渲染。
- 分镜图正式视觉依据纳入规范化角色名单与角色描述，使修改角色描述或出场名单会让相关分镜图变旧。
- 预览、入队校验与正式执行共用同一套角色语义；不改变参考图选择、发送上限或剧本 `image_prompt` 原文。

## Capabilities

### New Capabilities

- `storyboard-image-prompting`: 规定普通分镜图提示词如何把角色名称、参考图、外貌描述和本镜人数绑定，并与正式产物视觉依据使用同一角色语义。

### Modified Capabilities

无。

## Impact

- 主要影响 `lib/prompt_builders.py` 的分镜图渲染出口、`lib/prompt_templates/templates/storyboard/image.md`，以及执行期 `server/services/generation_tasks.py`、预览 `server/services/prompt_preview.py`、入队校验 `server/media_tools/storyboards.py`。
- `lib/visual_artifact_provenance.py` 与 `lib/artifact_planner.py` 需把角色名单和描述纳入分镜图视觉依据；kind version 升级会使存量普通分镜图被判过期，须显式重生后才带新约束。
- 宫格已有同等约束，本变更将共享身份投影抽出以免两套描述来源分叉；宫格对外行为保持不变。
- 需更新 `CONTEXT.md` 中「`@[名称]` 一律换成图N」的释义（角色改为「角色名（图N）」），以及 `generate-storyboard` skill 示例。
- 不新增外部依赖，不改变 REST API、项目 JSON schema 或供应商后端。
