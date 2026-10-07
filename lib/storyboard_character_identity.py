"""Deterministic character identity projection for storyboard and grid prompts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lib.asset_types import DERIVATIVES_FIELD, asset_name_comparison_key, resolve_asset_key
from lib.reference_catalog import split_derivative_reference


@dataclass(frozen=True, slots=True)
class CharacterIdentity:
    """One logical character shape used by a storyboard prompt and its visual basis."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CharacterContext:
    """Ordered identities plus the ordered roster for each storyboard item or grid cell."""

    identities: tuple[CharacterIdentity, ...]
    cell_characters: tuple[tuple[str, ...], ...]

    @property
    def character_names(self) -> frozenset[str]:
        return frozenset(identity.name for identity in self.identities)

    @property
    def descriptions(self) -> dict[str, str]:
        return {identity.name: identity.description for identity in self.identities}


GridCharacterIdentity = CharacterIdentity
GridCharacterContext = CharacterContext


def _description(value: object) -> str:
    if not isinstance(value, Mapping):
        return ""
    raw = value.get("description")
    return raw.strip() if isinstance(raw, str) else ""


def _character_description(characters: object, name: str) -> str:
    if not isinstance(characters, Mapping):
        return ""
    base_name, derivative_name = split_derivative_reference(name)
    base_key = resolve_asset_key(characters, base_name)
    if base_key is None:
        return ""
    base = characters.get(base_key)
    base_description = _description(base)
    if not derivative_name or not isinstance(base, Mapping):
        return base_description
    derivatives = base.get(DERIVATIVES_FIELD)
    derivative_key = resolve_asset_key(derivatives, derivative_name)
    derivative_description = (
        _description(derivatives.get(derivative_key))
        if isinstance(derivatives, Mapping) and derivative_key is not None
        else ""
    )
    return "；".join(part for part in (base_description, derivative_description) if part)


def _scene_characters(scene: Mapping[str, object], char_field: str | None) -> tuple[str, ...]:
    if char_field is None:
        return ()
    raw_names = scene.get(char_field, ())
    if not isinstance(raw_names, Sequence) or isinstance(raw_names, (str, bytes)):
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for raw_name in raw_names:
        if not isinstance(raw_name, str):
            continue
        name = asset_name_comparison_key(raw_name)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return tuple(names)


def project_character_context(
    scenes: Sequence[Mapping[str, object]],
    *,
    char_field: str | None,
    characters: object,
) -> CharacterContext:
    """Project stable character facts without inventing missing appearance data."""

    cell_characters = tuple(_scene_characters(scene, char_field) for scene in scenes)
    ordered_names: list[str] = []
    seen: set[str] = set()
    for roster in cell_characters:
        for name in roster:
            if name in seen:
                continue
            seen.add(name)
            ordered_names.append(name)
    identities = tuple(
        CharacterIdentity(name=name, description=_character_description(characters, name)) for name in ordered_names
    )
    return CharacterContext(identities=identities, cell_characters=cell_characters)


def project_grid_character_context(
    scenes: Sequence[Mapping[str, object]],
    *,
    char_field: str | None,
    characters: object,
) -> CharacterContext:
    """Project one grid's character facts; same algorithm as :func:`project_character_context`."""

    return project_character_context(scenes, char_field=char_field, characters=characters)


__all__ = [
    "CharacterContext",
    "CharacterIdentity",
    "GridCharacterContext",
    "GridCharacterIdentity",
    "project_character_context",
    "project_grid_character_context",
]
