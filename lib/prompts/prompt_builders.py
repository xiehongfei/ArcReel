"""图像 / 视频 / 资产 prompt 的统一真相源。

WebUI（server/services/tasks/generation_tasks.py）和 Skill（agent_runtime_profile/.claude/skills/generate-assets）
都从这里取最终 prompt 文本，确保入口一致、不漂移。

资产图与分镜图的系统包装由内置模版渲染；本模块提供分镜图的渲染出口，把投影与「图N」编号作为槽位值装配。
反向提示词写在正文末尾的 Avoid 键，不使用 backend 的 negative_prompt 参数通道。
"""

from __future__ import annotations

from collections.abc import Sequence

from lib.prompts.prompt_style import normalize_style_value
from lib.prompts.prompt_templates.builtin import builtin_templates
from lib.prompts.prompt_utils import (
    image_prompt_to_yaml,
    project_storyboard_image_prompt,
    yaml_section,
)
from lib.prompts.reference_image_numbering import (
    REFERENCE_IMAGES_KEY,
    ReferenceImageSlot,
    reference_images_declaration,
)
from lib.storyboard_character_identity import CharacterContext
from lib.storyboard_character_prompt import (
    SHOT_ROSTER_UNIT,
    format_character_identities,
    format_character_roster,
    reference_character_names,
    render_character_mentions,
)


def _asset_prompt(asset_type: str, name: str, description: str, style: str = "", style_description: str = "") -> str:
    return builtin_templates.render(
        "asset/sheet",
        asset_type=asset_type,
        name=name,
        description=description,
        style=normalize_style_value(style),
        style_description=normalize_style_value(style_description),
    )


def build_character_prompt(name: str, description: str, style: str = "", style_description: str = "") -> str:
    """角色资产图（人脸特写 + 全身三视图，16:9）。"""
    return _asset_prompt("character", name, description, style, style_description)


def build_character_derivative_prompt(description: str) -> str:
    """只改描述到的外观，其余版式与外观保留本体资产图。"""
    return _asset_prompt("character_derivative", "", description)


def build_scene_prompt(name: str, description: str, style: str = "", style_description: str = "") -> str:
    """无人场景资产图。"""
    return _asset_prompt("scene", name, description, style, style_description)


def build_prop_prompt(name: str, description: str, style: str = "", style_description: str = "") -> str:
    """道具资产图。"""
    return _asset_prompt("prop", name, description, style, style_description)


def build_product_prompt(name: str, description: str, style: str = "", style_description: str = "") -> str:
    """忠实于实拍参考的商品资产图，风格变体为空。"""
    return _asset_prompt("product", name, description, style, style_description)


# ---------------------------------------------------------------------------
# 分镜图提示词渲染出口
# ---------------------------------------------------------------------------


def render_storyboard_edit_prompt(instruction: str, references: Sequence[ReferenceImageSlot]) -> str:
    """用实发参考图编号区分编辑底图与角色资产，不拼角色描述或原分镜提示词。"""
    if len(references) <= 1:
        return instruction
    return builtin_templates.render(
        "storyboard/edit",
        instruction=render_character_mentions(instruction, references, reference_character_names(references)),
        references=reference_images_declaration(references, include_logical_ids=True),
    )


def render_storyboard_image_prompt(
    image_prompt: object,
    *,
    style: str = "",
    style_description: str = "",
    references: Sequence[ReferenceImageSlot] = (),
    character_context: CharacterContext | None = None,
) -> str:
    """分镜图最终提示词文本的唯一出口。

    执行路径、Skill 入队校验与预览接口共用本函数：结构形态经项目风格投影为 YAML、文本形态原样
    作提示词主体，两者同样注入项目风格、参考图类型声明、角色身份约束与 ``Avoid`` 反向约束。
    ``references`` 是实际随请求发出的参考图列表（编排层最终装配序），其位置即「图N」编号：
    类型声明行 ``Reference_Images`` 插在风格块与 ``Scene`` 之间，角色 ``@[名称]`` 换成
    「角色名（图N）」、其他资产换成对应编号、对不上的渲染为裸名；没有参考图就没有声明行。
    商品参考图的保真要求并入声明行。``character_context`` 有角色时在声明与画面正文之间插入
    名称与参考图绑定、面部与头身比例保真要求及本镜清单，不注入角色资产描述。
    """

    context = character_context or CharacterContext(identities=(), cell_characters=())
    character_names = context.character_names | reference_character_names(references)
    identities = format_character_identities(context, references)
    roster = (
        format_character_roster(context.cell_characters[0], references, unit=SHOT_ROSTER_UNIT)
        if context.cell_characters
        else ""
    )

    projected, projected_style = project_storyboard_image_prompt(image_prompt, style)
    normalized_style = normalize_style_value(projected_style)
    normalized_description = normalize_style_value(style_description)
    declaration = reference_images_declaration(references)

    if isinstance(projected, dict):
        projected["scene"] = render_character_mentions(projected["scene"], references, character_names)
        return image_prompt_to_yaml(
            projected,
            normalized_style,
            reference_images=declaration,
            style_description=normalized_description,
            character_identities=identities,
            character_roster=roster,
        ).rstrip()
    return builtin_templates.render(
        "storyboard/image",
        style=normalized_style,
        style_description=normalized_description,
        reference_images=yaml_section({REFERENCE_IMAGES_KEY: declaration}) if declaration else "",
        character_identities=identities,
        character_roster=roster,
        structured_body="",
        text_body=render_character_mentions(projected, references, character_names),
    )
