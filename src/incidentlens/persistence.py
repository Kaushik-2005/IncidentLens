import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class StoredArtifact(BaseModel):
    artifact_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    artifact_type: Literal["telemetry", "finding", "report", "evidence"]
    schema_version: int = Field(ge=1)
    content: dict[str, Any]


class Checkpoint(BaseModel):
    investigation_id: str = Field(min_length=1)
    state_version: int = Field(ge=1)
    status: str = Field(min_length=1)
    artifact_refs: list[str] = Field(default_factory=list)


class ArtifactError(ValueError):
    """Base class for artifact persistence failures."""


class ArtifactConflictError(ArtifactError):
    """Raised when an artifact ID is reused with different content."""


class ArtifactScopeError(ArtifactError):
    """Raised when an artifact belongs to a different incident."""


class ArtifactCorruptionError(ArtifactError):
    """Raised when stored artifact data cannot be validated."""


class ArtifactNotFoundError(ArtifactError):
    """Raised when a referenced artifact is unavailable."""


class ArtifactSizeError(ArtifactError):
    """Raised when an artifact exceeds the configured size limit."""


class CheckpointError(ValueError):
    """Base class for checkpoint persistence failures."""


class CheckpointCorruptionError(CheckpointError):
    """Raised when stored checkpoint data cannot be validated."""


class UnsupportedStateVersionError(CheckpointError):
    """Raised when a checkpoint requires an unsupported state schema."""


class ArtifactStore:
    def __init__(
        self,
        root: str | Path,
        *,
        max_artifact_bytes: int = 1_000_000,
        max_artifacts: int | None = None,
    ) -> None:
        if max_artifact_bytes < 1:
            raise ValueError("max_artifact_bytes must be positive")
        if max_artifacts is not None and max_artifacts < 1:
            raise ValueError("max_artifacts must be positive")
        self.root = Path(root)
        self.max_artifact_bytes = max_artifact_bytes
        self.max_artifacts = max_artifacts
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, artifact_id: str) -> Path:
        if not artifact_id or Path(artifact_id).name != artifact_id:
            raise ArtifactError("artifact ID must be a single path-safe name")
        return self.root / f"{artifact_id}.json"

    def put(self, artifact: StoredArtifact) -> StoredArtifact:
        path = self._path(artifact.artifact_id)
        encoded = json.dumps(artifact.model_dump(mode="json"), sort_keys=True).encode()
        if len(encoded) > self.max_artifact_bytes:
            raise ArtifactSizeError("artifact exceeds configured size limit")
        if not path.exists():
            self._write_json(path, artifact.model_dump(mode="json"))
            self._enforce_retention()
            return artifact

        existing = self._load(path, artifact.artifact_id)
        if existing.model_dump(mode="json") != artifact.model_dump(mode="json"):
            raise ArtifactConflictError(
                f"artifact already exists with different content: {artifact.artifact_id}"
            )
        return existing

    def load(self, artifact_id: str, incident_id: str) -> StoredArtifact:
        path = self._path(artifact_id)
        if not path.exists():
            raise ArtifactNotFoundError(f"artifact is unavailable: {artifact_id}")
        artifact = self._load(path, artifact_id)
        if artifact.incident_id != incident_id:
            raise ArtifactScopeError("artifact belongs to another incident")
        return artifact

    def validate_references(
        self,
        artifact_ids: list[str],
        incident_id: str,
    ) -> list[StoredArtifact]:
        """Load every checkpoint reference within the active incident scope."""
        return [self.load(artifact_id, incident_id) for artifact_id in artifact_ids]

    def _enforce_retention(self) -> None:
        if self.max_artifacts is None:
            return
        paths = sorted(
            self.root.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
        )
        for path in paths[: max(0, len(paths) - self.max_artifacts)]:
            path.unlink()

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _load(path: Path, artifact_id: str) -> StoredArtifact:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return StoredArtifact.model_validate(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ArtifactCorruptionError(f"artifact is invalid: {artifact_id}") from exc


class CheckpointStore:
    CURRENT_STATE_VERSION = 1

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, investigation_id: str) -> Path:
        if not investigation_id or Path(investigation_id).name != investigation_id:
            raise CheckpointError("investigation ID must be a single path-safe name")
        return self.root / f"{investigation_id}.json"

    def save(self, checkpoint: Checkpoint) -> None:
        ArtifactStore._write_json(
            self._path(checkpoint.investigation_id),
            checkpoint.model_dump(mode="json"),
        )

    def load(self, investigation_id: str) -> Checkpoint:
        path = self._path(investigation_id)
        try:
            checkpoint = Checkpoint.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise CheckpointCorruptionError(f"checkpoint is invalid: {investigation_id}") from exc

        if checkpoint.state_version != self.CURRENT_STATE_VERSION:
            raise UnsupportedStateVersionError(
                f"unsupported checkpoint state version: {checkpoint.state_version}"
            )
        return checkpoint
