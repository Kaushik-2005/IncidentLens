"""Run repeated development comparisons across the four evaluation variants."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from incidentlens.contracts import (
    Evidence,
    Hypothesis,
    IncidentInput,
    InvestigationReport,
    ModelFinalReport,
)
from incidentlens.evaluation import (
    EvaluationDataset,
    EvaluationRunStore,
    MultiAgentRunner,
    MultiAgentWithoutVerifierRunner,
    SingleAgentRunner,
    aggregate_repeated_runs,
    build_agent_fixture_registry,
    build_variant_adapters,
    run_repeated_evaluation,
)
from incidentlens.specialist_runtime import build_model_backed_worker
from incidentlens.specialists import SpecialistRole, build_role_tool_registry
from incidentlens.telemetry import load_agent_fixture

VARIANTS = (
    "deterministic",
    "single_agent",
    "multi_agent",
    "multi_agent_without_verifier",
)


class OfflineEvaluationModel:
    """Deterministic model substitute for evaluation plumbing and ablation tests.

    It reads only the agent-safe fixture projection and never accesses evaluator labels.
    The model emits one structured report, making this mode reproducible without Gemini
    quota, network access, or secrets.
    """

    def __init__(self, fixture_path, role: SpecialistRole | None = None):
        fixture = load_agent_fixture(fixture_path)
        allowed_sources = (
            {"log", "metric", "trace"}
            if role is None
            else {
                SpecialistRole.LOGS: {"log"},
                SpecialistRole.METRICS: {"metric"},
                SpecialistRole.TRACES: {"trace"},
            }[role]
        )
        self._evidence = [
            Evidence(
                evidence_id=record.record_id,
                source=record.signal_type,
                summary=_safe_record_summary(record),
            )
            for record in fixture.telemetry
            if record.signal_type in allowed_sources
        ]
        self.last_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    def invoke(self, incident: IncidentInput, _observations):
        text = " ".join(item.summary.casefold() for item in self._evidence)
        if "connection_pool" in text or "database connection" in text:
            statement = "Database connection pool exhaustion affected checkout."
        elif "returned 503" in text:
            statement = "Payment-service dependency failure affected checkout."
        elif "request timed out" in text or "duration_ms" in text:
            statement = "Payment-service response delay affected checkout."
        else:
            statement = "The incident cause could not be determined from available telemetry."
        report = InvestigationReport(
            incident_id=incident.incident_id,
            summary="Offline scripted analysis using safe fixture telemetry.",
            evidence=self._evidence,
            hypotheses=[
                Hypothesis(
                    statement=statement,
                    confidence="medium",
                    supporting_evidence_ids=[item.evidence_id for item in self._evidence],
                )
            ],
            status="completed" if self._evidence else "inconclusive",
        )
        return ModelFinalReport(report=report)


def _safe_record_summary(record) -> str:
    payload = ", ".join(
        f"{key}={value}" for key, value in sorted(record.payload.items())
    )
    metric = record.attributes.get("metric_name")
    prefix = f"{metric}: " if metric else ""
    return f"{prefix}{payload}" or f"{record.signal_type} observation"


def build_runners(settings):
    from incidentlens.model_adapter import GeminiLangChainModelClient

    def single_model(view):
        return GeminiLangChainModelClient.from_settings(
            settings=settings,
            tools=build_agent_fixture_registry(view.incident_fixture_path),
        )

    def worker_factory(view):
        registries = {
            role: build_role_tool_registry(role, view.incident_fixture_path)
            for role in SpecialistRole
        }
        models = {
            role: GeminiLangChainModelClient.from_settings(
                settings=settings,
                tools=registries[role],
            )
            for role in SpecialistRole
        }
        return build_model_backed_worker(models, registries)

    return build_variant_adapters(
        single_agent=SingleAgentRunner(
            single_model,
            max_steps=settings.max_agent_steps,
        ),
        multi_agent=MultiAgentRunner(
            worker_factory,
            max_concurrency=3,
            branch_timeout_seconds=10,
        ),
        multi_agent_without_verifier=MultiAgentWithoutVerifierRunner(
            worker_factory,
            max_concurrency=3,
            branch_timeout_seconds=10,
        ),
    )


def build_offline_runners():
    """Build all variants without provider calls for reproducible comparisons."""

    def single_model(view):
        return OfflineEvaluationModel(view.incident_fixture_path)

    def worker_factory(view):
        models = {
            role: OfflineEvaluationModel(view.incident_fixture_path, role)
            for role in SpecialistRole
        }
        registries = {
            role: build_role_tool_registry(role, view.incident_fixture_path)
            for role in SpecialistRole
        }
        return build_model_backed_worker(models, registries)

    return build_variant_adapters(
        single_agent=SingleAgentRunner(single_model),
        multi_agent=MultiAgentRunner(worker_factory),
        multi_agent_without_verifier=MultiAgentWithoutVerifierRunner(worker_factory),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", "--trails", dest="trials", type=int, default=1)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use the deterministic scripted model instead of Gemini.",
    )
    parser.add_argument(
        "--variant",
        choices=("all", *VARIANTS),
        default="all",
        help="Run one evaluation variant to limit provider usage (default: all).",
    )
    args = parser.parse_args()

    if args.offline:
        settings = None
    else:
        from incidentlens.config import Settings

        settings = Settings()
        if not settings.google_api_key:
            raise SystemExit("INCIDENTLENS_GOOGLE_API_KEY is required for model-backed evaluation")

    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    store = EvaluationRunStore("artifacts/evaluation")
    def runner_factory():
        runners = (
            build_offline_runners()
            if args.offline
            else build_runners(settings)
        )
        if args.variant == "all":
            return runners
        return {args.variant: runners[args.variant]}

    run_sets = run_repeated_evaluation(
        dataset=dataset,
        split="development",
        runner_factory=runner_factory,
        trials=args.trials,
        store=store,
        run_set_id_prefix=(
            f"development-comparison-{args.variant}-{'offline' if args.offline else 'live'}"
        ),
    )
    summaries = aggregate_repeated_runs(run_sets)
    comparison = None
    if args.variant == "all":
        comparison = {
            "multi_agent_vs_without_verifier": {
                "unsupported_claim_rate_delta": (
                    summaries["multi_agent_without_verifier"].unsupported_claim_rate_mean
                    - summaries["multi_agent"].unsupported_claim_rate_mean
                ),
                "abstention_quality_delta": (
                    summaries["multi_agent_without_verifier"].abstention_quality_mean
                    - summaries["multi_agent"].abstention_quality_mean
                ),
                "mean_latency_ms_delta": (
                    summaries["multi_agent_without_verifier"].mean_latency_ms_mean
                    - summaries["multi_agent"].mean_latency_ms_mean
                ),
                "mean_model_calls_delta": (
                    summaries["multi_agent_without_verifier"].mean_model_calls_mean
                    - summaries["multi_agent"].mean_model_calls_mean
                ),
                "mean_total_tokens_delta": (
                    summaries["multi_agent_without_verifier"].mean_total_tokens_mean
                    - summaries["multi_agent"].mean_total_tokens_mean
                ),
                "estimated_cost_delta": (
                    summaries["multi_agent_without_verifier"].total_estimated_cost_mean
                    - summaries["multi_agent"].total_estimated_cost_mean
                ),
            }
        }
    output = {variant: summary.model_dump(mode="json") for variant, summary in summaries.items()}
    if comparison is not None:
        output["ablation_comparison"] = comparison
    print(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"Persisted {len(run_sets)} development run set(s) under artifacts/evaluation/"
    )


if __name__ == "__main__":
    main()
