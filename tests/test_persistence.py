import json
from pathlib import Path

import pytest

from incidentlens.persistence import (
    ArtifactConflictError,
    ArtifactCorruptionError,
    ArtifactNotFoundError,
    ArtifactScopeError,
    ArtifactSizeError,
    ArtifactStore,
    Checkpoint,
    CheckpointCorruptionError,
    CheckpointStore,
    StoredArtifact,
    UnsupportedStateVersionError,
)


def make_artifact() -> StoredArtifact:
    return StoredArtifact(
        artifact_id="evidence-inc-001-v1",
        incident_id="inc-001",
        artifact_type="telemetry",
        schema_version=1,
        content={"records": ["E1", "E2"]},
    )


def test_artifact_round_trip(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    artifact = make_artifact()

    store.put(artifact)

    assert store.load(artifact.artifact_id, "inc-001") == artifact


def test_exact_duplicate_is_idempotent(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    artifact = make_artifact()

    assert store.put(artifact) == store.put(artifact)


def test_conflicting_duplicate_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.put(make_artifact())
    conflicting = make_artifact().model_copy(update={"content": {"records": ["E9"]}})

    with pytest.raises(ArtifactConflictError):
        store.put(conflicting)


def test_cross_incident_artifact_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.put(make_artifact())

    with pytest.raises(ArtifactScopeError):
        store.load("evidence-inc-001-v1", "inc-002")


def test_corrupted_artifact_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    path = tmp_path / "evidence-inc-001-v1.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ArtifactCorruptionError):
        store.load("evidence-inc-001-v1", "inc-001")


def test_checkpoint_round_trip(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path)
    checkpoint = Checkpoint(
        investigation_id="inc-001",
        state_version=1,
        status="investigating",
        artifact_refs=["evidence-inc-001-v1"],
    )

    store.save(checkpoint)

    assert store.load("inc-001") == checkpoint


def test_corrupted_checkpoint_is_rejected(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path)
    (tmp_path / "inc-001.json").write_text("not json", encoding="utf-8")

    with pytest.raises(CheckpointCorruptionError):
        store.load("inc-001")


def test_unsupported_checkpoint_version_is_rejected(tmp_path: Path) -> None:
    store = CheckpointStore(tmp_path)
    (tmp_path / "inc-001.json").write_text(
        json.dumps(
            {
                "investigation_id": "inc-001",
                "state_version": 99,
                "status": "investigating",
                "artifact_refs": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedStateVersionError):
        store.load("inc-001")


def test_missing_artifact_is_rejected_as_unavailable(tmp_path: Path) -> None:
    with pytest.raises(ArtifactNotFoundError):
        ArtifactStore(tmp_path).load("missing", "inc-001")


def test_checkpoint_artifact_references_are_validated_in_scope(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.put(make_artifact())

    loaded = store.validate_references(["evidence-inc-001-v1"], "inc-001")

    assert [item.artifact_id for item in loaded] == ["evidence-inc-001-v1"]


def test_artifact_size_limit_is_enforced(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, max_artifact_bytes=20)

    with pytest.raises(ArtifactSizeError):
        store.put(make_artifact())


def test_artifact_retention_removes_oldest_artifacts(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path, max_artifacts=1)
    store.put(make_artifact())
    second = make_artifact().model_copy(update={"artifact_id": "evidence-inc-001-v2"})
    store.put(second)

    with pytest.raises(ArtifactNotFoundError):
        store.load("evidence-inc-001-v1", "inc-001")
    assert store.load("evidence-inc-001-v2", "inc-001") == second


def test_missing_checkpoint_artifact_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)

    checkpoint = Checkpoint(
        investigation_id="incident-001",
        state_version=1,
        status="investigating",
        artifact_refs=["missing-E7"],
    )

    with pytest.raises(ArtifactNotFoundError):
        store.validate_references(
            checkpoint.artifact_refs,
            checkpoint.investigation_id,
        )