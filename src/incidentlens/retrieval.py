import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunbookSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    title: str = Field(min_length=1)

    service_name: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    service_version: str | None = None

    valid_from: datetime
    valid_until: datetime | None = None
    status: Literal["active", "deprecated"]

    content: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dates(self) -> "RunbookSection":
        _require_utc(self.valid_from, "valid_from")

        if self.valid_until is not None:
            _require_utc(self.valid_until, "valid_until")
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be after valid_from")

        return self


class RunbookCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    quote_or_summary: str = Field(min_length=1)
    retrieval_score: float = Field(ge=0)


class ChangeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    environment: str = Field(min_length=1)

    version_before: str | None = None
    version_after: str | None = None

    change_type: Literal[
        "deployment",
        "configuration",
        "feature_flag",
    ]

    occurred_at: datetime
    summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_timestamp(self) -> "ChangeEvent":
        _require_utc(self.occurred_at, "occurred_at")
        return self


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    if value.tzinfo != UTC:
        raise ValueError(f"{field_name} must use UTC")


def filter_runbooks(
    sections: list[RunbookSection],
    *,
    service_name: str,
    environment: str,
    incident_time: datetime,
) -> list[RunbookSection]:
    _require_utc(incident_time, "incident_time")

    return [
        section
        for section in sections
        if (
            section.service_name == service_name
            and section.environment == environment
            and section.status == "active"
            and section.valid_from <= incident_time
            and (section.valid_until is None or incident_time < section.valid_until)
        )
    ]


class RunbookCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    sections: list[RunbookSection] = Field(min_length=1)

    @model_validator(mode="after")
    def section_ids_are_unique(self) -> "RunbookCorpus":
        keys = [(section.document_id, section.section_id) for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("runbook section identifiers must be unique")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "RunbookCorpus":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def retrieve(
        self,
        query: str,
        *,
        service_name: str,
        environment: str,
        incident_time: datetime,
        limit: int = 5,
    ) -> list[RunbookCitation]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")

        candidates = filter_runbooks(
            self.sections,
            service_name=service_name,
            environment=environment,
            incident_time=incident_time,
        )
        query_terms = _terms(query)
        ranked: list[tuple[float, RunbookSection]] = []
        for section in candidates:
            searchable = _terms(f"{section.title} {section.content}")
            overlap = query_terms & searchable
            if overlap:
                score = len(overlap) / len(query_terms)
                ranked.append((score, section))

        ranked.sort(key=lambda item: (-item[0], item[1].document_id, item[1].section_id))
        return [
            RunbookCitation(
                document_id=section.document_id,
                section_id=section.section_id,
                quote_or_summary=section.content,
                retrieval_score=score,
            )
            for score, section in ranked[:limit]
        ]


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", value.lower()))


class RunbookQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    incident_time: datetime
    limit: int = Field(default=5, ge=1, le=20)


class ChangeQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    start_time: datetime
    end_time: datetime
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_window(self) -> "ChangeQuery":
        _require_utc(self.start_time, "start_time")
        _require_utc(self.end_time, "end_time")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class ChangeCorpus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    events: list[ChangeEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def change_ids_are_unique(self) -> "ChangeCorpus":
        ids = [event.change_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("change IDs must be unique")
        return self

    @classmethod
    def load(cls, path: str | Path) -> "ChangeCorpus":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def query(self, request: ChangeQuery) -> list[ChangeEvent]:
        matches = [
            event
            for event in self.events
            if (
                event.service_name == request.service_name
                and event.environment == request.environment
                and request.start_time <= event.occurred_at < request.end_time
            )
        ]
        return sorted(matches, key=lambda event: (event.occurred_at, event.change_id))[
            : request.limit
        ]


class RunbookAgent:
    """Read-only agent boundary for runbook guidance only."""

    agent_id = "runbook-agent"
    allowed_tools = frozenset({"retrieve_runbook"})
    allowed_signal_types = frozenset({"runbook"})

    def __init__(self, corpus: RunbookCorpus) -> None:
        self._corpus = corpus

    def investigate(self, request: RunbookQuery) -> list[RunbookCitation]:
        return self._corpus.retrieve(
            request.query,
            service_name=request.service_name,
            environment=request.environment,
            incident_time=request.incident_time,
            limit=request.limit,
        )


class ChangeAgent:
    """Read-only agent boundary for deployment/configuration events only."""

    agent_id = "change-agent"
    allowed_tools = frozenset({"query_changes"})
    allowed_signal_types = frozenset({"change"})

    def __init__(self, corpus: ChangeCorpus) -> None:
        self._corpus = corpus

    def investigate(self, request: ChangeQuery) -> list[ChangeEvent]:
        return self._corpus.query(request)


class RetrievalMetrics(BaseModel):
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    hit_rate: float = Field(ge=0, le=1)
    reciprocal_rank: float = Field(ge=0, le=1)


def citation_key(citation: RunbookCitation) -> str:
    return f"{citation.document_id}:{citation.section_id}"


def evaluate_retrieval(
    retrieved: list[RunbookCitation],
    relevant_ids: set[str],
) -> RetrievalMetrics:
    retrieved_ids = [citation_key(item) for item in retrieved]
    retrieved_set = set(retrieved_ids)
    relevant_count = len(retrieved_set & relevant_ids)

    precision = relevant_count / len(retrieved_ids) if retrieved_ids else float(not relevant_ids)
    recall = relevant_count / len(relevant_ids) if relevant_ids else 1.0
    first_match = next(
        (index for index, item in enumerate(retrieved_ids, start=1) if item in relevant_ids),
        None,
    )
    reciprocal_rank = 1 / first_match if first_match is not None else 0.0

    return RetrievalMetrics(
        precision=precision,
        recall=recall,
        hit_rate=float(bool(retrieved_set & relevant_ids)),
        reciprocal_rank=reciprocal_rank,
    )


class ChangeCorrelation(BaseModel):
    change_id: str = Field(min_length=1)
    relation: Literal["before_incident", "during_incident"]
    offset_seconds: float
    supports_causation: bool = False


def correlate_change_events(
    events: list[ChangeEvent],
    *,
    incident_start: datetime,
    incident_end: datetime,
    max_before_seconds: int = 300,
) -> list[ChangeCorrelation]:
    _require_utc(incident_start, "incident_start")
    _require_utc(incident_end, "incident_end")
    if incident_start >= incident_end:
        raise ValueError("incident_start must be before incident_end")
    if max_before_seconds < 0:
        raise ValueError("max_before_seconds cannot be negative")

    correlations: list[ChangeCorrelation] = []
    for event in events:
        if incident_start <= event.occurred_at < incident_end:
            correlations.append(
                ChangeCorrelation(
                    change_id=event.change_id,
                    relation="during_incident",
                    offset_seconds=(event.occurred_at - incident_start).total_seconds(),
                )
            )
        elif incident_start - event.occurred_at <= timedelta(seconds=max_before_seconds):
            correlations.append(
                ChangeCorrelation(
                    change_id=event.change_id,
                    relation="before_incident",
                    offset_seconds=(incident_start - event.occurred_at).total_seconds(),
                )
            )

    return sorted(correlations, key=lambda item: (item.offset_seconds, item.change_id))
