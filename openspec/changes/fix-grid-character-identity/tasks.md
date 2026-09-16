## 1. 宫格角色语义投影

- [x] 1.1 在宫格领域实现确定性的角色身份投影，覆盖角色首次出镜排序、普通/衍生角色描述、逐格角色名单以及缺失定义降级；用单元测试验证描述来源、各一人约束和不臆造外貌。
- [x] 1.2 实现宫格专用角色 mention 渲染，角色输出为“名称（图N）”、未实际发送的参考图不产生编号、非角色引用保持现有图N行为；运行 `uv run pytest tests/unit/lib/grid/test_grid_prompt_builder.py` 验证。

## 2. 单时态宫格提示词

- [x] 2.1 将每个内容格改为只投影同序分镜的 `image_prompt`，删除前一分镜 `video_prompt.action` 拼接并同步帧链文案；用 2×2 满格、带占位格和末格场景验证逐格一一对应。
- [x] 2.2 在提示词中加入一次性全局角色身份段和逐格角色清单，验证单角色只出现一人、多角色各一人且明确禁止复制/融合/互换，并验证正文中已有空间关系原样保留。

## 3. 生成入口与视觉依据一致性

- [x] 3.1 更新 HTTP 宫格路由、媒体工具和正式任务执行器，统一传入剧本角色字段名及项目角色表；验证创建阶段可生成无图N身份提示词、正式阶段按实际参考图重建并覆盖带图N提示词。
- [x] 3.2 升级宫格正式视觉依据版本，纳入规范化角色名单与角色描述并移除视频动作依赖；更新执行器、产物补录规划器及相关测试，验证角色描述变化会使宫格变旧而单独修改视频动作不会。
- [x] 3.3 更新宫格执行和视觉产物集成测试，验证正式提示词与正式依据读取同一实时分镜、角色和参考输入，并确认既有宫格记录无需数据迁移仍可读取。

## 4. 回归验证

- [x] 4.1 运行相关测试选择，至少覆盖 `tests/unit/lib/grid/test_grid_prompt_builder.py`、`tests/unit/lib/test_grid_executor.py` 和 `tests/integration/lib/test_visual_artifact_provenance.py`，确认非零用例且全部通过。
- [x] 4.2 因测试文件发生修改，运行 `uv run python scripts/audit_tests.py --check` 并修复全部审计问题。
- [x] 4.3 运行后端受影响域全量闸门：`uv run ruff check . && uv run ruff format . && uv run basedpyright --warnings && uv run lint-imports && uv run deptry lib server alembic scripts tests && uv run python -m pytest -n 4 --dist loadfile`，确认全部通过。
