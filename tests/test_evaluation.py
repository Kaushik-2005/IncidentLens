import json

import pytest

from incidentlens.contracts import (
    Evidence,
    Hypothesis,
    InvestigationReport,
    ModelFinalReport,
    ModelToolRequest,
    ToolCall,
)
from incidentlens.evaluation import (
    AgentScenarioView,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    EvaluationRunSet,
    EvaluationRunStore,
    EvaluationScenario,
    HumanReview,
    MultiAgentRunner,
    MultiAgentWithoutVerifierRunner,
    SingleAgentRunner,
    TrajectoryTrace,
    VariantExecution,
    agent_view_excludes_labels,
    aggregate_repeated_runs,
    aggregate_results,
    build_variant_adapters,
    calibrate_judge,
    check_abstention,
    check_evidence_precision,
    check_evidence_recall,
    check_report_grounding,
    check_root_cause_match,
    check_trajectory,
    compare_variant_runs,
    deterministic_variant_runner,
    evaluate_execution,
    run_held_out_evaluation,
    run_repeated_evaluation,
    run_variant_evaluation,
    run_variant_suite,
    validate_scenario_split,
)
from incidentlens.specialists import FindingKind


def scenario(**updates) -> EvaluationScenario:
    values = {
        "scenario_id": "payment-001",
        "split": "development",
        "incident_fixture_path": "fixtures/incidents/payment_latency.json",
        "expected_root_cause": "payment-service degradation",
        "expected_evidence_ids": {"L1", "T1"},
        "acceptable_abstention": True,
        "required_evidence_sources": {"log", "trace"},
    }
    values.update(updates)
    return EvaluationScenario(**values)


def report(*, status="completed", supporting=None, contradicting=None, missing=None):
    return InvestigationReport(
        incident_id="payment-001",
        summary="Payment service degradation affected checkout.",
        evidence=[
            Evidence(evidence_id="L1", source="log", summary="Timeouts increased."),
            Evidence(evidence_id="T1", source="trace", summary="Payment span was slow."),
            Evidence(evidence_id="X1", source="metric", summary="Distractor metric."),
        ],
        hypotheses=[
            Hypothesis(
                statement="Payment-service degradation affected checkout.",
                confidence="medium",
                supporting_evidence_ids=supporting or [],
                contradicting_evidence_ids=contradicting or [],
                missing_evidence=missing or [],
            )
        ],
        status=status,
    )


def test_agent_view_excludes_evaluator_labels() -> None:
    hidden = scenario()
    view = AgentScenarioView.from_payload(
        scenario=hidden,
        incident_title="Checkout latency",
        affected_service="checkout-api",
        start_time="2026-09-10T10:00:00Z",
        incident_summary="Checkout latency increased.",
    )

    assert agent_view_excludes_labels(view, hidden)
    assert "payment-service degradation" not in view.model_dump_json()
    assert "L1" not in view.model_dump_json()


def test_grounding_rejects_unknown_citation() -> None:
    result = report(supporting=["X1"])

    assert not check_report_grounding(result, {"L1", "T1"})


def test_failed_report_is_not_counted_as_grounded_or_abstained() -> None:
    result = report(status="failed")

    assert not check_report_grounding(result, {"L1", "T1", "X1"})
    assert not check_abstention(result, acceptable_abstention=True)


def test_precision_and_recall_are_computed_from_citations() -> None:
    result = report(supporting=["L1", "T1", "X1"])

    assert check_evidence_precision(result, {"L1", "T1"}) == pytest.approx(2 / 3)
    assert check_evidence_recall(result, {"L1", "T1"}) == 1.0


def test_root_cause_match_is_case_and_whitespace_insensitive() -> None:
    result = report(supporting=["L1"])

    assert check_root_cause_match(result, " PAYMENT-service   degradation ")


def test_inconclusive_report_is_correct_when_abstention_is_acceptable() -> None:
    result = report(status="inconclusive", missing=["metric saturation"])

    assert check_abstention(result, acceptable_abstention=True)
    assert not check_abstention(result, acceptable_abstention=False)


def test_completed_report_is_wrong_when_required_evidence_is_unavailable() -> None:
    result = report(supporting=["L1"])

    assert not check_abstention(
        result,
        acceptable_abstention=True,
        required_evidence_available=False,
    )


def test_split_validation_selects_only_requested_split() -> None:
    scenarios = [scenario(), scenario(scenario_id="payment-002", split="held_out")]

    selected = validate_scenario_split(scenarios, "held_out")

    assert [item.scenario_id for item in selected] == ["payment-002"]


def test_split_validation_rejects_empty_split() -> None:
    with pytest.raises(ValueError, match="no scenarios"):
        validate_scenario_split([scenario()], "held_out")


def test_versioned_dataset_projects_only_agent_safe_fixture_fields() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")

    view = dataset.agent_view("db-exhaustion-001")

    assert view.scenario_id == "db-exhaustion-001"
    assert "database connection pool exhaustion" not in view.model_dump_json()
    assert "db-metric-1" not in view.model_dump_json()


def test_dataset_requires_unique_scenario_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        EvaluationDataset(scenarios=[scenario(), scenario()])


def test_agent_view_rejects_scenario_fixture_identity_mismatch(tmp_path) -> None:
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "manifest": {
                    "schema_version": "1.0",
                    "incident_id": "different-incident",
                    "title": "Synthetic incident",
                    "time_window": {
                        "start": "2025-01-01T00:00:00Z",
                        "end": "2025-01-01T00:05:00Z",
                    },
                    "affected_services": ["checkout"],
                    "telemetry_record_ids": ["r1"],
                },
                "telemetry": [
                    {
                        "schema_version": "1.0",
                        "record_id": "r1",
                        "signal_type": "log",
                        "timestamp": "2025-01-01T00:01:00Z",
                        "normalized_timestamp": "2025-01-01T00:01:00Z",
                        "payload": {"message": "synthetic"},
                        "provenance": {
                            "source_type": "fixture",
                            "source_name": "mismatch-test",
                        },
                    }
                ],
                "hidden_ground_truth": {
                    "root_cause": "hidden",
                    "expected_evidence_ids": [],
                },
            }
        ),
        encoding="utf-8",
    )
    dataset = EvaluationDataset(
        scenarios=[
            scenario(
                scenario_id="declared-incident",
                incident_fixture_path=str(fixture_path),
            )
        ]
    )

    with pytest.raises(ValueError, match="does not match"):
        dataset.agent_view("declared-incident")


def test_evaluation_run_requires_matching_result_configuration() -> None:
    result = EvaluationResult(
        scenario_id="payment-001",
        variant="single_agent",
        split="development",
        grounded=True,
        root_cause_correct=True,
        unsupported_claim=False,
        abstained_appropriately=True,
        evidence_precision=1,
        evidence_recall=1,
        model_calls=1,
        tool_calls=1,
        latency_ms=10,
        recovery_success=True,
    )

    with pytest.raises(ValueError, match="do not match"):
        EvaluationRun(
            evaluation_version="1.0",
            variant="multi_agent",
            split="development",
            results=[result],
            aggregate={
                "scenario_count": 1,
                "grounded_rate": 1,
                "root_cause_accuracy": 1,
                "unsupported_claim_rate": 0,
                "abstention_quality": 1,
                "mean_evidence_precision": 1,
                "mean_evidence_recall": 1,
                "mean_model_calls": 1,
                "mean_tool_calls": 1,
                "mean_latency_ms": 10,
                "total_estimated_cost": 0,
                "recovery_rate": 1,
            },
        )


def test_aggregate_results_computes_quality_and_efficiency_metrics() -> None:
    results = [
        EvaluationResult(
            scenario_id="payment-001",
            variant="deterministic",
            split="development",
            grounded=True,
            root_cause_correct=True,
            unsupported_claim=False,
            abstained_appropriately=True,
            evidence_precision=1,
            evidence_recall=0.5,
            model_calls=0,
            tool_calls=3,
            latency_ms=10,
            estimated_cost=0,
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
            recovery_success=True,
        ),
        EvaluationResult(
            scenario_id="payment-002",
            variant="deterministic",
            split="development",
            grounded=False,
            root_cause_correct=False,
            unsupported_claim=True,
            abstained_appropriately=False,
            evidence_precision=0.5,
            evidence_recall=0,
            model_calls=0,
            tool_calls=4,
            latency_ms=20,
            estimated_cost=0,
            input_tokens=300,
            output_tokens=100,
            total_tokens=400,
            recovery_success=True,
        ),
    ]

    aggregate = aggregate_results(results)

    assert aggregate.scenario_count == 2
    assert aggregate.grounded_rate == 0.5
    assert aggregate.root_cause_accuracy == 0.5
    assert aggregate.unsupported_claim_rate == 0.5
    assert aggregate.mean_tool_calls == 3.5
    assert aggregate.mean_latency_ms == 15
    assert aggregate.mean_input_tokens == 200
    assert aggregate.mean_output_tokens == 70
    assert aggregate.mean_total_tokens == 270


def test_run_variant_evaluation_scores_deterministic_runner_on_held_out_split() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")

    def deterministic_runner(scenario, _view):
        if scenario.scenario_id == "db-exhaustion-001":
            report_value = InvestigationReport(
                incident_id="db-exhaustion-001",
                summary="Database connection pool exhaustion affected checkout.",
                evidence=[
                    Evidence(
                        evidence_id="db-metric-1",
                        source="metric",
                        summary="Connection pool reached capacity.",
                    )
                ],
                hypotheses=[
                    Hypothesis(
                        statement="Database connection pool exhaustion affected checkout.",
                        confidence="medium",
                        supporting_evidence_ids=["db-metric-1"],
                    )
                ],
                status="completed",
            )
            return VariantExecution(report=report_value, tool_calls=1, latency_ms=12)
        raise AssertionError("unexpected scenario")

    evaluation = run_variant_evaluation(
        dataset=dataset,
        split="held_out",
        variant="deterministic",
        runner=deterministic_runner,
    )

    assert evaluation.aggregate.scenario_count == 1
    assert evaluation.results[0].root_cause_correct


def test_deterministic_variant_runner_scores_all_available_splits() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")

    development = run_variant_evaluation(
        dataset=dataset,
        split="development",
        variant="deterministic",
        runner=deterministic_variant_runner,
    )
    held_out = run_variant_evaluation(
        dataset=dataset,
        split="held_out",
        variant="deterministic",
        runner=deterministic_variant_runner,
    )

    assert development.aggregate.scenario_count == 2
    assert development.aggregate.trajectory_success_rate == 1
    assert held_out.aggregate.root_cause_accuracy == 1
    assert held_out.results[0].tool_calls == 0


def test_trajectory_evaluator_rejects_unauthorized_and_scoped_requests() -> None:
    trace = TrajectoryTrace(
        allowed_tools=frozenset({"query_logs"}),
        requested_tools=["query_logs", "read_environment_secrets"],
        scope_violations=1,
    )

    assert not check_trajectory(trace)


def test_evaluate_execution_records_trajectory_failures() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    scenario_value = dataset.for_split("development")[0]
    view = dataset.agent_view(scenario_value.scenario_id)
    execution = deterministic_variant_runner(scenario_value, view).model_copy(
        update={
            "trajectory": TrajectoryTrace(
                allowed_tools=frozenset({"query_logs"}),
                requested_tools=["read_environment_secrets"],
            )
        }
    )

    result = evaluate_execution(
        scenario=scenario_value,
        variant="deterministic",
        execution=execution,
    )

    assert not result.trajectory_valid
    assert result.unauthorized_tool_requests == 1


def test_variant_suite_persists_comparable_runs(tmp_path) -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    store = EvaluationRunStore(tmp_path / "evaluation-runs")

    run_set = run_variant_suite(
        dataset=dataset,
        split="held_out",
        runners={
            "deterministic": deterministic_variant_runner,
            "single_agent": deterministic_variant_runner,
        },
        store=store,
        run_set_id="held-out-baseline",
    )
    loaded = store.load("held-out-baseline")

    assert isinstance(run_set, EvaluationRunSet)
    assert [run.variant for run in loaded.runs] == ["deterministic", "single_agent"]
    assert all(run.aggregate.scenario_count == 1 for run in loaded.runs)
    assert loaded.runs[0].results[0].scenario_id == loaded.runs[1].results[0].scenario_id

    comparison = compare_variant_runs(
        loaded,
        left_variant="deterministic",
        right_variant="single_agent",
    )
    assert comparison.scenario_count == 1
    assert comparison.grounded_rate_delta == 0
    assert comparison.mean_tool_calls_delta == 0


def test_variant_suite_rejects_partial_persistence_arguments() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")

    with pytest.raises(ValueError, match="supplied together"):
        run_variant_suite(
            dataset=dataset,
            split="held_out",
            runners={"deterministic": deterministic_variant_runner},
            run_set_id="without-store",
        )


def test_repeated_evaluation_uses_fresh_runner_factories_and_aggregates_trials(tmp_path) -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    store = EvaluationRunStore(tmp_path / "repeated-runs")
    created = []

    def runner_factory():
        created.append(object())
        return {
            "deterministic": deterministic_variant_runner,
            "single_agent": deterministic_variant_runner,
        }

    runs = run_repeated_evaluation(
        dataset=dataset,
        split="development",
        runner_factory=runner_factory,
        trials=2,
        store=store,
        run_set_id_prefix="development-trial",
    )
    summaries = aggregate_repeated_runs(runs)

    assert len(runs) == 2
    assert len(created) == 2
    assert summaries["deterministic"].trial_count == 2
    assert summaries["deterministic"].grounded_rate_mean == 1
    assert summaries["deterministic"].grounded_rate_stddev == 0
    assert store.load("development-trial-001").split == "development"


def test_held_out_evaluation_uses_only_the_frozen_held_out_split(tmp_path) -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    store = EvaluationRunStore(tmp_path / "held-out-runs")

    run_set = run_held_out_evaluation(
        dataset=dataset,
        runners={"deterministic": deterministic_variant_runner},
        store=store,
        run_set_id="held-out-final",
    )

    assert run_set.split == "held_out"
    assert run_set.runs[0].aggregate.scenario_count == 1
    assert run_set.runs[0].results[0].scenario_id == "db-exhaustion-001"
    assert store.load("held-out-final").split == "held_out"


def test_judge_calibration_reports_human_disagreements() -> None:
    result = calibrate_judge(
        [
            HumanReview(
                scenario_id="s1",
                variant="multi_agent",
                automated_judgment="supported",
                human_judgment="supported",
                reviewer_reference="review-1",
            ),
            HumanReview(
                scenario_id="s2",
                variant="multi_agent",
                automated_judgment="supported",
                human_judgment="inconclusive",
                reviewer_reference="review-1",
            ),
        ]
    )

    assert result.sample_count == 2
    assert result.agreement_rate == 0.5
    assert result.disagreements == ["multi_agent:s2"]


def test_named_variant_adapters_share_one_execution_contract() -> None:
    adapters = build_variant_adapters(
        single_agent=deterministic_variant_runner,
        multi_agent=deterministic_variant_runner,
        multi_agent_without_verifier=deterministic_variant_runner,
    )

    assert set(adapters) == {
        "deterministic",
        "single_agent",
        "multi_agent",
        "multi_agent_without_verifier",
    }
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    scenario_value = dataset.for_split("held_out")[0]
    view = dataset.agent_view(scenario_value.scenario_id)
    assert adapters["multi_agent_without_verifier"](scenario_value, view).report.incident_id == view.scenario_id


def test_single_agent_runner_uses_safe_fixture_tool_and_records_usage() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    scenario_value = dataset.for_split("held_out")[0]
    view = dataset.agent_view(scenario_value.scenario_id)

    class ScriptedSingleAgent:
        def invoke(self, _incident, observations):
            if not observations:
                return ModelToolRequest(
                    tool_call=ToolCall(
                        name="lookup_incident_fixture",
                        arguments={"incident_id": view.scenario_id},
                    )
                )
            return ModelFinalReport(
                report=InvestigationReport(
                    incident_id=view.scenario_id,
                    summary="The database pool reached capacity.",
                    evidence=[
                        Evidence(
                            evidence_id="db-metric-1",
                            source="metric",
                            summary="Connection pool reached capacity.",
                        )
                    ],
                    hypotheses=[
                        Hypothesis(
                            statement="Database connection pool exhaustion affected checkout.",
                            confidence="medium",
                            supporting_evidence_ids=["db-metric-1"],
                        )
                    ],
                    status="completed",
                )
            )

    execution = SingleAgentRunner(lambda _view: ScriptedSingleAgent())(
        scenario_value,
        view,
    )

    assert execution.report.incident_id == view.scenario_id
    assert execution.model_calls == 2
    assert execution.tool_calls == 1
    assert execution.trajectory.requested_tools == ["lookup_incident_fixture"]
    assert "hidden_ground_truth" not in execution.report.model_dump_json()


def test_multi_agent_runner_uses_coordinator_runtime_and_preserves_coverage() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    scenario_value = dataset.for_split("held_out")[0]
    view = dataset.agent_view(scenario_value.scenario_id)

    async def worker(task):
        return [
            {
                "task_id": task.task_id,
                "finding_id": f"{task.task_id}-finding",
                "incident_id": task.incident_id,
                "agent_id": task.specialist_role.value,
                "specialist_role": task.specialist_role,
                "claim_kind": FindingKind.OBSERVATION,
                "claim": f"Observed {task.specialist_role.value} evidence.",
                "evidence_ids": [task.evidence_refs[0]],
                "confidence": "medium",
            }
        ]

    execution = MultiAgentRunner(
        lambda _view: worker,
        branch_timeout_seconds=1,
    )(scenario_value, view)

    assert execution.report.incident_id == view.scenario_id
    assert execution.report.status == "inconclusive"
    assert len(execution.report.hypotheses) == 2
    assert execution.trajectory.allowed_tools
    assert "Verification completed" in execution.report.summary


def test_no_verifier_runner_reuses_specialist_path_without_verification() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    scenario_value = dataset.for_split("held_out")[0]
    view = dataset.agent_view(scenario_value.scenario_id)

    async def worker(task):
        return [
            {
                "task_id": task.task_id,
                "finding_id": f"{task.task_id}-finding",
                "incident_id": task.incident_id,
                "agent_id": task.specialist_role.value,
                "specialist_role": task.specialist_role,
                "claim_kind": FindingKind.INFERENCE,
                "claim": f"Observed {task.specialist_role.value} evidence.",
                "evidence_ids": [task.evidence_refs[0]],
                "confidence": "high",
            }
        ]

    execution = MultiAgentWithoutVerifierRunner(
        lambda _view: worker,
        branch_timeout_seconds=1,
    )(scenario_value, view)

    assert execution.report.status == "inconclusive"
    assert all(hypothesis.confidence == "high" for hypothesis in execution.report.hypotheses)
    assert "Verification completed" not in execution.report.summary
