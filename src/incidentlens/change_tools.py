import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from incidentlens.retrieval import ChangeCorpus, ChangeEvent
from incidentlens.tools import ToolRegistry, ToolSpec

MAX_CHANGE_WINDOW = timedelta(days=7)


class ChangeQueryArgs(BaseModel):
    incident_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_window(self) -> "ChangeQueryArgs":
        for name, value in (("start_time", self.start_time), ("end_time", self.end_time)):
            if value.tzinfo is None or value.utcoffset() is None or value.tzinfo != UTC:
                raise ValueError(f"{name} must use UTC")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > MAX_CHANGE_WINDOW:
            raise ValueError("change query window exceeds maximum duration")
        return self


class ChangeQueryResult(BaseModel):
    incident_id: str
    status: Literal["success", "invalid_query"] = "success"
    records: list[ChangeEvent] = Field(default_factory=list)
    truncated: bool = False
    error: dict[str, object] | None = None


class ChangeFixtureStore:
    def __init__(self, incident_id: str, corpus: ChangeCorpus) -> None:
        self.incident_id = incident_id
        self.corpus = corpus

    def list_changes(self, args: ChangeQueryArgs) -> ChangeQueryResult:
        if args.incident_id != self.incident_id:
            return ChangeQueryResult(
                incident_id=args.incident_id,
                status="invalid_query",
                error={
                    "classification": "incident_scope_violation",
                    "retryable": False,
                    "message": "Requested incident is outside the active investigation scope.",
                },
            )
        matches = self.corpus.query(
            args.model_copy(
                update={
                    "service_name": args.service_name,
                    "environment": args.environment,
                }
            )
        )
        return ChangeQueryResult(
            incident_id=args.incident_id,
            records=matches[: args.limit],
            truncated=len(matches) > args.limit,
        )


def build_changes_registry(fixture_path: str | Path, *, incident_id: str) -> ToolRegistry:
    data = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    corpus = ChangeCorpus.model_validate(data)
    store = ChangeFixtureStore(incident_id, corpus)
    return ToolRegistry(
        [
            ToolSpec(
                name="list_changes",
                description="List bounded deployment and configuration changes for the active incident.",
                args_schema=ChangeQueryArgs,
                result_schema=ChangeQueryResult,
                handler=store.list_changes,
            )
        ]
    )
