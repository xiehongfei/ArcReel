"""Load profile subagent Markdown files into SDK ``AgentDefinition`` values.

The Agent tool's host registry only lists built-in types plus ``ClaudeAgentOptions.agents``.
Filesystem ``.claude/agents/*.md`` is still materialized for the subagent to read, but
dispatch names come from this programmatic map.
"""

from __future__ import annotations

import logging
from pathlib import Path

from claude_agent_sdk import AgentDefinition

from lib.profile_frontmatter import FrontmatterError, parse_agent_document

logger = logging.getLogger(__name__)

# Subagents inherit parent tools when ``tools`` is omitted. Block the spawn
# tools so a focused agent cannot nest another Agent/Task (CLAUDE.*.md 约束).
_SUBAGENT_DISALLOWED_TOOLS = ["Agent", "Task"]


def load_project_agents(
    project_cwd: Path,
    profile_root: Path,
) -> dict[str, AgentDefinition] | None:
    """Return custom subagents for ``ClaudeAgentOptions.agents``, or None if none load.

    Prefers ``{project_cwd}/.claude/agents/*.md`` when that directory has Markdown
    files (materialized / user-customized copies). Otherwise reads the same tree
    under ``profile_root``. Invalid files are skipped; an empty result is None so
    the assembler does not pass an empty dict that would hide leftover filesystem
    agents.
    """
    agents_dir = _resolve_agents_dir(project_cwd, profile_root)
    if agents_dir is None:
        return None

    loaded: dict[str, AgentDefinition] = {}
    for path in sorted(agents_dir.glob("*.md")):
        try:
            document = parse_agent_document(path)
        except (FrontmatterError, OSError) as exc:
            logger.warning("skipping subagent file %s: %s", path, exc)
            continue
        loaded[document.name] = AgentDefinition(
            description=document.description,
            prompt=document.prompt,
            skills=list(document.skills) or None,
            disallowedTools=list(_SUBAGENT_DISALLOWED_TOOLS),
        )
    return loaded or None


def _resolve_agents_dir(project_cwd: Path, profile_root: Path) -> Path | None:
    project_dir = project_cwd / ".claude" / "agents"
    if _has_agent_markdown(project_dir):
        return project_dir
    profile_dir = profile_root / ".claude" / "agents"
    if _has_agent_markdown(profile_dir):
        return profile_dir
    return None


def _has_agent_markdown(directory: Path) -> bool:
    return directory.is_dir() and any(directory.glob("*.md"))
