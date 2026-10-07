"""Tests for image basis restoration compatibility."""

import pytest

from lib.artifacts.artifact_manifest import ArtifactBasis
from lib.artifacts.artifact_version_provenance import IMAGE_ARTIFACT_BASIS_FIELD, parse_image_version_basis


@pytest.mark.parametrize("kind_version", [1, 2])
def test_grid_composite_versions_remain_restorable(kind_version: int) -> None:
    basis = ArtifactBasis.build(
        "artifact-visual/grid-composite",
        kind_version=kind_version,
        inputs={"group_id": "grid_1"},
    )

    assert (
        parse_image_version_basis(
            "grids",
            "grid_1",
            {IMAGE_ARTIFACT_BASIS_FIELD: basis.to_evidence_dict()},
        )
        == basis
    )


@pytest.mark.parametrize("kind_version", [1, 2])
def test_grid_member_versions_remain_restorable(kind_version: int) -> None:
    basis = ArtifactBasis.build(
        "artifact-visual/grid-member",
        kind_version=kind_version,
        inputs={"cell": {"resource_id": "E1S01"}},
    )

    assert (
        parse_image_version_basis(
            "storyboards",
            "E1S01",
            {IMAGE_ARTIFACT_BASIS_FIELD: basis.to_evidence_dict()},
        )
        == basis
    )


@pytest.mark.parametrize("kind_version", [1, 2])
def test_storyboard_image_versions_remain_restorable(kind_version: int) -> None:
    basis = ArtifactBasis.build(
        "artifact-visual/storyboard-image",
        kind_version=kind_version,
        inputs={"resource_id": "E1S01"},
    )

    assert (
        parse_image_version_basis(
            "storyboards",
            "E1S01",
            {IMAGE_ARTIFACT_BASIS_FIELD: basis.to_evidence_dict()},
        )
        == basis
    )
