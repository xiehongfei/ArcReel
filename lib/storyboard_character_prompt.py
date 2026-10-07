"""Shared character identity and roster lines for storyboard and grid prompts."""

from __future__ import annotations

from collections.abc import Sequence

from lib.project.asset_types import asset_name_comparison_key
from lib.prompts.reference_image_numbering import ReferenceImageSlot, mention_replacements
from lib.script.reference_video.text_parser import render_mentions
from lib.storyboard_character_identity import CharacterContext

GRID_ROSTER_UNIT = "格"
SHOT_ROSTER_UNIT = "镜"


def reference_character_names(references: Sequence[ReferenceImageSlot]) -> frozenset[str]:
    return frozenset(
        asset_name_comparison_key(slot.logical_id)
        for slot in references
        if slot.logical_type == "character" and slot.logical_id
    )


def character_label(name: str, references: Sequence[ReferenceImageSlot]) -> str:
    reference = mention_replacements(references).get(name)
    return f"{name}（{reference}）" if reference else name


def render_character_mentions(
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


def append_character_identities(
    lines: list[str],
    context: CharacterContext,
    references: Sequence[ReferenceImageSlot],
) -> None:
    if not context.identities:
        return
    lines.append("【角色身份】")
    for identity in context.identities:
        label = character_label(identity.name, references)
        lines.append(f"- {label}")
    lines.append(
        "- 已绑定参考图的角色必须严格保持各自参考图中的脸型、眼形、眼距、鼻口比例、发际线和头身比例；"
        "面部、发型、体型、服装和配饰不得互换"
    )
    lines.append("")


def append_character_roster(
    lines: list[str],
    roster: tuple[str, ...],
    references: Sequence[ReferenceImageSlot],
    *,
    unit: str,
    indent: str = "",
) -> None:
    if not roster:
        return
    if unit == GRID_ROSTER_UNIT:
        labels = "、".join(character_label(name, references) for name in roster)
        lines.append(f"{indent}本格主体：{labels}。")
        lines.append(
            f"{indent}上述每个可见角色只出现一个独立主体，身份与外观不得复制、融合或互换；"
            "非人物设备按参考图呈现，不拟人化，设备阵列作为同一主体；仅发声而未在画面描述中出镜的角色不画成人物。"
        )
        return
    labels = "、".join(f"{character_label(name, references)}1人" for name in roster)
    lines.append(f"{indent}本{unit}角色：{labels}。")
    if len(roster) == 1:
        lines.append(f"{indent}本{unit}只出现上述角色1人，同一角色不得重复出现。")
    else:
        lines.append(f"{indent}本{unit}中上述角色各恰好1人，身份与外观不得复制、融合、替换或互换。")


def format_character_identities(
    context: CharacterContext,
    references: Sequence[ReferenceImageSlot],
) -> str:
    lines: list[str] = []
    append_character_identities(lines, context, references)
    return "\n".join(lines)


def format_character_roster(
    roster: tuple[str, ...],
    references: Sequence[ReferenceImageSlot],
    *,
    unit: str,
    indent: str = "",
) -> str:
    lines: list[str] = []
    append_character_roster(lines, roster, references, unit=unit, indent=indent)
    return "\n".join(lines)


__all__ = [
    "GRID_ROSTER_UNIT",
    "SHOT_ROSTER_UNIT",
    "append_character_identities",
    "append_character_roster",
    "character_label",
    "format_character_identities",
    "format_character_roster",
    "reference_character_names",
    "render_character_mentions",
]
