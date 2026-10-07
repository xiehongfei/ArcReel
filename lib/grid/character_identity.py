"""Compatibility re-export of the shared storyboard character identity projection."""

from __future__ import annotations

from lib.storyboard_character_identity import (
    CharacterContext as GridCharacterContext,
)
from lib.storyboard_character_identity import (
    CharacterIdentity as GridCharacterIdentity,
)
from lib.storyboard_character_identity import (
    project_character_context as project_grid_character_context,
)

__all__ = [
    "GridCharacterContext",
    "GridCharacterIdentity",
    "project_grid_character_context",
]
