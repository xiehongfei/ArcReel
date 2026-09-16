"""Grid prompt builder for grid-image-to-video feature.

参考图与分镜图同一口径：prompt 首行为 ``Reference_Images`` 类型声明，各格正文里的 ``@[登记名]``
按最终参考图列表的序位换成「图N」（见 :mod:`lib.reference_image_numbering`）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import gcd

from lib.asset_types import asset_name_comparison_key
from lib.grid.character_identity import GridCharacterContext, project_grid_character_context
from lib.reference_image_numbering import (
    REFERENCE_IMAGES_KEY,
    ReferenceImageSlot,
    mention_replacements,
    reference_images_declaration,
)
from lib.reference_video.text_parser import render_mentions


def pending_grid_prompt_ids(scenes: Sequence[Mapping[str, object]], id_field: str) -> list[str]:
    """一张联合图里提示词待生成（``None``）或为空的格子 id，按剧本顺序。

    联合图的提示词由每格的 ``image_prompt`` 拼成，任一格缺失整张图都出不了；REST 路由与
    Agent 工具在入队计费前共用这一判定。
    """

    return [str(scene.get(id_field)) for scene in scenes if not scene.get("image_prompt")]


def project_grid_image_prompt(image_prompt: object) -> str | dict[str, object]:
    """Project grid image semantics into the canonical provider/basis shape.

    ``None`` 是机械转换后的待生成态，没有可渲染、可取证的内容，与
    :func:`lib.prompt_utils.project_storyboard_image_prompt` 同样拒绝，不能变成字面量 ``"None"``。
    """

    if image_prompt is None:
        raise ValueError("grid image_prompt is pending; the cell has no prompt to render")
    if not isinstance(image_prompt, Mapping):
        return str(image_prompt)
    scene = image_prompt.get("scene")
    if scene is None:
        scene = ""
    if not isinstance(scene, str):
        raise ValueError("grid image_prompt.scene must be a string")
    raw_composition = image_prompt.get("composition")
    if raw_composition is None:
        raw_composition = {}
    if not isinstance(raw_composition, Mapping):
        raise ValueError("grid image_prompt.composition must be an object")
    if any(not isinstance(key, str) for key in raw_composition):
        raise ValueError("grid image_prompt.composition keys must be strings")
    composition: dict[str, str] = {}
    for key in sorted(raw_composition):
        raw_value = raw_composition[key]
        if raw_value is None:
            continue
        value = str(raw_value)
        if value:
            composition[key] = value
    return {"scene": scene, "composition": composition}


def _render_grid_mentions(
    text: str,
    references: Sequence[ReferenceImageSlot],
    character_names: frozenset[str],
) -> str:
    replacements = mention_replacements(references)

    def _replacement(name: str) -> str:
        reference = replacements.get(name)
        if name in character_names:
            return f"{name}（{reference}）" if reference else name
        return reference or name

    return render_mentions(text, _replacement)


def _extract_image_desc(
    scene: dict,
    references: Sequence[ReferenceImageSlot] = (),
    character_names: frozenset[str] = frozenset(),
) -> str:
    """Extract image description from a scene.

    If image_prompt is a dict, join scene + composition fields.
    If string, return as-is. Character mentions retain their logical name alongside 图N.
    """
    image_prompt = project_grid_image_prompt(scene.get("image_prompt", ""))
    if isinstance(image_prompt, str):
        return _render_grid_mentions(image_prompt, references, character_names)
    parts: list[str] = []
    scene_text = image_prompt["scene"]
    if scene_text:
        parts.append(_render_grid_mentions(str(scene_text), references, character_names))
    composition = image_prompt["composition"]
    if isinstance(composition, Mapping):
        comp_parts = [f"{key}: {value}" for key, value in composition.items()]
        if comp_parts:
            parts.append("，".join(comp_parts))
    return "；".join(parts) if parts else ""


def _reference_character_names(references: Sequence[ReferenceImageSlot]) -> frozenset[str]:
    return frozenset(
        asset_name_comparison_key(slot.logical_id)
        for slot in references
        if slot.logical_type == "character" and slot.logical_id
    )


def _character_label(name: str, references: Sequence[ReferenceImageSlot]) -> str:
    reference = mention_replacements(references).get(name)
    return f"{name}（{reference}）" if reference else name


def _append_character_identities(
    lines: list[str],
    context: GridCharacterContext,
    references: Sequence[ReferenceImageSlot],
) -> None:
    if not context.identities:
        return
    lines.append("【角色身份】")
    for identity in context.identities:
        label = _character_label(identity.name, references)
        suffix = f"：{identity.description}" if identity.description else ""
        lines.append(f"- {label}{suffix}")
    lines.append("- 各角色必须忠实于各自身份说明与参考图，面部、发型、体型、服装和配饰不得互换")
    lines.append("")


def _append_cell_roster(
    lines: list[str],
    roster: tuple[str, ...],
    references: Sequence[ReferenceImageSlot],
) -> None:
    if not roster:
        return
    labels = "、".join(f"{_character_label(name, references)}1人" for name in roster)
    lines.append(f"  本格角色：{labels}。")
    if len(roster) == 1:
        lines.append("  本格只出现上述角色1人，同一角色不得重复出现。")
    else:
        lines.append("  本格中上述角色各恰好1人，身份与外观不得复制、融合、替换或互换。")


def _compute_panel_aspect(grid_aspect_ratio: str, rows: int, cols: int) -> str:
    """从整体宫格比例推算单格比例。

    例：grid 4:3, 3行2列 → panel (4/2):(3/3) = 2:1
    """
    gw, gh = (int(x) for x in grid_aspect_ratio.split(":"))
    pw = gw * rows  # 交叉相乘避免浮点
    ph = gh * cols
    g = gcd(pw, ph)
    return f"{pw // g}:{ph // g}"


def build_grid_prompt(
    *,
    scenes: list[dict],
    id_field: str,
    rows: int,
    cols: int,
    style: str,
    aspect_ratio: str = "16:9",
    grid_aspect_ratio: str | None = None,
    references: Sequence[ReferenceImageSlot] = (),
    char_field: str | None = None,
    characters: object = None,
    character_context: GridCharacterContext | None = None,
) -> str:
    """Assemble one static opening image per storyboard item into a grid prompt.

    Args:
        scenes: List of scene dicts with image_prompt and video_prompt fields.
        id_field: Key in each scene dict for the scene ID.
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        style: Style description for the grid.
        aspect_ratio: Aspect ratio for each cell (default "16:9").
        references: The reference images sent with the request, in array order.
        char_field: Storyboard field containing the character roster for each cell.
        characters: Project character definitions used as identity descriptions.
        character_context: Precomputed identity projection shared with formal provenance.

    Returns:
        Assembled prompt string.
    """
    total = rows * cols
    n_scenes = len(scenes)
    if n_scenes > total:
        # 超员场景在成图中没有对应画格，切格回填会按位置错配——调用方应先按
        # max_cell_count 切块（见 lib.grid.layout.plan_grid_chunks），此处 fail loud。
        raise ValueError(f"分镜数 {n_scenes} 超过 {rows}×{cols} 宫格的画格数 {total}，分组应先切块再构建 prompt")

    character_context = character_context or project_grid_character_context(
        scenes, char_field=char_field, characters=characters
    )
    if len(character_context.cell_characters) != n_scenes:
        raise ValueError("grid character context must contain one roster per scene")
    character_names = character_context.character_names | _reference_character_names(references)

    effective_grid_ar = grid_aspect_ratio or aspect_ratio
    panel_ar = _compute_panel_aspect(effective_grid_ar, rows, cols)

    lines: list[str] = []

    declaration = reference_images_declaration(references, include_logical_ids=True)
    if declaration:
        lines.append(f"{REFERENCE_IMAGES_KEY}: {declaration}")
        lines.append("")

    # Header
    lines.append(
        f"你是一位专业的分镜画师。请严格按照 {rows}×{cols} 宫格布局生成一张包含恰好 {total} 个等大画格的联合图。"
    )
    lines.append("")

    # Layout requirements
    lines.append("【布局要求】")
    lines.append(f"- 恰好 {rows} 行 {cols} 列，共 {total} 个画格，阅读顺序：从左到右，从上到下")
    lines.append(f"- 整体图片比例：{effective_grid_ar}")
    lines.append(f"- 每个画格比例：{panel_ar}，所有画格大小完全相同")
    lines.append("- 画格之间无边框、无间隙、无留白，紧密排列")
    lines.append("- 不得合并画格、不得遗漏画格、不得错位排列")
    lines.append("- 同一角色在所有出镜画格中的面部、发型、体型、服装和配饰保持一致")
    lines.append("- 同一场景在所有画格中的空间结构、主要陈设和固定物件保持一致")
    lines.append("- 同一道具在所有画格中的形状、材质和标志性细节保持一致")
    lines.append("- 所有内容画格保持统一的色彩与渲染风格；光线按各格描述变化，相邻格之间自然连续")
    lines.append("")

    _append_character_identities(lines, character_context, references)

    # Frame chain rhythm
    lines.append("【帧链节奏】")
    lines.append("本宫格采用首尾帧链式结构：")
    lines.append("- 每个内容格只描绘对应场景 image_prompt 定义的一个静态时刻")
    lines.append("- 格0 是第一个场景的开场静态画面")
    if n_scenes > 1:
        lines.append(f"- 格1~格{n_scenes - 1} 分别是对应后续场景的开场静态画面，同时作为前一场景的结束共享帧")
    lines.append("- 不得在同一画格中并列绘制动作前后、过渡过程或同一角色的多个时间点")
    lines.append("")

    # Cell contents
    lines.append("【各格内容】")

    for cell_idx in range(total):
        row_num = cell_idx // cols + 1
        col_num = cell_idx % cols + 1
        position = f"row{row_num} col{col_num}"

        if cell_idx == 0:
            # First scene opening
            scene = scenes[0]
            scene_id = scene.get(id_field, "")
            image_desc = _extract_image_desc(scene, references, character_names)
            lines.append(f"格{cell_idx}（{position}）— {scene_id}开场：")
            _append_cell_roster(lines, character_context.cell_characters[cell_idx], references)
            lines.append(f"  {image_desc}")

        elif cell_idx < n_scenes:
            # Shared frame: render only the next scene's opening state.
            prev_scene = scenes[cell_idx - 1]
            next_scene = scenes[cell_idx]
            prev_scene_id = prev_scene.get(id_field, "")
            next_scene_id = next_scene.get(id_field, "")
            next_image_desc = _extract_image_desc(next_scene, references, character_names)
            lines.append(f"格{cell_idx}（{position}）— {prev_scene_id}→{next_scene_id}共享帧（{next_scene_id}开场）：")
            _append_cell_roster(lines, character_context.cell_characters[cell_idx], references)
            lines.append(f"  {next_image_desc}")

        else:
            # Placeholder
            lines.append(f"格{cell_idx}（{position}）— 空占位：中性灰填满这个画格，无人物、物件或文字")

    lines.append("")

    # Style requirements
    lines.append("【风格要求】")
    lines.append(style)
    lines.append("")

    # Negative constraints
    lines.append("【画面约束】")
    lines.append("- 仅呈现各格内容明确要求的画内文字；不添加字幕、标签、标题、数字编号或时间戳")
    lines.append("- 水印、logo、签名")
    lines.append("- 白色边框、黑色边框、粗边框、装饰性边框")
    lines.append("- 分隔线、间隙、间距、留白、padding、margin")
    placeholder_exception = "；明确指定为中性灰的画格除外" if n_scenes < total else ""
    lines.append(f"- 内容画格之间不出现白色或纯色背景条{placeholder_exception}")
    lines.append("- 合并的画格、缺失的画格、错位的画格")
    lines.append("- 连续全景图（非分格）、单张大图")
    lines.append("- 模糊、低画质、噪点")
    lines.append("- 内容画格内部不出现二次分栏、照片拼贴或蒙太奇叠片")
    lines.append("- 画格大小不一致、画格比例不一致")

    return "\n".join(lines)
