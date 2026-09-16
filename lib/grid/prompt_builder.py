"""Grid prompt builder for grid-image-to-video feature.

整段提示词由 ``storyboard/grid`` 模版渲染，本模块产出各格槽位值。
参考图与分镜图同一口径：prompt 首行为 ``Reference_Images`` 类型声明，各格正文里的 ``@[登记名]``
按最终参考图列表的序位换成「图N」（见 :mod:`lib.reference_image_numbering`）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import gcd

from lib.asset_types import asset_name_comparison_key
from lib.grid.character_identity import GridCharacterContext, project_grid_character_context
from lib.prompt_style import normalize_style_value
from lib.prompt_templates.builtin import builtin_templates
from lib.reference_image_numbering import (
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


def _extract_action(scene: dict) -> str:
    """Extract closing action from video_prompt.

    If dict, return action field. If string, return as-is.
    """
    video_prompt = scene.get("video_prompt")
    if video_prompt is None:
        return ""
    if isinstance(video_prompt, dict):
        return str(video_prompt.get("action", ""))
    return str(video_prompt)


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
    style_description: str,
    aspect_ratio: str = "16:9",
    grid_aspect_ratio: str | None = None,
    references: Sequence[ReferenceImageSlot] = (),
    char_field: str | None = None,
    characters: object = None,
    character_context: GridCharacterContext | None = None,
) -> str:
    """Render the grid image prompt with first-last frame chain structure.

    Args:
        scenes: List of scene dicts with image_prompt and video_prompt fields.
        id_field: Key in each scene dict for the scene ID.
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        style: Project style.
        style_description: Project style description.
        aspect_ratio: Aspect ratio for each cell (default "16:9").
        references: The reference images sent with the request, in array order.
        char_field: Storyboard field containing the character roster for each cell.
        characters: Project character definitions used as identity descriptions.
        character_context: Precomputed identity projection shared with formal provenance.

    Returns:
        The prompt rendered from the ``storyboard/grid`` template.
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
    first = scenes[0]

    def _roster(idx: int) -> str:
        roster_lines: list[str] = []
        _append_cell_roster(roster_lines, character_context.cell_characters[idx], references)
        return "\n".join(roster_lines)

    transitions = [
        {
            **_cell_position(idx, cols),
            "from_id": str(scenes[idx - 1].get(id_field, "")),
            "to_id": str(scenes[idx].get(id_field, "")),
            "action": _render_grid_mentions(_extract_action(scenes[idx - 1]), references, character_names),
            "description": _extract_image_desc(scenes[idx], references, character_names),
            "roster": _roster(idx),
        }
        for idx in range(1, n_scenes)
    ]
    placeholders = [_cell_position(idx, cols) for idx in range(n_scenes, total)]

    identity_lines: list[str] = []
    _append_character_identities(identity_lines, character_context, references)
    character_identities = "\n".join(identity_lines)

    return builtin_templates.render(
        "storyboard/grid",
        reference_images=reference_images_declaration(references, include_logical_ids=True) or None,
        rows=rows,
        cols=cols,
        cell_count=total,
        grid_aspect_ratio=effective_grid_ar,
        panel_aspect_ratio=_compute_panel_aspect(effective_grid_ar, rows, cols),
        last_chain_cell=n_scenes - 1,
        opening={
            "scene_id": str(first.get(id_field, "")),
            "description": _extract_image_desc(first, references, character_names),
            "roster": _roster(0),
        },
        transitions=transitions,
        placeholders=placeholders,
        style=normalize_style_value(style),
        style_description=normalize_style_value(style_description),
        character_identities=character_identities,
    )


def _cell_position(index: int, cols: int) -> dict[str, int]:
    return {"index": index, "row": index // cols + 1, "col": index % cols + 1}
