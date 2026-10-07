"""Programmatic subagent registry assembled from profile Markdown."""

from __future__ import annotations

from pathlib import Path

from server.agent_runtime.profile_agents import load_project_agents

_REPO = Path(__file__).resolve().parents[4]
_BUILTIN_PROFILE = _REPO / "agent_runtime_profile"
_BUILTIN_AGENT_NAMES = {
    "review-footage",
    "create-episode-script",
    "generate-assets",
    "normalize-drama-script",
    "split-narration-segments",
    "split-reference-video-units",
}


def test_builtin_profile_registers_normalize_drama_script(tmp_path: Path) -> None:
    """内置 profile 的专用子智能体必须进入 Agent 工具注册表，不能只剩 general-purpose。"""
    agents = load_project_agents(tmp_path / "empty-project", _BUILTIN_PROFILE)

    assert agents is not None
    assert set(agents) == _BUILTIN_AGENT_NAMES
    assert "剧情演绎" in agents["normalize-drama-script"].description
    assert agents["create-episode-script"].skills == ["generate-script"]
    assert agents["normalize-drama-script"].disallowedTools == ["Agent", "Task"]


def test_project_agents_override_profile(tmp_path: Path) -> None:
    project = tmp_path / "project"
    agents_dir = project / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "normalize-drama-script.md").write_text(
        "---\nname: normalize-drama-script\ndescription: 项目侧定制\n---\n定制正文\n",
        encoding="utf-8",
    )

    agents = load_project_agents(project, _BUILTIN_PROFILE)

    assert agents is not None
    assert set(agents) == {"normalize-drama-script"}
    assert agents["normalize-drama-script"].description == "项目侧定制"
    assert agents["normalize-drama-script"].prompt == "定制正文"


def test_invalid_agent_file_is_skipped(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    agents_dir = profile / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "broken.md").write_text("---\n- invalid\n---\n", encoding="utf-8")
    (agents_dir / "ok.md").write_text(
        "---\nname: ok\ndescription: 可用\n---\n正文\n",
        encoding="utf-8",
    )

    agents = load_project_agents(tmp_path / "project", profile)

    assert agents is not None
    assert set(agents) == {"ok"}


def test_missing_agents_dir_returns_none(tmp_path: Path) -> None:
    assert load_project_agents(tmp_path / "project", tmp_path / "profile") is None
