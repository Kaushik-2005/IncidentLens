from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from statistics import fmean, pstdev
from time import perf_counter
from types import SimpleNamespace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from incidentlens.agent_loop import (
    AgentLoopError,
    InvalidModelResponseError,
    MaxStepsExceededError,
    ModelBudgetExhaustedError,
    ModelCallBudget,
    ModelClient,
    ModelProviderError,
    ToolBudgetExhaustedError,
    run_agent_loop_with_metadata,
    validate_model_response,
)
from incidentlens.contracts import (
    Evidence,
    Hypothesis,
    IncidentInput,
    InvestigationReport,
    ModelToolRequest,
)
from incidentlens.coordination import (
    SpecialistFindingMessage,
    build_investigation_tasks,
)
from incidentlens.hypotheses import (
    EvidenceTable,
    HypothesisCandidate,
    VerifierAgent,
)
from incidentlens.parallel_investigation import (
    CoordinatorRuntime,
    Worker,
    aggregate_findings,
    apply_coverage_to_report,
)
from incidentlens.telemetry import load_agent_fixture, load_evaluator_fixture, project_agent_fixture
from incidentlens.tools import (
    IncidentFixtureArgs,
    IncidentFixtureResult,
    ToolRegistry,
    ToolSpec,
)

EvaluationSplit = Literal["development", "held_out"]
EvaluationJudgment = Literal["supported", "unsupported", "inconclusive"]
EvaluationVariant = Literal[
    "deterministic",
    "single_agent",
    "multi_agent",
    "multi_agent_without_verifier",
]


class EvaluationScenario(BaseModel):
    """Evaluator-owned scenario metadata, including hidden labels."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    split: EvaluationSplit
    incident_fixture_path: str = Field(min_length=1)
    expected_root_cause: str = Field(min_length=1)
    expected_evidence_ids: frozenset[str] = Field(default_factory=frozenset)
    acceptable_abstention: bool
    required_evidence_sources: frozenset[Literal["log", "metric", "trace", "change", "runbook"]] = Field(
        default_factory=frozenset
    )


class EvaluationDataset(BaseModel):
    """Versioned evaluator-owned scenario catalog."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    scenarios: list[EvaluationScenario] = Field(min_length=1)

    @model_validator(mode="after")
    def scenario_ids_are_unique(self) -> EvaluationDataset:
        ids = [scenario.scenario_id for scenario in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("evaluation scenario IDs must be unique")
        return self

    @classmethod
    def load(cls, path: str | Path) -> EvaluationDataset:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def for_split(self, split: EvaluationSplit) -> tuple[EvaluationScenario, ...]:
        return validate_scenario_split(self.scenarios, split)

    def agent_view(self, scenario_id: str) -> AgentScenarioView:
        scenario = next(
            (item for item in self.scenarios if item.scenario_id == scenario_id),
            None,
        )
        if scenario is None:
            raise ValueError(f"unknown evaluation scenario: {scenario_id}")
        evaluator_fixture = load_evaluator_fixture(scenario.incident_fixture_path)
        if evaluator_fixture.manifest.incident_id != scenario.scenario_id:
            raise ValueError(
                "evaluation scenario ID does not match fixture incident ID: "
                f"{scenario.scenario_id} != {evaluator_fixture.manifest.incident_id}"
            )
        # Force the agent projection through the telemetry boundary. The hidden
        # ground truth is never returned, even though the evaluator loads it here.
        agent_fixture = project_agent_fixture(evaluator_fixture)
        manifest = agent_fixture.manifest
        return AgentScenarioView.from_payload(
            scenario=scenario,
            incident_title=manifest.title,
            affected_service=manifest.affected_services[0],
            start_time=manifest.time_window.start.isoformat(),
            end_time=manifest.time_window.end.isoformat(),
            incident_summary=(
                f"Investigate {manifest.title} for {', '.join(manifest.affected_services)}."
            ),
        )


class AgentScenarioView(BaseModel):
    """Agent-visible projection that intentionally excludes evaluator labels."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    incident_fixture_path: str = Field(min_length=1)
    incident_title: str = Field(min_length=1)
    affected_service: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str | None = None
    incident_summary: str = Field(min_length=1)

    @classmethod
    def from_payload(
        cls,
        *,
        scenario: EvaluationScenario,
        incident_title: str,
        affected_service: str,
        start_time: str,
        incident_summary: str,
        end_time: str | None = None,
    ) -> AgentScenarioView:
        return cls(
            scenario_id=scenario.scenario_id,
            incident_fixture_path=scenario.incident_fixture_path,
            incident_title=incident_title,
            affected_service=affected_service,
            start_time=start_time,
            end_time=end_time,
            incident_summary=incident_summary,
        )


class EvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    variant: EvaluationVariant
    split: EvaluationSplit
    grounded: bool
    root_cause_correct: bool
    unsupported_claim: bool
    abstained_appropriately: bool
    evidence_precision: float = Field(ge=0, le=1)
    evidence_recall: float = Field(ge=0, le=1)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    recovery_success: bool
    trajectory_valid: bool = True
    unauthorized_tool_requests: int = Field(default=0, ge=0)
    duplicate_tool_calls: int = Field(default=0, ge=0)
    branch_statuses: dict[str, str] = Field(default_factory=dict)
    branch_errors: dict[str, str] = Field(default_factory=dict)


class EvaluationAggregate(BaseModel):
    scenario_count: int = Field(ge=0)
    grounded_rate: float = Field(ge=0, le=1)
    root_cause_accuracy: float = Field(ge=0, le=1)
    unsupported_claim_rate: float = Field(ge=0, le=1)
    abstention_quality: float = Field(ge=0, le=1)
    mean_evidence_precision: float = Field(ge=0, le=1)
    mean_evidence_recall: float = Field(ge=0, le=1)
    mean_model_calls: float = Field(ge=0)
    mean_tool_calls: float = Field(ge=0)
    mean_latency_ms: float = Field(ge=0)
    total_estimated_cost: float = Field(ge=0)
    recovery_rate: float = Field(ge=0, le=1)
    trajectory_success_rate: float = Field(default=0, ge=0, le=1)
    mean_unauthorized_tool_requests: float = Field(default=0, ge=0)
    mean_duplicate_tool_calls: float = Field(default=0, ge=0)


class EvaluationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_version: str = Field(min_length=1)
    variant: EvaluationVariant
    split: EvaluationSplit
    results: list[EvaluationResult] = Field(default_factory=list)
    aggregate: EvaluationAggregate

    @model_validator(mode="after")
    def results_match_run(self) -> EvaluationRun:
        mismatched = [
            result.scenario_id
            for result in self.results
            if result.variant != self.variant or result.split != self.split
        ]
        if mismatched:
            raise ValueError(f"evaluation results do not match run configuration: {mismatched}")
        if self.aggregate.scenario_count != len(self.results):
            raise ValueError("aggregate scenario_count must equal result count")
        return self


class EvaluationRunSet(BaseModel):
    """Comparable runs for one dataset split and evaluation version."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    dataset_version: str = Field(min_length=1)
    split: EvaluationSplit
    runs: list[EvaluationRun] = Field(min_length=1)

    @model_validator(mode="after")
    def runs_are_comparable(self) -> EvaluationRunSet:
        variants = [run.variant for run in self.runs]
        if len(variants) != len(set(variants)):
            raise ValueError("evaluation variants must be unique within a run set")
        if any(run.split != self.split for run in self.runs):
            raise ValueError("evaluation runs must use the run-set split")
        scenario_sets = [
            {result.scenario_id for result in run.results} for run in self.runs
        ]
        if any(ids != scenario_sets[0] for ids in scenario_sets[1:]):
            raise ValueError("evaluation variants must cover the same scenarios")
        return self


class EvaluationComparison(BaseModel):
    """Metric deltas between two comparable evaluation variants."""

    left_variant: EvaluationVariant
    right_variant: EvaluationVariant
    scenario_count: int = Field(ge=0)
    grounded_rate_delta: float
    root_cause_accuracy_delta: float
    unsupported_claim_rate_delta: float
    abstention_quality_delta: float
    mean_latency_ms_delta: float
    mean_model_calls_delta: float
    mean_tool_calls_delta: float
    total_estimated_cost_delta: float
    trajectory_success_rate_delta: float


class RepeatedVariantSummary(BaseModel):
    trial_count: int = Field(ge=1)
    grounded_rate_mean: float = Field(ge=0, le=1)
    grounded_rate_stddev: float = Field(ge=0)
    root_cause_accuracy_mean: float = Field(ge=0, le=1)
    root_cause_accuracy_stddev: float = Field(ge=0)
    unsupported_claim_rate_mean: float = Field(ge=0, le=1)
    unsupported_claim_rate_stddev: float = Field(ge=0)
    abstention_quality_mean: float = Field(ge=0, le=1)
    abstention_quality_stddev: float = Field(ge=0)
    mean_latency_ms_mean: float = Field(ge=0)
    mean_latency_ms_stddev: float = Field(ge=0)
    mean_model_calls_mean: float = Field(ge=0)
    mean_model_calls_stddev: float = Field(ge=0)
    mean_tool_calls_mean: float = Field(ge=0)
    mean_tool_calls_stddev: float = Field(ge=0)
    total_estimated_cost_mean: float = Field(ge=0)
    total_estimated_cost_stddev: float = Field(ge=0)
    recovery_rate_mean: float = Field(ge=0, le=1)
    recovery_rate_stddev: float = Field(ge=0)
    trajectory_success_rate_mean: float = Field(ge=0, le=1)
    trajectory_success_rate_stddev: float = Field(ge=0)


class HumanReview(BaseModel):
    """One blinded human comparison against an automated qualitative judgment."""

    scenario_id: str = Field(min_length=1)
    variant: EvaluationVariant
    automated_judgment: EvaluationJudgment
    human_judgment: EvaluationJudgment
    reviewer_reference: str = Field(min_length=1)


class JudgeCalibrationResult(BaseModel):
    sample_count: int = Field(ge=1)
    agreement_count: int = Field(ge=0)
    agreement_rate: float = Field(ge=0, le=1)
    disagreement_count: int = Field(ge=0)
    disagreements: list[str] = Field(default_factory=list)


class EvaluationRunStore:
    """Filesystem store for reproducible, comparable evaluation results."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, run_set_id: str) -> Path:
        if not run_set_id or Path(run_set_id).name != run_set_id:
            raise ValueError("evaluation run-set ID must be path-safe")
        return self.root / f"{run_set_id}.json"

    def save(self, run_set_id: str, run_set: EvaluationRunSet) -> None:
        path = self._path(run_set_id)
        encoded = json.dumps(run_set.model_dump(mode="json"), indent=2, sort_keys=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(encoded + "\n", encoding="utf-8")
        temporary.replace(path)

    def load(self, run_set_id: str) -> EvaluationRunSet:
        path = self._path(run_set_id)
        try:
            return EvaluationRunSet.model_validate(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError(f"evaluation run set is invalid: {run_set_id}") from exc


def compare_variant_runs(
    run_set: EvaluationRunSet,
    *,
    left_variant: EvaluationVariant,
    right_variant: EvaluationVariant,
) -> EvaluationComparison:
    """Compare two variants after run-set validation has established alignment."""
    selected = {run.variant: run for run in run_set.runs}
    if left_variant not in selected or right_variant not in selected:
        raise ValueError("both comparison variants must exist in the run set")
    left = selected[left_variant].aggregate
    right = selected[right_variant].aggregate
    return EvaluationComparison(
        left_variant=left_variant,
        right_variant=right_variant,
        scenario_count=left.scenario_count,
        grounded_rate_delta=right.grounded_rate - left.grounded_rate,
        root_cause_accuracy_delta=right.root_cause_accuracy - left.root_cause_accuracy,
        unsupported_claim_rate_delta=(
            right.unsupported_claim_rate - left.unsupported_claim_rate
        ),
        abstention_quality_delta=right.abstention_quality - left.abstention_quality,
        mean_latency_ms_delta=right.mean_latency_ms - left.mean_latency_ms,
        mean_model_calls_delta=right.mean_model_calls - left.mean_model_calls,
        mean_tool_calls_delta=right.mean_tool_calls - left.mean_tool_calls,
        total_estimated_cost_delta=right.total_estimated_cost - left.total_estimated_cost,
        trajectory_success_rate_delta=(
            right.trajectory_success_rate - left.trajectory_success_rate
        ),
    )


def calibrate_judge(reviews: Iterable[HumanReview]) -> JudgeCalibrationResult:
    """Compare automated qualitative judgments with a blinded human sample."""
    values = tuple(reviews)
    if not values:
        raise ValueError("at least one human review is required")
    disagreements = [
        f"{review.variant}:{review.scenario_id}"
        for review in values
        if review.automated_judgment != review.human_judgment
    ]
    agreement_count = len(values) - len(disagreements)
    return JudgeCalibrationResult(
        sample_count=len(values),
        agreement_count=agreement_count,
        agreement_rate=agreement_count / len(values),
        disagreement_count=len(disagreements),
        disagreements=disagreements,
    )


def run_repeated_evaluation(
    *,
    dataset: EvaluationDataset,
    split: EvaluationSplit,
    runner_factory: Callable[[], dict[EvaluationVariant, VariantRunner]],
    trials: int,
    dataset_version: str = "1.0",
    evaluation_version: str = "1.0",
    store: EvaluationRunStore | None = None,
    run_set_id_prefix: str | None = None,
) -> list[EvaluationRunSet]:
    """Run fresh variant adapters repeatedly over one development/evaluation split."""
    if trials < 1:
        raise ValueError("trials must be at least one")
    if (store is None) != (run_set_id_prefix is None):
        raise ValueError("store and run_set_id_prefix must be supplied together")

    run_sets = []
    for trial in range(1, trials + 1):
        run_sets.append(
            run_variant_suite(
                dataset=dataset,
                split=split,
                runners=runner_factory(),
                dataset_version=dataset_version,
                evaluation_version=evaluation_version,
                store=store,
                run_set_id=(
                    f"{run_set_id_prefix}-{trial:03d}"
                    if run_set_id_prefix is not None
                    else None
                ),
            )
        )
    return run_sets


def run_held_out_evaluation(
    *,
    dataset: EvaluationDataset,
    runners: dict[EvaluationVariant, VariantRunner],
    dataset_version: str = "1.0",
    evaluation_version: str = "1.0",
    store: EvaluationRunStore | None = None,
    run_set_id: str | None = None,
) -> EvaluationRunSet:
    """Run the frozen evaluation configuration against the held-out split once."""
    return run_variant_suite(
        dataset=dataset,
        split="held_out",
        runners=runners,
        dataset_version=dataset_version,
        evaluation_version=evaluation_version,
        store=store,
        run_set_id=run_set_id,
    )


def aggregate_repeated_runs(
    run_sets: Iterable[EvaluationRunSet],
) -> dict[EvaluationVariant, RepeatedVariantSummary]:
    """Summarize quality and efficiency variability across aligned trials."""
    values = tuple(run_sets)
    if not values:
        raise ValueError("at least one run set is required")
    variants = {run.variant for run in values[0].runs}
    for run_set in values[1:]:
        if {run.variant for run in run_set.runs} != variants:
            raise ValueError("repeated runs must contain the same variants")

    def metric(variant: EvaluationVariant, name: str) -> list[float]:
        return [
            float(getattr(next(run for run in run_set.runs if run.variant == variant).aggregate, name))
            for run_set in values
        ]

    def pair(variant: EvaluationVariant, name: str) -> tuple[float, float]:
        samples = metric(variant, name)
        return fmean(samples), pstdev(samples)

    summaries: dict[EvaluationVariant, RepeatedVariantSummary] = {}
    for variant in variants:
        grounded_mean, grounded_std = pair(variant, "grounded_rate")
        root_mean, root_std = pair(variant, "root_cause_accuracy")
        unsupported_mean, unsupported_std = pair(variant, "unsupported_claim_rate")
        abstention_mean, abstention_std = pair(variant, "abstention_quality")
        latency_mean, latency_std = pair(variant, "mean_latency_ms")
        model_mean, model_std = pair(variant, "mean_model_calls")
        tool_mean, tool_std = pair(variant, "mean_tool_calls")
        cost_mean, cost_std = pair(variant, "total_estimated_cost")
        recovery_mean, recovery_std = pair(variant, "recovery_rate")
        trajectory_mean, trajectory_std = pair(variant, "trajectory_success_rate")
        summaries[variant] = RepeatedVariantSummary(
            trial_count=len(values),
            grounded_rate_mean=grounded_mean,
            grounded_rate_stddev=grounded_std,
            root_cause_accuracy_mean=root_mean,
            root_cause_accuracy_stddev=root_std,
            unsupported_claim_rate_mean=unsupported_mean,
            unsupported_claim_rate_stddev=unsupported_std,
            abstention_quality_mean=abstention_mean,
            abstention_quality_stddev=abstention_std,
            mean_latency_ms_mean=latency_mean,
            mean_latency_ms_stddev=latency_std,
            mean_model_calls_mean=model_mean,
            mean_model_calls_stddev=model_std,
            mean_tool_calls_mean=tool_mean,
            mean_tool_calls_stddev=tool_std,
            total_estimated_cost_mean=cost_mean,
            total_estimated_cost_stddev=cost_std,
            recovery_rate_mean=recovery_mean,
            recovery_rate_stddev=recovery_std,
            trajectory_success_rate_mean=trajectory_mean,
            trajectory_success_rate_stddev=trajectory_std,
        )
    return summaries


class TrajectoryTrace(BaseModel):
    """Deterministic process facts collected during one variant execution."""

    allowed_tools: frozenset[str] = Field(default_factory=frozenset)
    requested_tools: list[str] = Field(default_factory=list)
    scope_violations: int = Field(default=0, ge=0)
    budget_exhausted: bool = False
    duplicate_tool_calls: int = Field(default=0, ge=0)
    branch_statuses: dict[str, str] = Field(default_factory=dict)
    branch_errors: dict[str, str] = Field(default_factory=dict)


class VariantExecution(BaseModel):
    """Provider-neutral output and measurements from one variant execution."""

    report: InvestigationReport
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    recovery_success: bool = True
    trajectory: TrajectoryTrace = Field(default_factory=TrajectoryTrace)


def check_trajectory(trace: TrajectoryTrace) -> bool:
    """Check objective process invariants without judging semantic quality."""
    unauthorized = set(trace.requested_tools) - set(trace.allowed_tools)
    return not unauthorized and trace.scope_violations == 0 and not trace.budget_exhausted


def deterministic_variant_runner(
    scenario: EvaluationScenario,
    view: AgentScenarioView,
) -> VariantExecution:
    """Run the fixture-backed deterministic baseline without evaluator labels."""
    fixture = load_agent_fixture(view.incident_fixture_path)
    evidence = [
        Evidence(
            evidence_id=record.record_id,
            source=record.signal_type,
            summary=_record_summary(record),
        )
        for record in fixture.telemetry
    ]
    statement = _deterministic_hypothesis(evidence)
    report = InvestigationReport(
        incident_id=view.scenario_id,
        summary=f"Deterministic analysis of {view.incident_title}.",
        evidence=evidence,
        hypotheses=[
            Hypothesis(
                statement=statement,
                confidence="medium",
                supporting_evidence_ids=[item.evidence_id for item in evidence],
            )
        ],
        status="completed",
    )
    trace = TrajectoryTrace(allowed_tools=frozenset(), requested_tools=[])
    return VariantExecution(report=report, tool_calls=0, trajectory=trace)


def build_agent_fixture_registry(fixture_path: str | Path) -> ToolRegistry:
    """Build the single-agent registry from the safe fixture projection only."""
    fixture = load_agent_fixture(fixture_path)
    evidence = [
        Evidence(
            evidence_id=record.record_id,
            source=record.signal_type,
            summary=_record_summary(record),
        )
        for record in fixture.telemetry
    ]

    def lookup(args: IncidentFixtureArgs) -> IncidentFixtureResult:
        if args.incident_id != fixture.manifest.incident_id:
            raise ValueError("fixture incident is outside the active evaluation scope")
        return IncidentFixtureResult(incident_id=args.incident_id, evidence=evidence)

    return ToolRegistry(
        [
            ToolSpec(
                name="lookup_incident_fixture",
                description="Read bounded evidence for the active synthetic incident.",
                args_schema=IncidentFixtureArgs,
                result_schema=IncidentFixtureResult,
                handler=lookup,
            )
        ]
    )


class _RecordingModelClient:
    def __init__(self, wrapped: ModelClient) -> None:
        self._wrapped = wrapped
        self.requested_tools: list[str] = []

    @property
    def last_usage(self) -> Any:
        return getattr(self._wrapped, "last_usage", None)

    def invoke(self, incident: IncidentInput, observations: list[BaseModel]) -> Any:
        raw_response = self._wrapped.invoke(incident, observations)
        response = validate_model_response(raw_response)
        if isinstance(response, ModelToolRequest):
            self.requested_tools.append(response.tool_call.name)
        return raw_response


class SingleAgentRunner:
    """Adapter from one bounded model agent to the evaluation runner contract."""

    def __init__(
        self,
        model_factory: Callable[[AgentScenarioView], ModelClient],
        *,
        max_steps: int = 4,
        model_budget_factory: Callable[[], ModelCallBudget] | None = None,
        tool_budget_factory: Callable[[], ModelCallBudget] | None = None,
    ) -> None:
        self._model_factory = model_factory
        self._max_steps = max_steps
        self._model_budget_factory = model_budget_factory
        self._tool_budget_factory = tool_budget_factory

    def __call__(
        self,
        scenario: EvaluationScenario,
        view: AgentScenarioView,
    ) -> VariantExecution:
        model = _RecordingModelClient(self._model_factory(view))
        tools = build_agent_fixture_registry(view.incident_fixture_path)
        incident = IncidentInput(
            incident_id=view.scenario_id,
            title=view.incident_title,
            affected_service=view.affected_service,
            start_time=view.start_time,
            end_time=view.end_time,
            summary=view.incident_summary,
        )
        started_at = perf_counter()
        try:
            result = run_agent_loop_with_metadata(
                incident=incident,
                model=model,
                tools=tools,
                max_steps=self._max_steps,
                model_budget=(
                    self._model_budget_factory() if self._model_budget_factory else None
                ),
                tool_budget=(
                    self._tool_budget_factory() if self._tool_budget_factory else None
                ),
            )
        except AgentLoopError as exc:
            return _failed_model_execution(
                incident_id=view.scenario_id,
                allowed_tools=frozenset(tools.tool_names),
                requested_tools=model.requested_tools,
                classification=_agent_loop_failure_classification(exc),
                model_calls=max(
                    1,
                    getattr(getattr(exc, "incident_error", None), "attempt_count", 0),
                ),
                tool_calls=len(model.requested_tools),
                latency_ms=(perf_counter() - started_at) * 1000,
            )
        return VariantExecution(
            report=result.report,
            model_calls=result.metadata.model_calls,
            tool_calls=result.metadata.tool_calls,
            latency_ms=result.metadata.elapsed_ms,
            trajectory=TrajectoryTrace(
                allowed_tools=frozenset(tools.tool_names),
                requested_tools=model.requested_tools,
            ),
        )


def _agent_loop_failure_classification(error: AgentLoopError) -> str:
    """Map internal loop failures to a stable, sanitized evaluation category."""
    if isinstance(error, ModelProviderError):
        return (
            error.incident_error.classification
            if error.incident_error is not None
            else "service_unavailable"
        )
    if isinstance(error, ModelBudgetExhaustedError):
        return "model_budget_exhausted"
    if isinstance(error, ToolBudgetExhaustedError):
        return "tool_budget_exhausted"
    if isinstance(error, InvalidModelResponseError):
        return "model_contract_violation"
    if isinstance(error, MaxStepsExceededError):
        return "model_step_limit_exhausted"
    return "agent_execution_error"


def _failed_model_execution(
    *,
    incident_id: str,
    allowed_tools: frozenset[str],
    requested_tools: list[str],
    classification: str,
    model_calls: int,
    tool_calls: int,
    latency_ms: float,
) -> VariantExecution:
    """Represent a model failure without fabricating a completed diagnosis."""
    report = InvestigationReport(
        incident_id=incident_id,
        summary=(
            "The investigation could not complete because model execution failed. "
            "No diagnostic conclusion was produced from the failed model call."
        ),
        hypotheses=[
            Hypothesis(
                statement="No diagnostic conclusion was produced.",
                confidence="low",
                missing_evidence=["valid model execution"],
            )
        ],
        status="failed",
    )
    return VariantExecution(
        report=report,
        model_calls=model_calls,
        tool_calls=tool_calls,
        latency_ms=latency_ms,
        recovery_success=False,
        trajectory=TrajectoryTrace(
            allowed_tools=allowed_tools,
            requested_tools=requested_tools,
            branch_errors={"model": classification},
        ),
    )


MultiAgentWorkerFactory = Callable[
    [AgentScenarioView], Worker
]
MultiAgentReportFactory = Callable[
    [AgentScenarioView, tuple[SpecialistFindingMessage, ...]], InvestigationReport
]


class MultiAgentRunner:
    """Adapter that executes all specialist branches through CoordinatorRuntime."""

    def __init__(
        self,
        worker_factory: MultiAgentWorkerFactory,
        *,
        report_factory: MultiAgentReportFactory | None = None,
        verification_enabled: bool = True,
        verifier_factory: Callable[[], VerifierAgent] = VerifierAgent,
        max_concurrency: int = 3,
        branch_timeout_seconds: float = 10,
        global_timeout_seconds: float | None = None,
    ) -> None:
        self._worker_factory = worker_factory
        self._report_factory = report_factory or _report_from_findings
        self._verification_enabled = verification_enabled
        self._verifier_factory = verifier_factory
        self._max_concurrency = max_concurrency
        self._branch_timeout_seconds = branch_timeout_seconds
        self._global_timeout_seconds = global_timeout_seconds

    def __call__(
        self,
        scenario: EvaluationScenario,
        view: AgentScenarioView,
    ) -> VariantExecution:
        fixture = load_agent_fixture(view.incident_fixture_path)
        evidence_by_signal = {
            signal_type: [
                record.record_id
                for record in fixture.telemetry
                if record.signal_type == signal_type
            ]
            for signal_type in ("log", "metric", "trace")
        }
        tasks = build_investigation_tasks(
            incident_id=view.scenario_id,
            time_window=fixture.manifest.time_window,
            affected_services=fixture.manifest.affected_services,
            evidence_by_signal=evidence_by_signal,
        )
        runtime = CoordinatorRuntime(
            tasks,
            self._worker_factory(view),
            max_concurrency=self._max_concurrency,
            branch_timeout_seconds=self._branch_timeout_seconds,
            global_timeout_seconds=self._global_timeout_seconds,
        )
        branches = runtime(SimpleNamespace(incident_id=view.scenario_id))
        findings = aggregate_findings(tasks, branches)
        report = self._report_factory(view, findings)
        if self._verification_enabled:
            report = _verify_report(report, view, self._verifier_factory())
        report = apply_coverage_to_report(report, branches)
        allowed_tools = frozenset(
            tool for task in tasks for tool in task.allowed_tools
        )
        requested_tools = [
            tool for branch in branches for tool in branch.requested_tools
        ]
        successful = all(branch.status == "success" for branch in branches)
        return VariantExecution(
            report=report,
            model_calls=sum(branch.model_calls for branch in branches),
            tool_calls=sum(branch.tool_calls for branch in branches),
            latency_ms=max((branch.latency_ms for branch in branches), default=0),
            recovery_success=successful,
            trajectory=TrajectoryTrace(
                allowed_tools=allowed_tools,
                requested_tools=requested_tools,
                budget_exhausted=any(
                    "budget" in (branch.error or "").casefold() for branch in branches
                ),
                branch_statuses={
                    branch.role.value: branch.status for branch in branches
                },
                branch_errors={
                    branch.role.value: branch.error
                    for branch in branches
                    if branch.error is not None
                },
            ),
        )


class MultiAgentWithoutVerifierRunner(MultiAgentRunner):
    """Multi-agent ablation that deliberately omits any verifier step."""

    def __init__(
        self,
        worker_factory: MultiAgentWorkerFactory,
        *,
        max_concurrency: int = 3,
        branch_timeout_seconds: float = 10,
        global_timeout_seconds: float | None = None,
    ) -> None:
        super().__init__(
            worker_factory,
            report_factory=_report_from_findings,
            verification_enabled=False,
            max_concurrency=max_concurrency,
            branch_timeout_seconds=branch_timeout_seconds,
            global_timeout_seconds=global_timeout_seconds,
        )


def _verify_report(
    report: InvestigationReport,
    view: AgentScenarioView,
    verifier: VerifierAgent,
) -> InvestigationReport:
    incident = IncidentInput(
        incident_id=view.scenario_id,
        title=view.incident_title,
        affected_service=view.affected_service,
        start_time=view.start_time,
        end_time=view.end_time,
        summary=report.summary,
    )
    candidates = [
        HypothesisCandidate(
            hypothesis_id=f"hypothesis-{index}",
            statement=hypothesis.statement,
            evidence=EvidenceTable(
                supporting_evidence_ids=hypothesis.supporting_evidence_ids,
                contradicting_evidence_ids=hypothesis.contradicting_evidence_ids,
                missing_evidence=hypothesis.missing_evidence,
            ),
            confidence=hypothesis.confidence,
            status=(
                "insufficient_evidence"
                if hypothesis.missing_evidence
                else "candidate"
            ),
        )
        for index, hypothesis in enumerate(report.hypotheses, start=1)
    ]
    verification = verifier.run(verifier.build_context(incident, candidates, report.evidence))
    results_by_id = {result.hypothesis_id: result for result in verification.results}
    updated_hypotheses = []
    report_is_inconclusive = report.status == "inconclusive"
    for index, hypothesis in enumerate(report.hypotheses, start=1):
        result = results_by_id[f"hypothesis-{index}"]
        report_is_inconclusive |= result.status == "insufficient_evidence"
        updated_hypotheses.append(
            hypothesis.model_copy(
                update={
                    "confidence": result.confidence,
                    "supporting_evidence_ids": result.supporting_evidence_ids,
                    "contradicting_evidence_ids": result.contradicting_evidence_ids,
                    "missing_evidence": result.missing_evidence,
                }
            )
        )
    return report.model_copy(
        update={
            "hypotheses": updated_hypotheses,
            "status": "inconclusive" if report_is_inconclusive else report.status,
            "summary": (
                f"{report.summary} Verification completed with deterministic evidence checks."
            ),
        }
    )


def _report_from_findings(
    view: AgentScenarioView,
    findings: tuple[SpecialistFindingMessage, ...],
) -> InvestigationReport:
    evidence = [
        Evidence(
            evidence_id=record.record_id,
            source=record.signal_type,
            summary=_record_summary(record),
        )
        for record in load_agent_fixture(view.incident_fixture_path).telemetry
    ]
    hypotheses = [
        Hypothesis(
            statement=finding.claim,
            confidence=finding.confidence,
            supporting_evidence_ids=finding.evidence_ids,
            missing_evidence=finding.open_questions,
        )
        for finding in findings
        if finding.evidence_ids
    ]
    if not hypotheses:
        hypotheses = [
            Hypothesis(
                statement="The available specialist evidence is insufficient to determine the cause.",
                confidence="low",
                missing_evidence=["additional specialist evidence"],
            )
        ]
    return InvestigationReport(
        incident_id=view.scenario_id,
        summary=f"Multi-agent analysis of {view.incident_title}.",
        evidence=evidence,
        hypotheses=hypotheses,
        status="completed",
    )


def _record_summary(record: Any) -> str:
    payload = ", ".join(f"{key}={value}" for key, value in sorted(record.payload.items()))
    metric = record.attributes.get("metric_name")
    prefix = f"{metric}: " if metric else ""
    return f"{prefix}{payload}" or f"{record.signal_type} observation"


def _deterministic_hypothesis(evidence: list[Evidence]) -> str:
    text = " ".join(item.summary.casefold() for item in evidence)
    if "connection_pool" in text or "database connection" in text:
        return "Database connection pool exhaustion affected checkout."
    if "returned 503" in text:
        return "Payment-service dependency failure affected checkout."
    if "request timed out" in text or "duration_ms" in text:
        return "Payment-service response delay affected checkout."
    return "The incident cause could not be determined from available telemetry."


def agent_view_excludes_labels(view: AgentScenarioView, scenario: EvaluationScenario) -> bool:
    """Return whether evaluator-only labels are absent from the serialized agent view."""
    agent_fields = set(AgentScenarioView.model_fields)
    evaluator_fields = {
        "expected_root_cause",
        "expected_evidence_ids",
        "acceptable_abstention",
        "required_evidence_sources",
    }
    return not agent_fields.intersection(evaluator_fields)


def cited_evidence_ids(report: InvestigationReport) -> set[str]:
    return {
        evidence_id
        for hypothesis in report.hypotheses
        for evidence_id in (
            hypothesis.supporting_evidence_ids + hypothesis.contradicting_evidence_ids
        )
    }


def check_report_grounding(
    report: InvestigationReport,
    available_evidence_ids: set[str],
) -> bool:
    if report.status == "failed":
        return False
    return cited_evidence_ids(report).issubset(available_evidence_ids)


def check_evidence_precision(
    report: InvestigationReport,
    expected_evidence_ids: set[str] | frozenset[str],
) -> float:
    cited = cited_evidence_ids(report)
    if not cited:
        return 1.0 if not expected_evidence_ids else 0.0
    return len(cited & set(expected_evidence_ids)) / len(cited)


def check_evidence_recall(
    report: InvestigationReport,
    expected_evidence_ids: set[str] | frozenset[str],
) -> float:
    expected = set(expected_evidence_ids)
    if not expected:
        return 1.0
    return len(cited_evidence_ids(report) & expected) / len(expected)


def check_root_cause_match(report: InvestigationReport, expected_root_cause: str) -> bool:
    expected = _normalize(expected_root_cause)
    return any(expected in _normalize(hypothesis.statement) for hypothesis in report.hypotheses)


def check_abstention(
    report: InvestigationReport,
    *,
    acceptable_abstention: bool,
    required_evidence_available: bool = True,
) -> bool:
    if report.status == "failed":
        return False
    if report.status == "inconclusive":
        return acceptable_abstention
    return report.status != "completed" or required_evidence_available


def validate_scenario_split(
    scenarios: Iterable[EvaluationScenario],
    requested_split: EvaluationSplit,
) -> tuple[EvaluationScenario, ...]:
    selected = tuple(scenario for scenario in scenarios if scenario.split == requested_split)
    if not selected:
        raise ValueError(f"no scenarios exist for split: {requested_split}")
    scenario_ids = [scenario.scenario_id for scenario in selected]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("evaluation scenario IDs must be unique within a split")
    return selected


def evaluate_execution(
    *,
    scenario: EvaluationScenario,
    variant: EvaluationVariant,
    execution: VariantExecution,
) -> EvaluationResult:
    """Score one completed variant execution using evaluator-only scenario labels."""
    available_fixture = load_agent_fixture(scenario.incident_fixture_path)
    available_ids = {record.record_id for record in available_fixture.telemetry}
    grounded = check_report_grounding(execution.report, available_ids)
    required_sources_available = scenario.required_evidence_sources.issubset(
        {record.source for record in execution.report.evidence}
    )
    abstained_appropriately = check_abstention(
        execution.report,
        acceptable_abstention=scenario.acceptable_abstention,
        required_evidence_available=required_sources_available,
    )
    completed_report_has_unsupported_hypothesis = (
        execution.report.status == "completed"
        and any(
            hypothesis.missing_evidence or not hypothesis.supporting_evidence_ids
            for hypothesis in execution.report.hypotheses
        )
    )
    unsupported_claim = execution.report.status != "failed" and (
        not grounded
        or not abstained_appropriately
        or completed_report_has_unsupported_hypothesis
    )
    unauthorized_tool_requests = len(
        set(execution.trajectory.requested_tools)
        - set(execution.trajectory.allowed_tools)
    )
    return EvaluationResult(
        scenario_id=scenario.scenario_id,
        variant=variant,
        split=scenario.split,
        grounded=grounded,
        root_cause_correct=grounded
        and check_root_cause_match(execution.report, scenario.expected_root_cause),
        unsupported_claim=unsupported_claim,
        abstained_appropriately=abstained_appropriately,
        evidence_precision=check_evidence_precision(
            execution.report, scenario.expected_evidence_ids
        ),
        evidence_recall=check_evidence_recall(execution.report, scenario.expected_evidence_ids),
        model_calls=execution.model_calls,
        tool_calls=execution.tool_calls,
        latency_ms=execution.latency_ms,
        estimated_cost=execution.estimated_cost,
        recovery_success=execution.recovery_success,
        trajectory_valid=check_trajectory(execution.trajectory),
        unauthorized_tool_requests=unauthorized_tool_requests,
        duplicate_tool_calls=execution.trajectory.duplicate_tool_calls,
        branch_statuses=execution.trajectory.branch_statuses,
        branch_errors=execution.trajectory.branch_errors,
    )


def aggregate_results(results: Iterable[EvaluationResult]) -> EvaluationAggregate:
    values = tuple(results)
    count = len(values)
    if count == 0:
        return EvaluationAggregate(
            scenario_count=0,
            grounded_rate=0,
            root_cause_accuracy=0,
            unsupported_claim_rate=0,
            abstention_quality=0,
            mean_evidence_precision=0,
            mean_evidence_recall=0,
            mean_model_calls=0,
            mean_tool_calls=0,
            mean_latency_ms=0,
            total_estimated_cost=0,
            recovery_rate=0,
            trajectory_success_rate=0,
            mean_unauthorized_tool_requests=0,
            mean_duplicate_tool_calls=0,
        )

    def rate(predicate: Callable[[EvaluationResult], bool]) -> float:
        return sum(predicate(item) for item in values) / count

    return EvaluationAggregate(
        scenario_count=count,
        grounded_rate=rate(lambda item: item.grounded),
        root_cause_accuracy=rate(lambda item: item.root_cause_correct),
        unsupported_claim_rate=rate(lambda item: item.unsupported_claim),
        abstention_quality=rate(lambda item: item.abstained_appropriately),
        mean_evidence_precision=sum(item.evidence_precision for item in values) / count,
        mean_evidence_recall=sum(item.evidence_recall for item in values) / count,
        mean_model_calls=sum(item.model_calls for item in values) / count,
        mean_tool_calls=sum(item.tool_calls for item in values) / count,
        mean_latency_ms=sum(item.latency_ms for item in values) / count,
        total_estimated_cost=sum(item.estimated_cost for item in values),
        recovery_rate=rate(lambda item: item.recovery_success),
        trajectory_success_rate=rate(lambda item: item.trajectory_valid),
        mean_unauthorized_tool_requests=sum(
            item.unauthorized_tool_requests for item in values
        )
        / count,
        mean_duplicate_tool_calls=sum(item.duplicate_tool_calls for item in values) / count,
    )


VariantRunner = Callable[[EvaluationScenario, AgentScenarioView], VariantExecution]


class VariantRunnerAdapter:
    """Named adapter that binds one execution implementation to an evaluator variant."""

    def __init__(self, variant: EvaluationVariant, runner: VariantRunner) -> None:
        self.variant = variant
        self._runner = runner

    def __call__(
        self,
        scenario: EvaluationScenario,
        view: AgentScenarioView,
    ) -> VariantExecution:
        execution = self._runner(scenario, view)
        if not isinstance(execution, VariantExecution):
            raise TypeError(f"{self.variant} runner returned an invalid execution")
        return execution


def build_variant_adapters(
    *,
    single_agent: VariantRunner,
    multi_agent: VariantRunner,
    multi_agent_without_verifier: VariantRunner,
) -> dict[EvaluationVariant, VariantRunner]:
    """Bind real workflow implementations to stable evaluation variant names."""
    return {
        "deterministic": VariantRunnerAdapter("deterministic", deterministic_variant_runner),
        "single_agent": VariantRunnerAdapter("single_agent", single_agent),
        "multi_agent": VariantRunnerAdapter("multi_agent", multi_agent),
        "multi_agent_without_verifier": VariantRunnerAdapter(
            "multi_agent_without_verifier", multi_agent_without_verifier
        ),
    }


def run_variant_suite(
    *,
    dataset: EvaluationDataset,
    split: EvaluationSplit,
    runners: dict[EvaluationVariant, VariantRunner],
    dataset_version: str = "1.0",
    evaluation_version: str = "1.0",
    store: EvaluationRunStore | None = None,
    run_set_id: str | None = None,
) -> EvaluationRunSet:
    """Run supplied variant adapters over the same split and optionally persist them."""
    if not runners:
        raise ValueError("at least one variant runner is required")
    runs = [
        run_variant_evaluation(
            dataset=dataset,
            split=split,
            variant=variant,
            runner=runner,
            evaluation_version=evaluation_version,
        )
        for variant, runner in runners.items()
    ]
    run_set = EvaluationRunSet(
        dataset_version=dataset_version,
        split=split,
        runs=runs,
    )
    if (store is None) != (run_set_id is None):
        raise ValueError("store and run_set_id must be supplied together")
    if store is not None and run_set_id is not None:
        store.save(run_set_id, run_set)
    return run_set


def run_variant_evaluation(
    *,
    dataset: EvaluationDataset,
    split: EvaluationSplit,
    variant: EvaluationVariant,
    runner: VariantRunner,
    evaluation_version: str = "1.0",
) -> EvaluationRun:
    """Run one variant over one split and return reproducible per-case and aggregate scores."""
    scenarios = dataset.for_split(split)
    results = []
    for scenario in scenarios:
        view = dataset.agent_view(scenario.scenario_id)
        execution = runner(scenario, view)
        results.append(
            evaluate_execution(
                scenario=scenario,
                variant=variant,
                execution=execution,
            )
        )
    return EvaluationRun(
        evaluation_version=evaluation_version,
        variant=variant,
        split=split,
        results=results,
        aggregate=aggregate_results(results),
    )


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())
