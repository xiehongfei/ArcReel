from pathlib import Path

import pytest

from lib.prompt_builders import (
    build_character_derivative_prompt,
    build_character_prompt,
    build_product_prompt,
    build_prop_prompt,
    build_scene_prompt,
    render_storyboard_image_prompt,
)
from lib.reference_image_numbering import PREVIOUS_STORYBOARD_ROLE
from lib.storyboard_character_identity import project_character_context
from lib.visual_artifact_provenance import VisualReference


class TestCharacterPrompt:
    def test_includes_supplied_character_details(self):
        prompt = build_character_prompt(
            "姜月茴",
            "黑发，冷静神态。",
            style="古风",
            style_description="Cinematic, low-key lighting",
        )
        assert "姜月茴" in prompt
        assert "黑发，冷静神态。" in prompt
        assert "Style: 古风" in prompt
        assert "Visual style: Cinematic, low-key lighting" in prompt
        assert prompt.endswith("Avoid: 水印、多余文字、Logo")
        assert "Cinematic, low-key lighting" in prompt

    def test_layout_is_face_closeup_plus_full_body_turnaround(self):
        prompt = build_character_prompt("张三", "短发青年")
        assert "人脸特写" in prompt
        assert "全身三视图" in prompt
        assert "正面" in prompt
        assert "正侧" in prompt
        assert "背面" in prompt


class TestCharacterDerivativePrompt:
    def test_preserves_closeup_plus_full_body_turnaround_layout(self):
        prompt = build_character_derivative_prompt("换上黑色重甲")
        assert "换上黑色重甲" in prompt
        assert "人脸特写" in prompt
        assert "全身三视图" in prompt
        assert "正面" in prompt
        assert "正侧" in prompt
        assert "背面" in prompt


class TestScenePromptAndPropPrompt:
    def test_prop_includes_supplied_details(self):
        prompt = build_prop_prompt("玉佩", "古朴温润")
        assert "玉佩" in prompt
        assert "古朴温润" in prompt

    def test_scene_includes_supplied_details(self):
        prompt = build_scene_prompt("祠堂", "昏暗古朴")
        assert "祠堂" in prompt
        assert "昏暗古朴" in prompt

    def test_empty_prop_guard_does_not_add_a_blank_paragraph(self):
        assert "\n\n\n" not in build_prop_prompt("玉佩", "古朴温润")


class TestFigureExclusion:
    """展示环境或物件的图种排除人物；画面主体本身是人物的图种不排除。"""

    # 断言完整片段而非「人物」二字：正文里的普通描述也可能出现该词，按关键词断言会误判。
    _EXCLUSION = "Avoid: 出镜人物"

    def test_environment_and_object_sheets_exclude_people(self):
        assert self._EXCLUSION in build_scene_prompt("祠堂", "昏暗古朴")
        assert self._EXCLUSION in build_prop_prompt("玉佩", "古朴温润")
        assert self._EXCLUSION in build_product_prompt("护手霜", "白色管装，哑光质感")

    def test_exclusion_survives_a_description_that_repeats_it(self):
        prompt = build_scene_prompt("祠堂", "昏暗古朴，无出镜人物、无声响。")
        assert prompt.endswith("Avoid: 出镜人物、水印、多余文字、Logo")

    def test_character_and_storyboard_keep_people(self):
        assert self._EXCLUSION not in build_character_prompt("张三", "短发青年")
        assert self._EXCLUSION not in render_storyboard_image_prompt("林清坐在窗边木桌前")


class TestStoryboardImageAvoidLine:
    def test_text_form_ends_with_one_image_avoid_line(self):
        assert (
            render_storyboard_image_prompt("林清坐在窗边木桌前") == "林清坐在窗边木桌前\n\nAvoid: 水印、多余文字、Logo"
        )

    def test_idempotent(self):
        once = render_storyboard_image_prompt("林清坐在窗边木桌前")
        assert render_storyboard_image_prompt(once) == once


def _sheet(asset_type: str, name: str) -> VisualReference:
    return VisualReference(
        path=Path(f"{name}.png"), role="asset_sheet", logical_type=asset_type, logical_id=name, kind="sheet"
    )


_PREVIOUS = VisualReference(
    path=Path("prev.png"), role=PREVIOUS_STORYBOARD_ROLE, logical_type="storyboard", logical_id="E1S02"
)

_SCENE = (
    "@[林清]坐在窗边木桌前，目光落在信纸上；@[沈茹/黑化]立在门口的阴影里。"
    "桌面摊着一只褪色的@[怀表]，@[林家老宅·书房]的木格窗棂外雨丝密集。"
)
_STRUCTURED = {
    "scene": _SCENE,
    "composition": {"shot_type": "Medium Shot", "lighting": "右侧落地窗逆光，蓝灰色调", "ambiance": "雨天，室内昏暗"},
}


class TestRenderStoryboardImagePrompt:
    """图N 编号由实际发出的参考图列表机械派生，对全部图像后端同一口径。"""

    @pytest.mark.parametrize("prompt", [_STRUCTURED, _SCENE])
    def test_both_forms_share_style_block_and_wrappers_survive_text_roundtrip(self, prompt):
        references = [_sheet("character", "林清")]
        rendered = render_storyboard_image_prompt(
            prompt, style="Anime", style_description="cinematic", references=references
        )
        assert rendered.startswith("Style: Anime\nVisual style: cinematic\nReference_Images:")
        assert (
            render_storyboard_image_prompt(
                rendered, style="Anime", style_description="cinematic", references=references
            )
            == rendered
        )
        for label in ("Style:", "Visual style:", "Reference_Images:", "Avoid:"):
            assert rendered.count(label) == 1

    def test_structured_prompt_declares_types_between_style_and_scene_and_numbers_mentions(self):
        references = [
            _sheet("character", "林清"),
            _sheet("character", "沈茹/黑化"),
            _sheet("scene", "林家老宅·书房"),
            _PREVIOUS,
        ]
        rendered = render_storyboard_image_prompt(_STRUCTURED, style="电影感写实，冷色调", references=references)
        assert rendered == (
            "Style: 电影感写实，冷色调\n"
            "Reference_Images: 图1、图2为角色参考图；图3为场景参考图；图4为上一分镜图，只参考构图与色调。\n"
            "Scene: 林清（图1）坐在窗边木桌前，目光落在信纸上；沈茹/黑化（图2）立在门口的阴影里。"
            "桌面摊着一只褪色的怀表，图3的木格窗棂外雨丝密集。\n"
            "Composition:\n"
            "  shot_type: Medium Shot\n"
            "  lighting: 右侧落地窗逆光，蓝灰色调\n"
            "  ambiance: 雨天，室内昏暗\n"
            "Avoid: 水印、多余文字、Logo"
        )

    def test_product_images_lead_the_numbering_and_replace_the_fidelity_tail(self):
        references = [
            VisualReference(
                path=Path("p.png"), role="asset_sheet", logical_type="product", logical_id="保温杯", kind="sheet"
            ),
            VisualReference(
                path=Path("o.jpg"), role="source", logical_type="product", logical_id="保温杯", kind="original"
            ),
            _sheet("character", "Alice"),
        ]
        rendered = render_storyboard_image_prompt(
            {
                "scene": "@[Alice]手持@[保温杯]特写",
                "composition": {"shot_type": "Close-up", "lighting": "", "ambiance": ""},
            },
            style="Anime",
            references=references,
        )
        assert "Reference_Images: 图1、图2为商品参考图，画面中的商品须与之完全一致；图3为角色参考图。\n" in rendered
        assert "Scene: Alice（图3）手持图1特写\n" in rendered
        assert "商品高保真还原" not in rendered

    def test_mentions_without_a_reference_image_render_as_bare_names(self):
        rendered = render_storyboard_image_prompt(_STRUCTURED, style="Anime", references=[_sheet("character", "林清")])
        assert "Reference_Images: 图1为角色参考图。\n" in rendered
        assert (
            "Scene: 林清（图1）坐在窗边木桌前，目光落在信纸上；沈茹/黑化立在门口的阴影里。桌面摊着一只褪色的怀表，林家老宅·书房的"
            in rendered
        )

    def test_without_references_there_is_no_declaration_and_mentions_stay_bare(self):
        rendered = render_storyboard_image_prompt(_STRUCTURED, style="Anime")
        assert "Reference_Images" not in rendered
        assert "Scene: 林清坐在窗边木桌前" in rendered

    def test_text_form_gets_the_same_declaration_and_replacement(self):
        references = [_sheet("character", "林清"), _PREVIOUS]
        rendered = render_storyboard_image_prompt(
            "@[林清]坐在窗边木桌前", style="Anime", style_description="cinematic", references=references
        )
        assert rendered == (
            "Style: Anime\n"
            "Visual style: cinematic\n"
            "Reference_Images: 图1为角色参考图；图2为上一分镜图，只参考构图与色调。\n\n"
            "林清（图1）坐在窗边木桌前\n\n"
            "Avoid: 水印、多余文字、Logo"
        )

    def test_rendering_a_rendered_text_again_is_idempotent(self):
        references = [_sheet("character", "林清"), _PREVIOUS]
        once = render_storyboard_image_prompt(
            _STRUCTURED, style="Anime", style_description="cinematic", references=references
        )
        assert (
            render_storyboard_image_prompt(once, style="Anime", style_description="cinematic", references=references)
            == once
        )

    def test_character_context_inserts_identity_table_and_single_shot_roster(self):
        references = [_sheet("character", "子墨")]
        context = project_character_context(
            [{"characters_in_shot": ["子墨"]}],
            char_field="characters_in_shot",
            characters={"子墨": {"description": "短而整齐的头发，现代校服"}},
        )
        rendered = render_storyboard_image_prompt(
            {
                "scene": "@[子墨]独自捧书",
                "composition": {"shot_type": "Medium Shot", "lighting": "", "ambiance": ""},
            },
            style="Anime",
            references=references,
            character_context=context,
        )
        assert "【角色身份】\n- 子墨（图1）\n" in rendered
        assert (
            "- 已绑定参考图的角色必须严格保持各自参考图中的脸型、眼形、眼距、鼻口比例、发际线和头身比例；面部、发型、体型、服装和配饰不得互换\n"
            in rendered
        )
        assert "本镜角色：子墨（图1）1人。\n本镜只出现上述角色1人，同一角色不得重复出现。\n" in rendered
        assert "Scene: 子墨（图1）独自捧书\n" in rendered
        assert "短而整齐的头发，现代校服" not in rendered
        assert "本格角色" not in rendered
        assert rendered.index("Reference_Images:") < rendered.index("【角色身份】") < rendered.index("Scene:")

    def test_multi_character_roster_forbids_swap_and_keeps_spatial_relations(self):
        references = [_sheet("character", "子墨"), _sheet("character", "骆宾王")]
        context = project_character_context(
            [{"characters_in_shot": ["子墨", "骆宾王"]}],
            char_field="characters_in_shot",
            characters={
                "子墨": {"description": "短发现代男孩"},
                "骆宾王": {"description": "束发古装男孩"},
            },
        )
        rendered = render_storyboard_image_prompt(
            {
                "scene": "@[子墨]在左侧，@[骆宾王]在右侧",
                "composition": {"shot_type": "Medium Shot", "lighting": "", "ambiance": ""},
            },
            style="Anime",
            references=references,
            character_context=context,
        )
        assert "本镜角色：子墨（图1）1人、骆宾王（图2）1人。" in rendered
        assert "本镜中上述角色各恰好1人，身份与外观不得复制、融合、替换或互换。" in rendered
        assert "Scene: 子墨（图1）在左侧，骆宾王（图2）在右侧\n" in rendered

    def test_missing_description_keeps_name_and_does_not_invent_appearance(self):
        context = project_character_context(
            [{"characters_in_shot": ["路人甲"]}],
            char_field="characters_in_shot",
            characters={"路人甲": {"description": 7}},
        )
        rendered = render_storyboard_image_prompt(
            {"scene": "@[路人甲]走过", "composition": {"shot_type": "Medium Shot", "lighting": "", "ambiance": ""}},
            style="Anime",
            character_context=context,
        )
        assert "【角色身份】\n- 路人甲\n" in rendered
        assert "本镜角色：路人甲1人。" in rendered
        assert "Scene: 路人甲走过\n" in rendered

    @pytest.mark.parametrize("has_reference", [False, True])
    def test_derivative_identity_omits_base_and_derivative_descriptions(self, has_reference):
        context = project_character_context(
            [{"characters_in_shot": ["张三/劲装"]}],
            char_field="characters_in_shot",
            characters={
                "张三": {
                    "description": "短发青年",
                    "derivatives": {"劲装": {"description": "黑色劲装"}},
                }
            },
        )
        rendered = render_storyboard_image_prompt(
            {"scene": "@[张三/劲装]站立", "composition": {"shot_type": "Medium Shot", "lighting": "", "ambiance": ""}},
            style="Anime",
            character_context=context,
            references=[_sheet("character", "张三/劲装")] if has_reference else [],
        )
        label = "张三/劲装（图1）" if has_reference else "张三/劲装"
        assert f"- {label}\n" in rendered
        assert "短发青年" not in rendered
        assert "黑色劲装" not in rendered
        assert f"本镜角色：{label}1人。" in rendered
        assert f"Scene: {label}站立\n" in rendered

    def test_character_without_a_sent_reference_keeps_the_name_and_not_a_fake_number(self):
        context = project_character_context(
            [{"characters_in_shot": ["林清", "沈茹/黑化"]}],
            char_field="characters_in_shot",
            characters={"林清": {"description": "黑发"}, "沈茹": {"description": "长发"}},
        )
        rendered = render_storyboard_image_prompt(
            _STRUCTURED,
            style="Anime",
            references=[_sheet("character", "林清")],
            character_context=context,
        )
        assert "- 林清（图1）\n" in rendered
        assert "- 沈茹/黑化\n" in rendered
        assert "黑发" not in rendered
        assert "长发" not in rendered
        assert "图2" not in rendered
        assert "沈茹/黑化（图" not in rendered
        assert "本镜角色：林清（图1）1人、沈茹/黑化1人。" in rendered
        assert "Scene: 林清（图1）坐在窗边木桌前，目光落在信纸上；沈茹/黑化立在门口的阴影里。" in rendered

    def test_empty_character_context_omits_identity_blocks(self):
        rendered = render_storyboard_image_prompt(_STRUCTURED, style="Anime", references=[_sheet("character", "林清")])
        assert "【角色身份】" not in rendered
        assert "本镜角色" not in rendered

    def test_text_form_keeps_identity_blocks_off_style_and_scene_lines(self):
        context = project_character_context(
            [{"characters_in_segment": ["林清"]}],
            char_field="characters_in_segment",
            characters={"林清": {"description": "黑发"}},
        )
        rendered = render_storyboard_image_prompt(
            "@[林清]坐在窗边木桌前",
            style="Anime",
            style_description="cinematic",
            references=[_sheet("character", "林清")],
            character_context=context,
        )
        assert rendered == (
            "Style: Anime\n"
            "Visual style: cinematic\n"
            "Reference_Images: 图1为角色参考图。\n"
            "【角色身份】\n"
            "- 林清（图1）\n"
            "- 已绑定参考图的角色必须严格保持各自参考图中的脸型、眼形、眼距、鼻口比例、发际线和头身比例；面部、发型、体型、服装和配饰不得互换\n"
            "\n"
            "本镜角色：林清（图1）1人。\n"
            "本镜只出现上述角色1人，同一角色不得重复出现。\n"
            "\n"
            "林清（图1）坐在窗边木桌前\n"
            "\n"
            "Avoid: 水印、多余文字、Logo"
        )
        for label in ("Style:", "Visual style:", "Reference_Images:", "Avoid:"):
            assert rendered.count(label) == 1
        assert rendered.count("【角色身份】") == 1
        assert (
            render_storyboard_image_prompt(
                rendered,
                style="Anime",
                style_description="cinematic",
                references=[_sheet("character", "林清")],
                character_context=context,
            )
            == rendered
        )


class TestTextFormRerenderAfterStyleFieldsChange:
    """纯文本形态回贴后项目风格字段才补齐，再渲染时每条风格声明仍只出现一次。"""

    @pytest.mark.parametrize(
        ("first", "then"),
        [
            ({"style": "水墨"}, {"style": "水墨", "style_description": "留白写意"}),
            ({"style_description": "留白写意"}, {"style": "水墨", "style_description": "留白写意"}),
        ],
        ids=["description-added", "style-added"],
    )
    def test_each_style_declaration_appears_once(self, first, then):
        once = render_storyboard_image_prompt("林清坐在窗边木桌前", **first)
        again = render_storyboard_image_prompt(once, **then)
        lines = again.split("\n")
        assert lines.count("Style: 水墨") == 1
        assert lines.count("Visual style: 留白写意") == 1
        assert lines.count("Avoid: 水印、多余文字、Logo") == 1
        assert render_storyboard_image_prompt(again, **then) == again

    def test_legacy_text_with_description_first_is_not_stacked(self):
        legacy = "Visual style: 留白写意\n\nStyle: 水墨\n\n林清坐在窗边木桌前\n\nAvoid: 水印、多余文字、Logo"
        rendered = render_storyboard_image_prompt(legacy, style="水墨", style_description="留白写意")
        assert rendered == legacy


def test_product_sheet_preserves_product_and_ignores_project_style():
    prompt = build_product_prompt("护手霜", "白色管装", "水彩", "柔和笔触")
    assert "商品「护手霜」的标准资产图。" in prompt
    assert "logo、文字、配色、材质、比例与结构不得改变或臆造" in prompt
    assert "包装上印刷的人像图案属于商品外观，须原样保留。" in prompt
    assert "水彩" not in prompt
    assert "柔和笔触" not in prompt
    assert prompt.endswith("Avoid: 出镜人物、水印、多余文字、Logo")


def test_derivative_keeps_reference_layout_and_has_no_style_block():
    prompt = build_character_derivative_prompt("衣服变为黑色")
    assert prompt.startswith("衣服变为黑色")
    assert "保持原图版式（左侧人脸特写、右侧全身三视图" in prompt
    assert "Style:" not in prompt
    assert prompt.endswith("Avoid: 水印、多余文字、Logo")
