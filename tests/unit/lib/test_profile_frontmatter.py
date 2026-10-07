"""profile Markdown frontmatter 解析。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.profile_frontmatter import FrontmatterError, parse_agent_document, parse_profile_metadata


def test_parse_agent_document_reads_identity_skills_and_body(tmp_path: Path) -> None:
    path = tmp_path / "normalize-drama-script.md"
    path.write_text(
        "---\n"
        "name: normalize-drama-script\n"
        "description: 剧情演绎规范化剧本\n"
        "skills:\n"
        "  - generate-script\n"
        "---\n"
        "将小说整理为结构化分镜。\n",
        encoding="utf-8",
    )

    document = parse_agent_document(path)

    assert document.name == "normalize-drama-script"
    assert document.description == "剧情演绎规范化剧本"
    assert document.skills == ("generate-script",)
    assert document.prompt == "将小说整理为结构化分镜。"


def test_parse_agent_document_rejects_empty_body(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("---\nname: empty\ndescription: 无正文\n---\n", encoding="utf-8")

    with pytest.raises(FrontmatterError, match="prompt body"):
        parse_agent_document(path)


def test_parse_profile_metadata_still_accepts_empty_body(tmp_path: Path) -> None:
    path = tmp_path / "helper.md"
    path.write_text("---\nname: helper\ndescription: A helper.\n---\n", encoding="utf-8")

    metadata = parse_profile_metadata(path)

    assert metadata.name == "helper"
    assert metadata.description == "A helper."
