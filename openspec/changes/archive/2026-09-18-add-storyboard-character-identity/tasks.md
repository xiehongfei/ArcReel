## 1. 共享角色身份投影

- [x] 1.1 把宫格角色身份投影抽到 `lib/storyboard_character_identity.py`，宫格构建器与既有 `lib/grid/character_identity.py` 调用改为导入共享模块；运行 `uv run pytest tests/unit/lib/grid/test_grid_character_identity.py tests/unit/lib/grid/test_grid_prompt_builder.py` 确认宫格输出不变。
- [x] 1.2 抽出身份段与名单清单的共用渲染（单位名词可切换「格」/「镜」），宫格继续输出「本格角色」；运行 `uv run pytest tests/unit/lib/grid/test_grid_prompt_builder.py` 确认宫格字符串不变。

## 2. 普通分镜图提示词

- [x] 2.1 扩展 `render_storyboard_image_prompt` 接收 `character_context`，在 `Reference_Images` 与 `Scene` 之间插入 `【角色身份】` 与「本镜角色」清单；无角色时两段都不出现。更新 `tests/unit/lib/test_prompt_builders.py`，覆盖单人、多人、无角色、描述缺失与衍生描述拼接。
- [x] 2.2 实现普通分镜角色 mention 渲染为「角色名（图N）」、无实发槽位退化为角色名、非角色 mention 仍为「图N」；在 `tests/unit/lib/test_prompt_builders.py` 锁定与现有 `Reference_Images` 分组声明（含商品保真句）并存。
- [x] 2.3 更新 `storyboard/image` 模版槽位，使身份段与清单在预览转纯文本后不与 Style / Scene 叠行；用结构化与纯文本两种 `image_prompt` 各跑一条渲染断言。

## 3. 生成入口与视觉依据

- [x] 3.1 让 `execute_storyboard_task`、`preview_item_prompts` 和入队 `_build_prompt` 传入 `char_field` 与项目角色表并共享同一投影；运行 `uv run pytest tests/integration/server/services/test_prompt_preview.py tests/integration/server/media_tools/test_storyboards.py tests/integration/server/services/test_execute_generation_task.py` 中与分镜图提示词相关的用例，确认预览与正式生成的身份段、清单和图N一致。
- [x] 3.2 将 `artifact-visual/storyboard-image` 升到 `kind_version=2`，纳入规范化角色名单与描述；更新 `build_storyboard_image_visual_basis`、规划器与相关测试，验证改角色描述或出场名单会使分镜图变旧、只改视频动作不会。至少覆盖 `tests/integration/lib/test_visual_artifact_provenance.py`。
- [x] 3.3 图片编辑重建分镜图依据时省略身份上下文（空名单），确认编辑路径测试仍通过：`uv run pytest tests/integration/server/media_tools/test_image_edits.py tests/unit/server/services/test_image_edit_executor.py`。

## 4. 文档

- [x] 4.1 更新 `CONTEXT.md` 中分镜 `@[名称]` 释义：角色渲染为「角色名（图N）」，其他资产仍为「图N」。
- [x] 4.2 更新 `agent_runtime_profile/.claude/skills/generate-storyboard/SKILL.md` 的提示词示例，使其包含身份表、本镜清单和角色名（图N）。

## 5. 回归验证

- [x] 5.1 按 `CONTRIBUTING.md`「测试选择」运行相关测试，至少覆盖 `tests/unit/lib/test_prompt_builders.py`、`tests/unit/lib/grid/test_grid_prompt_builder.py`、`tests/integration/server/services/test_prompt_preview.py`、`tests/integration/lib/test_visual_artifact_provenance.py`，确认非零用例且全部通过。
- [x] 5.2 因测试文件发生修改，运行 `uv run python scripts/audit_tests.py --check` 并修复全部审计问题。
- [x] 5.3 运行后端受影响域全量闸门：`uv run ruff check . && uv run ruff format . && uv run basedpyright --warnings && uv run lint-imports && uv run deptry lib server alembic scripts tests && uv run python -m pytest -n 4 --dist loadfile`，确认全部通过。
