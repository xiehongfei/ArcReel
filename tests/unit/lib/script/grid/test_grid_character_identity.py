"""Tests for deterministic grid character identity projection."""

from lib.script.grid.character_identity import project_grid_character_context


def test_projects_first_appearance_order_and_deduplicated_cell_rosters() -> None:
    scenes = [
        {"characters_in_scene": [" 子墨 ", "骆宾王", "子墨"]},
        {"characters_in_scene": ["骆宾王", "飞飞"]},
    ]

    context = project_grid_character_context(
        scenes,
        char_field="characters_in_scene",
        characters={
            "子墨": {"description": "短发现代男孩"},
            "骆宾王": {"description": "束发古装男孩"},
            "飞飞": {"description": "白纸飞机"},
        },
    )

    assert [identity.name for identity in context.identities] == ["子墨", "骆宾王", "飞飞"]
    assert [identity.description for identity in context.identities] == [
        "短发现代男孩",
        "束发古装男孩",
        "白纸飞机",
    ]
    assert context.cell_characters == (("子墨", "骆宾王"), ("骆宾王", "飞飞"))


def test_combines_base_and_derivative_descriptions() -> None:
    context = project_grid_character_context(
        [{"characters_in_scene": ["飞飞/载人形态"]}],
        char_field="characters_in_scene",
        characters={
            "飞飞": {
                "description": "白纸飞机",
                "derivatives": {"载人形态": {"description": "放大并增加固定座"}},
            }
        },
    )

    assert context.identities[0].description == "白纸飞机；放大并增加固定座"


def test_missing_or_malformed_definitions_do_not_invent_descriptions() -> None:
    context = project_grid_character_context(
        [
            {"characters_in_scene": ["未登记角色", None, 7]},
            {"characters_in_scene": "不是列表"},
        ],
        char_field="characters_in_scene",
        characters={"未登记角色": {"description": 7}},
    )

    assert context.identities[0].name == "未登记角色"
    assert context.identities[0].description == ""
    assert context.cell_characters == (("未登记角色",), ())


def test_absent_character_field_yields_empty_context() -> None:
    context = project_grid_character_context(
        [{"characters_in_scene": ["子墨"]}],
        char_field=None,
        characters={"子墨": {"description": "短发"}},
    )

    assert context.identities == ()
    assert context.cell_characters == ((),)
