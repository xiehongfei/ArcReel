"""Safe parsing and validation for Agent Profile Markdown frontmatter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class FrontmatterError(ValueError):
    """The Markdown frontmatter is missing, malformed, or has invalid metadata."""


@dataclass(frozen=True)
class ProfileMetadata:
    name: str
    description: str
    user_invocable: bool = True


@dataclass(frozen=True)
class AgentDocument:
    """A `.claude/agents/*.md` file split into identity, skills, and body prompt."""

    name: str
    description: str
    prompt: str
    skills: tuple[str, ...] = ()


def _split_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter object, body)`` from a Markdown file with YAML fences."""
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise FrontmatterError("frontmatter is not valid UTF-8") from exc

    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterError("frontmatter must start with a YAML delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise FrontmatterError("frontmatter closing delimiter is missing") from exc
    source = "\n".join(lines[1:end])
    try:
        loaded: Any = yaml.safe_load(source)
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"invalid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise FrontmatterError("frontmatter must be an object")
    return loaded, "\n".join(lines[end + 1 :]).strip()


def _require_identity(loaded: dict[str, Any]) -> tuple[str, str]:
    name = loaded.get("name")
    description = loaded.get("description")
    if not isinstance(name, str) or not name.strip():
        raise FrontmatterError("name must be a non-empty string")
    if not isinstance(description, str) or not description.strip():
        raise FrontmatterError("description must be a non-empty string")
    return name.strip(), description.strip()


def parse_profile_metadata(path: Path) -> ProfileMetadata:
    """Parse validated YAML metadata from a Skill or Subagent Markdown file."""
    loaded, _body = _split_frontmatter(path)
    name, description = _require_identity(loaded)
    user_invocable = loaded.get("user-invocable", True)
    if not isinstance(user_invocable, bool):
        raise FrontmatterError("user-invocable must be a boolean")
    return ProfileMetadata(
        name=name,
        description=description,
        user_invocable=user_invocable,
    )


def parse_agent_document(path: Path) -> AgentDocument:
    """Parse a subagent Markdown file into identity, optional skills, and body prompt."""
    loaded, prompt = _split_frontmatter(path)
    name, description = _require_identity(loaded)
    if not prompt:
        raise FrontmatterError("agent prompt body must be non-empty")
    raw_skills = loaded.get("skills")
    skills: tuple[str, ...] = ()
    if raw_skills is not None:
        if not isinstance(raw_skills, list) or not all(isinstance(item, str) and item.strip() for item in raw_skills):
            raise FrontmatterError("skills must be a list of non-empty strings")
        skills = tuple(item.strip() for item in raw_skills)
    return AgentDocument(
        name=name,
        description=description,
        prompt=prompt,
        skills=skills,
    )
