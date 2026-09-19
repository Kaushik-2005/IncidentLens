# IncidentLens Learning Tracker

## Current position
- Roadmap: ../roadmap.md
- Module: 15 - Evaluation, ablations, observability, and optimization
- Phase: Orient
- Status: In Progress
- Mode: Guided Learning
- Exact current task: orient Module 15 around evaluation design, ablations, observability, and optimization.
- Last completed evidence: Module 14 completed through reliability/security implementation, final conceptual review, debugging analysis, failure-matrix design, and full validation.

## Module progress
| Module | Title | Implementation | Understanding | Overall |
| --- | --- | --- | --- | --- |
| 1 | Multi-agent foundations and project contract | Completed | Checked | Completed |
| 2 | Gemini agent loop and single-agent baseline | Completed | Checked | Completed |
| 3 | Incident-response domain and realistic telemetry | Completed | Checked | Completed |
| 4 | Tool engineering and the observation boundary | Completed | Checked | Completed |
| 5 | LangGraph state and deterministic orchestration | Completed | Checked | Completed |
| 6 | Specialization and context engineering | Completed | Checked | Completed |
| 7 | Coordination topologies and protocol design | Completed | Checked | Completed |
| 8 | Parallel investigation and evidence aggregation | Completed | Checked | Completed |
| 9 | Memory, persistence, checkpoints, and artifacts | Completed | Checked | Completed |
| 10 | Planning, adaptive routing, budgets, and termination | Completed | Checked | Completed |
| 11 | Runbook RAG and change intelligence | Completed | Checked | Completed |
| 12 | Hypothesis formation, critique, and calibrated confidence | Completed | Checked | Completed |
| 13 | Human oversight, authorization, and safe actions | Completed | Checked | Completed |
| 14 | Reliability, security, and adversarial behavior | Completed | Checked | Completed |
| 15 | Evaluation, ablations, observability, and optimization | Not started | Not checked | Not started |
| 16 | Productization, live telemetry, and resume-grade capstone | Not started | Not checked | Not started |

## Current module completion evidence
- [x] Required concepts learned from authoritative sources
- [x] Learner explained the core concept in their own words
- [x] Knowledge check passed
- [x] Exercise attempted and reviewed
- [x] Required project or design increment completed
- [x] Relevant validation executed successfully
- [x] Learning notes updated
- [x] Design snapshot and module history reconciled with code
- Sources/sections covered: `../roadmap.md` Module 14; reliability, security, failure-boundary, and adversarial-behavior requirements recorded in the module review.
- Learner explanation or answer: Learner explained that timeout, circuit-open, and dependency failure mean unavailable evidence rather than an empty successful query; retry policy, coordinator budgets, and report acceptance have separate owners. Learner explained untrusted runbook handling, least privilege, incident scope isolation, sanitized diagnostics, and why unsupported causal claims must be downgraded when evidence is unavailable.
- Exercise path/result: Completed the Module 14 failure-matrix exercise and debugging task for an overconfident report while the Metrics circuit was open. Implemented provider-neutral errors, redaction, scoped circuit breakers, adversarial retry bounds, coverage classification, and workflow synthesis integration.
- Changed files: `src/incidentlens/errors.py`, `reliability.py`, model/telemetry/coordinator/workflow modules, focused tests, and the three required learning records.
- Commands and observed results: `python -m pytest -q` -> 213 passed, 1 skipped; `python -m ruff check .` passed; `python -m ruff format --check .` passed.
- Design decision/evolution: Coverage is deterministic at the coordinator/fan-in to synthesis boundary. Mixed specialist availability yields an explicitly `inconclusive` report; no successful evidence yields workflow `FAILED`; successful full coverage can remain `completed`.
- Untested assumptions: Production coordinator wiring and a unified failure matrix for all live dependency classes remain future work; live outage behavior is represented by deterministic fixtures.
- Weak concepts: No blocking Module 14 weakness identified. Continue practicing evaluation of evidence sufficiency and calibrated abstention in Module 15.
- Optional work deferred: All optional advanced extensions.

## Module 1 Evidence History
- Status: Completed on 2026-09-10.
- Sources/sections covered: `../roadmap.md` Module 1; LangChain Multi-agent; Anthropic Building effective agents; AutoGen Agent and Multi-Agent Applications.
- Learner explanation or answer: Learner explained deterministic workflow as known conditional control flow and agents as components that decide from available information under uncertainty. Learner distinguished parallel tool execution from parallel specialist agent investigation. Learner explained that a narrow PostgreSQL connection-pool exhaustion confirmation should use a single agent because multiple agents would add coordination overhead, duplicate work, extra model calls, and possible conflicting conclusions without improving diagnosis.
- Review answers: Lifecycle transitions should be deterministic for predictability, testability, and recovery. Logs/metrics/traces agents are defensible due to distinct evidence sources and tools, while persona-only agents are weaker. Deployment evidence supports a trigger when errors correlate with a release, affect only the new version, show changed code paths, and rollback resolves the issue, but confounders prevent claiming proof without causal mechanism.
- Failure-analysis result: Learner identified weak specialization, missing trace ownership, persona-style skeptic, shared long context, excessive tool access, planner overreach, missing evidence contracts, ungrounded final reports, and premature consensus. Proposed deterministic orchestrator, isolated specialist agents, evidence store, verification agent, and synthesis with evidence IDs.
- Exercise path/result: Learner drafted the Module 1 project contract. Reviewed and recorded in docs/design.md with two refinements: Gemini remains the required provider per roadmap, and triaging/synthesizing are internal phases rather than top-level lifecycle states.
- Changed files: docs/tracker.md, docs/learning.md, docs/design.md
- Commands and observed results: python -m pytest -q passed with 20 tests and one local google-auth/grpcio FutureWarning; python -m ruff check . passed; python -m ruff format --check . passed; python -m mypy src remains deferred because mypy is not installed; settings loaded the API key without exposing its value; the initial live call rejected gemini-2.5-flash with 404, so the configurable default was updated to gemini-3-flash-preview; offline retry tests passed; the bounded live retry reached the provider twice and ended with InvalidModelResponseError.
- Validation: Documentation/design validation only; no runtime code exists in Module 1. Records were read back after creation and reconciled. Module 1 source pages were consulted through web access.
- Design decision/evolution: Project contract and proposed architecture boundary recorded. Lifecycle is `created -> investigating -> awaiting_review -> completed | failed | cancelled`. Triaging and synthesis may be internal phases later. Architecture remains proposed only; no runtime code exists yet.
- Untested assumptions: Python version and project tooling remain unconfigured until Module 2.
- Weak concepts: None blocking Module 1 completion. Continue reinforcing agent boundaries when implementation begins.
- Optional work deferred: All optional advanced extensions.

## Blockers and deviations
- Historical: Git metadata was unavailable during early Module 3 work. Resolved; repository status is now available and current changes are tracked in the working tree.

## Exact next session
- Module and phase: Module 15 - Evaluation, ablations, observability, and optimization, Orient
- File/function/section: `roadmap.md` Module 15 and the current evaluation/fixture layout
- Next question or exercise: Define correctness, evidence grounding, abstention, reliability, cost, and latency metrics for IncidentLens.
- Next build task: Establish deterministic and single-agent baselines plus a small held-out evaluation set.
- Next validation command: `python -m pytest -q`; `python -m ruff check .`; `python -m ruff format --check .`.




























- Retry implementation evidence: ProviderRetryMetadata records sanitized failure categories and bounded delays; retries consume max_steps; token fields remain null when unavailable. Offline validation observed 20 passed, Ruff check passed, and format check passed. The bounded live retry reached gemini-3-flash-preview twice and ended with InvalidModelResponseError; no live artifact was written.
- Live-test isolation evidence: Added tests/test_live_gemini.py with the live marker and RUN_LIVE_GEMINI=1 opt-in guard. Default validation observed 20 passed and 1 skipped, with no Gemini call from the live test.
- Live test follow-up: the adapter fence-normalization regression test passed. An opt-in live run reached the provider and then ended after bounded retries with sanitized provider failure classification for quota exhaustion (429); no live artifact was produced.
- Correction from learner-provided live artifact: Gemini 3 live baseline completed successfully after 3 model calls, 1 retry, and 1 tool call. Artifact: artifacts/baseline-payment-latency-001.json. It recorded 979 input tokens, 627 output tokens, and 1606 total tokens. The report is schema-valid and evidence-linked; factual root-cause verification remains outside Module 2.
- Module 3 knowledge check: Learner correctly distinguished metric symptom evidence, log event evidence, and trace localization. They proposed matching payment-service metrics as independent corroboration while explicitly rejecting automatic causal proof.
- Module 3 correlation check: Learner correctly prioritized request/trace IDs and timestamp normalization over proximity-only matching, and required uncertain relationships when clock skew or identity cannot be explained.
- Module 3 classification check: Learner correctly separated symptom, contributing-factor localization, and root-cause hypothesis.
- Module 3 timeline check: Learner correctly explained why peak-only analysis can confuse simultaneous symptoms with causal signals and why signal evolution matters.
- Module 3 RED/USE check: Learner correctly classified service request signals and database resource signals, and distinguished available fixture evidence from useful but unobserved investigative queries.
- Module 3 span check: Learner correctly identified trace, span, and parent-span identifiers; service identity and timing were added as interpretation requirements.
- Module 3 ground-truth check: Learner correctly identified that exposing root-cause labels through the fixture loader creates ground-truth leakage and invalidates evaluation.
- Module 3 manual diagnosis exercise: Completed successfully. Learner separated observations, inferences, hypotheses, competing explanations, missing evidence, and next bounded investigations without leaking or assuming ground truth.
- Module 3 build evidence: Added src/incidentlens/telemetry.py and tests/test_telemetry.py. Implemented versioned provider-neutral telemetry and manifest contracts, deterministic UTC consistency checks, evaluator/agent fixture projection, and ground-truth sentinel tests. Validation observed 27 passed, 1 skipped; Ruff check and format check passed. Module remains in progress pending additional fixtures and correlation/timestamp edge cases.

- Module 3 fixture increment: Added fixtures/incidents/payment_failure.json and fixtures/incidents/resource_exhaustion.json. Added tests for fixture loading, missing signals, partial records, out-of-order trace records, and manifest references. Validation observed 33 passed, 1 skipped; Ruff check and format check passed.

- Module 3 completion update: Manifest enrichment, standardized service-latency fixture, fail-fast malformed-record policy, trace/log correlation coverage, deterministic ordering, and empty-window behavior are implemented. Validation observed 37 passed, 1 skipped; Ruff check and format check passed. Remaining gate is learner review, not core implementation.
- Validation confirmation: Learner ran `python -m pytest tests\test_telemetry.py -q` with 16 passed and `python -m pytest -q` with 37 passed, 1 skipped. Module 3 implementation validation is passing; review gate remains.

- Live validation confirmation: Learner ran the opt-in Gemini test successfully against the synthetic incident fixture. Live model invocation, tool execution, retry metadata, schema-valid report generation, and artifact persistence are operational.

- Module 3 final conceptual review: Passed. Learner accurately explained telemetry signal boundaries, identity-based correlation, timestamp provenance/normalization, ground-truth leakage prevention, and symptom/contributor/hypothesis distinctions.

- Module 3 debugging review: Passed. Learner identified five defects involving timezone conversion, ground-truth boundaries, temporal semantics, timestamp validation, and uncertainty handling for empty evidence.

- Module 4 capability-boundary check: Passed. Learner correctly explained that the deterministic tool/application layer must reject an out-of-scope path before access and validate resolved paths against the allowed fixture root.

- Module 4 narrow-tool check: Passed. Learner correctly justified typed metric queries over arbitrary SQL using least privilege, bounded resource use, injection resistance, data isolation, and auditability.

- Module 4 bounds check: Passed. Learner correctly explained truncation propagation, incomplete coverage, confidence impact, and avoidance of conclusions assuming full telemetry.

- Module 4 error-taxonomy check: Passed. Learner correctly separated completed empty results from timeout uncertainty and rejected treating retrieval failure as evidence absence.

- Module 4 provenance check: Passed. Learner correctly justified preserving raw tool results separately from agent summaries for citation verification, contradiction detection, re-evaluation, and auditability.

- Module 4 preprocessing check: Passed. Learner correctly defined provenance-preserving trace-summary requirements and distinguished deterministic compression from root-cause inference.

- Module 4 build/validation evidence: Added TelemetryQueryResult invariants and a bounded query_metrics tool in src/incidentlens/telemetry_tools.py. It validates UTC windows and limits, scopes queries to the active fixture, returns success/partial/invalid-query results, and preserves structured telemetry records. Added tests/test_telemetry_tools.py. Validation observed 44 passed, 1 skipped; Ruff check and format check passed.

- Module 4 final conceptual review: Passed. Learner correctly explained capability boundaries, narrow typed queries, structured error semantics, and propagation of truncation/provenance/raw evidence through the investigation chain.

### Module 5 orientation evidence
- [x] Learner explained that authoritative workflow data belongs in typed graph state rather than chat history.
- [x] Learner assigned lifecycle transition authority to deterministic orchestration and named schema, completion-step, and evidence-reference checks.
- [ ] Minimal state schema and legal transition table designed.
- [ ] LangGraph implementation and transition tests completed.
- Weak concept to preserve: evidence-reference validity is not the same as factual grounding.
- [x] State-design exercise reviewed: typed state, legal/illegal transitions, terminal behavior, and invariants defined.
- Remaining concept: node/edge execution and reducers, especially how state updates remain deterministic.
- [x] Node/edge/reducer knowledge check passed: lifecycle ownership remains centralized and evidence aggregation is deterministic and deduplicating.

### Module 5 state-contract implementation evidence
- [x] Added `src/incidentlens/workflow_state.py` with typed lifecycle state and explicit transition rules.
- [x] Added deterministic rejection for skipped, backward, and terminal transitions.
- [x] Added completion/report and failure/error entry validation.
- [x] Added monotonic `record_usage` updates for model/tool counters.
- [x] Focused validation: `python -m pytest tests\\test_workflow_state.py -q` -> 9 passed; `python -m ruff check .` passed.
- [ ] Add LangGraph graph nodes, edges, reducers, cancellation, and full lifecycle validation.

### Module 5 LangGraph implementation evidence
- [x] Added `langgraph>=1.0` and explicit lifecycle graph in `src/incidentlens/workflow_graph.py`.
- [x] Added validation, triage, investigation, and synthesis nodes with conditional terminal routing.
- [x] Added explicit cancellation input and sanitized synthesis failure behavior.
- [x] Preserved deterministic transition ownership in `workflow_state.py`.
- [x] Full validation: `python -m pytest -q` -> 58 passed, 1 skipped; Ruff check and format check passed.
- [ ] Inspect a graph execution and expand legal/illegal transition coverage before Module 5 completion.

## Exact next session
- Module and phase: 5 - LangGraph state and deterministic orchestration, Validate
- File/function/section: `src/incidentlens/workflow_graph.py`; graph invocation and transition tests.
- Next question or exercise: Explain how graph output, checkpoint state, and model messages differ.
- Next build task: Add execution inspection and complete transition/terminal-state coverage.
- Next validation command: `python -m pytest tests\\test_workflow_state.py tests\\test_workflow_graph.py -q`

### Module 5 validation evidence
- [x] Inspected compiled graph execution and verified node sequence: `validate -> triage -> investigate -> synthesize`.
- [x] Covered cancellation from every active state and rejection from every terminal state.
- [x] Full validation: `python -m pytest -q` -> 66 passed, 1 skipped; Ruff check and format check passed.
- [ ] Final conceptual review and failure-analysis exercise.

### Module 6 orientation evidence
- [x] Reviewed Module 6 scope and prerequisites.
- [ ] Justify Logs, Metrics, and Traces boundaries using distinct tools, context, outputs, or stopping rules.
- [ ] Define versioned specialist role contracts.
- [ ] Implement isolated specialist contexts and tool allowlists.
- [ ] Validate role confusion, missing evidence, and context-size behavior.
- [x] Role-boundary knowledge check passed: persona-only agents were rejected and Metrics Agent least-privilege boundaries were correctly defined.
- Next concept: isolated context construction and prevention of cross-agent anchoring.
- [x] Isolated-context knowledge check passed: independent Metrics Agent inputs and excluded context were correctly specified.
- Next exercise: define versioned role contracts for Logs, Metrics, and Traces specialists.

### Module 6 runtime tool evidence
- [x] Added bounded `search_logs`, `search_traces`, and `get_trace` tools over agent-facing fixtures.
- [x] Added separate logs, metrics, and traces registries with least-privilege tool exposure.
- [x] Tested trace-ID retrieval, signal-domain results, invalid query scope, narrow trace filters, and unauthorized tool calls.
- [x] Full validation: `python -m pytest -q` -> 76 passed, 1 skipped; Ruff check and format check passed.
- [ ] Run role-confusion and missing-evidence cases.
- [ ] Complete Module 6 final conceptual review and failure-analysis exercise.

### Module 6 role-confusion validation evidence
- [x] Added parameterized context tests for Logs, Metrics, and Traces signal isolation.
- [x] Added tests that peer findings and ground-truth terms are absent from specialist context.
- [x] Added runtime registry tests for cross-domain tool rejection.
- [x] Full validation: `python -m pytest -q` -> 81 passed, 1 skipped; Ruff check and format check passed.
- [ ] Run missing-evidence cases.
- [ ] Complete Module 6 final conceptual review and failure-analysis exercise.

### Module 6 missing-evidence validation evidence
- [x] Added empty-context tests for Logs, Metrics, and Traces roles.
- [x] Added rejection of invented evidence IDs when no evidence is available.
- [x] Added rejection of findings with no evidence citations.
- [x] Full validation: `python -m pytest -q` -> 86 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 6 final conceptual review and failure-analysis exercise.

### Module 7 orientation evidence
- [x] Reviewed Module 7 scope, topology patterns, and protocol requirements.
- [ ] Compare coordination topologies for IncidentLens.
- [ ] Select and justify the initial production topology.
- [ ] Define versioned task-envelope and inter-agent message contracts.
- [ ] Test invalid, stale, duplicated, and incompatible messages.
- [x] Topology and task-envelope knowledge check passed: centralized supervisor/workers was justified and required envelope fields were identified.
- Next concept: versioned task and finding message contracts, including identity and duplicate handling.
- [x] Message-contract knowledge check passed: task/agent provenance and duplicate-finding idempotency were correctly explained.
- Next exercise: define versioned task-envelope and specialist-finding contracts.

### Module 7 coordination implementation evidence
- [x] Added versioned task-envelope and specialist-finding message contracts.
- [x] Added semantic validation for task, incident, role, and evidence scope.
- [x] Added idempotent `FindingInbox` for exact retries and conflicting duplicate rejection.
- [x] Validation: `python -m pytest -q` -> 94 passed, 1 skipped; Ruff check and format check passed.
- [ ] Implement pattern comparison labs and coordinator routing.
- [ ] Test incompatible messages against coordinator state.
- [ ] Complete Module 7 final conceptual review and failure-analysis exercise.

### Module 7 coordinator and topology implementation evidence
- [x] Added deterministic specialist task creation from role contracts.
- [x] Added `InvestigationCoordinator` with validated finding intake.
- [x] Added router, handoff, and supervisor-workers pattern labs and decision matrix.
- [x] Selected supervisor-workers as the initial IncidentLens topology.
- [x] Full validation: `python -m pytest -q` -> 97 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 7 final conceptual review and failure-analysis exercise.

### Module 8 orientation evidence
- [x] Fan-out/fan-in knowledge check passed: benefits, risks, partial success, and timeout uncertainty were correctly explained.
- [ ] Define bounded concurrency, per-branch deadlines, global investigation deadline, and cancellation behavior.
- [ ] Implement concurrent specialist execution and deterministic aggregation.
- [ ] Validate slow, failed, duplicated, and partially successful workers.
- [x] Stable-order knowledge check passed: nondeterministic arrival was separated from deterministic aggregate representation.
- Next exercise: implement bounded concurrent specialist execution and deterministic aggregation.

### Module 8 parallel runner implementation evidence
- [x] Repaired async test execution without skipped coroutine tests.
- [x] Added semaphore-bounded concurrent branch execution.
- [x] Added per-branch timeout, failure, and cancellation result classification.
- [x] Added stable role-order fan-in and sibling-success preservation.
- [x] Full validation: `python -m pytest -q` -> 102 passed, 1 skipped; Ruff check and format check passed.
- [ ] Add global investigation deadline and cancellation propagation.
- [ ] Validate duplicated findings and deterministic aggregation.
- [ ] Compare sequential and concurrent latency using the same scenario.

### Module 8 parallel execution completion evidence
- [x] Added global investigation deadline and cancellation of unfinished branches.
- [x] Preserved completed sibling results after global deadline expiry.
- [x] Added deterministic FindingInbox aggregation and duplicate-finding suppression.
- [x] Compared sequential and concurrent execution using the same controlled worker scenario.
- [x] Full validation: `python -m pytest -q` -> 105 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 8 final conceptual review and failure-analysis exercise.

### Module 9 knowledge-check evidence
- [x] Learner explained reuse of validated completed work during resume and distinguished thread-scoped checkpoints from cross-investigation memory.
- [ ] Learn checkpoint commit/recovery semantics and artifact integrity.
- [ ] Implement and validate Module 9 persistence increment.
- Exact next task: define checkpoint contents, commit points, and recovery behavior for interrupted investigation steps.
### Module 9 recovery exercise evidence
- [x] Correctly handled artifact-committed/checkpoint-missing recovery using stable execution identity and reuse.
- [x] Correctly handled artifact-missing recovery as bounded retry of incomplete work.
- [ ] Learn artifact integrity and state-version compatibility.
- Exact next task: define validation rules for artifact references and incompatible checkpoint versions.
### Module 9 integrity and versioning evidence
- [x] Correctly handled cross-incident artifact references as integrity/scope violations.
- [x] Correctly handled unsupported checkpoint versions through deterministic migration or rejection.
- [ ] Implement checkpoint and artifact persistence increment.
- [ ] Validate restart, stale references, corruption, duplicate resumes, and incompatible versions.
- Exact next task: implement a small versioned artifact store and checkpoint recovery boundary.
### Module 9 persistence implementation evidence
- [x] Implemented versioned artifact and checkpoint persistence contracts.
- [x] Added focused persistence tests: 8 passed.
- [x] Full validation: `python -m pytest -q` -> 113 passed, 1 skipped; Ruff check and format check passed.
- [ ] Integrate checkpoint persistence with the workflow graph and resume completed work.
- [ ] Validate restart, stale references, corruption, duplicate resumes, and incompatible versions.
- Exact next task: connect `CheckpointStore` to workflow execution and test truthful restart/resume behavior.
### Module 9 checkpoint integration evidence
- [x] Added optional LangGraph checkpointer support and controlled interrupt point.
- [x] Demonstrated pause/resume with stable `thread_id`: focused workflow tests passed 6 tests.
- [ ] Persist and restore evidence artifact references through graph state.
- [ ] Validate artifact-aware resume and duplicate-resume behavior.
- Exact next task: add durable artifact references to the state/checkpoint flow and test reuse after interruption.
### Module 9 artifact-aware resume evidence
- [x] Graph checkpoint resume test completed with stable `thread_id`.
- [x] Report artifact persisted and referenced from resumed graph state.
- [x] Focused state, graph, and persistence tests passed.
- [ ] Validate stale artifact references, duplicate resumes, and checkpoint/artifact reconciliation failures.
- Exact next task: add failure-focused recovery tests and retention/size-limit behavior.
### Module 9 persistence safeguard evidence
- [x] Added missing/stale artifact classification and checkpoint reference scope validation.
- [x] Added configurable artifact size and count retention limits.
- [x] Persisted report evidence artifacts and verified duplicate resume does not create duplicate files.
- [x] Full validation: `python -m pytest -q` -> 118 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 9 final conceptual review, failure analysis, and implementation exercise review.
- Exact next task: perform the Module 9 final review and decide whether recovery behavior is truthful under stale references, corruption, and retention eviction.
### Module 9 final review and completion
- [x] Learner passed five conceptual questions covering state, checkpoints, artifacts, memory, commit ordering, stable thread IDs, and versioning.
- [x] Learner completed the checkpoint/artifact scope failure analysis correctly.
- [x] Implemented and validated artifact-aware checkpoint resume, duplicate-resume handling, stale/missing artifact detection, cross-incident scope rejection, corruption/version rejection, size limits, and retention limits.
- [x] Full validation: `python -m pytest -q` -> 119 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitation: persistence is filesystem-backed and there is no separate production recovery service API yet.
- Exact next task: begin Module 10 planning, adaptive routing, budgets, and termination.
### Module 10 orientation evidence
- [x] Reviewed the roadmap scope for static/model-generated planning, adaptive routing, follow-up limits, budgets, and termination.
- [ ] Explain who owns planning, execution, budget enforcement, and termination.
- [ ] Implement complexity-aware bounded task planning and one follow-up round.
- [ ] Validate under-delegation, duplicate/excessive tasks, circular delegation, impossible requests, and budget exhaustion.
- Exact next task: distinguish model-proposed investigation plans from deterministic coordinator authorization.
### Module 10 planning knowledge-check evidence
- [x] Explained static baseline versus runtime evidence-dependent follow-up.
- [x] Kept model task proposals behind deterministic scope, permission, duplicate, and budget validation.
- [ ] Learn budget accounting and termination policy.
- Exact next task: define how global and per-task budgets produce partial or inconclusive reports.
### Module 10 budget knowledge-check evidence
- [x] Distinguished independent model/tool budgets and rejected an unexecutable follow-up before execution.
- [x] Defined truthful partial/inconclusive reporting after budget exhaustion.
- [ ] Define complexity-aware baseline selection and typed follow-up proposals.
- [ ] Implement deterministic plan validation, one follow-up round, and termination enforcement.
- Exact next task: design the plan proposal and coordinator validation contracts.
### Module 10 follow-up contract evidence
- [x] Defined a bounded model proposal contract separate from coordinator authorization.
- [x] Defined deterministic follow-up validation and rejection reasons.
- [x] Kept validation side-effect-free; budget and round state change only on scheduling.
- [ ] Implement plan proposal and validation contracts.
- Exact next task: add `FollowUpProposal`, validation context/result, canonical task key, and focused tests in `coordination.py`.
### Module 10 follow-up scheduling implementation evidence
- [x] Added deterministic scheduling from validated follow-up proposals.
- [x] Derived tools, signal types, and task budgets from role contracts.
- [x] Registered scheduled tasks with the finding inbox.
- [x] Added coordinator-local duplicate protection and active-incident scope validation.
- [x] Coordination validation: 17 passed; full validation: 125 passed, 1 skipped; Ruff checks passed.
- [ ] Add complexity-aware baseline selection and explicit termination/budget accounting.
- Exact next task: design the deterministic complexity policy and global budget ledger.
### Module 10 implementation evidence
- [x] Added deterministic simple/standard/complex incident classification and baseline role policy.
- [x] Added global model/tool `BudgetLedger` with exhaustion checks.
- [x] Added explicit deterministic termination decisions and reasons.
- [x] Added bounded follow-up scheduling with role-derived permissions/budgets, task registration, duplicate protection, and incident scope validation.
- [x] Coordination validation: 22 passed; full validation: 130 passed, 1 skipped; Ruff checks passed.
- [ ] Complete Module 10 final conceptual review, failure analysis, and implementation exercise review.
- Exact next task: answer final questions about planning ownership, budget exhaustion, termination, and adaptive routing.
### Module 10 final review and completion
- [x] Learner explained planning, execution, authorization, budget, lifecycle, and termination ownership.
- [x] Learner explained complexity-aware specialist selection and bounded adaptive follow-up.
- [x] Learner explained independent model/tool budgets and truthful partial reporting after exhaustion.
- [x] Learner completed the follow-up-limit failure analysis correctly; rejected work is not executed and remains an explicit unknown.
- [x] Implementation and validation complete: `python -m pytest -q` -> 130 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitation: follow-up dependencies are intentionally flat, so circular delegation is prevented by topology rather than modeled as a general dependency graph.
- Exact next task: begin Module 11 on runbook retrieval, change intelligence, and citation grounding.
### Module 11 orientation evidence
- [x] Reviewed the roadmap scope for retrieval, metadata filters, versioned runbooks, change correlation, citation grounding, and retrieval evaluation.
- [ ] Explain retrieval versus memory versus tool calls.
- [ ] Implement a versioned runbook corpus and Runbook Agent.
- [ ] Implement a Change Agent with bounded change-event retrieval.
- [ ] Validate irrelevant, contradictory, stale, missing, and malicious content.
- Exact next task: distinguish retrieved guidance from current-incident telemetry evidence.
### Module 11 retrieval-boundary evidence
- [x] Distinguished retrieval, memory, tool calls, runbook guidance, change observations, and telemetry evidence.
- [x] Defined deterministic metadata filtering and separate deployment citations.
- [x] Correctly handled malicious runbook instructions as untrusted content.
- [ ] Define versioned corpus, chunk, citation, and change-event contracts.
- Exact next task: design exact runbook-section citations and validity-aware retrieval results.
### Module 11 citation evidence
- [x] Explained exact section citations, provenance, validity inspection, and the limits of similarity scores.
- [ ] Implement versioned runbook-section and change-event contracts.
- [ ] Implement deterministic metadata filters and bounded retrieval.
- Exact next task: add provider-neutral retrieval contracts and tests for validity/status/service filters.
### Module 11 retrieval implementation evidence
- [x] Added provider-neutral runbook section, citation, and change-event contracts.
- [x] Added deterministic service/environment/status/validity filtering.
- [x] Added UTC and half-open validity validation.
- [x] Retrieval validation: 8 focused tests; full validation: 138 passed, 1 skipped; Ruff checks passed.
- [ ] Add versioned corpus loading, bounded ranking, Runbook Agent, and Change Agent.
- Exact next task: add synthetic runbook corpus loading and exact citation-preserving retrieval.
### Module 11 corpus and retrieval implementation evidence
- [x] Added versioned JSON runbook corpus loading.
- [x] Added unique document/section identity validation.
- [x] Added deterministic lexical retrieval after metadata/validity filtering.
- [x] Added bounded limits and exact citation output.
- [x] Retrieval validation: 12 focused tests; full validation: 142 passed, 1 skipped; Ruff checks passed.
- [ ] Add Runbook Agent and Change Agent tool boundaries.
- Exact next task: add a bounded Runbook Agent interface and separate Change Agent retrieval with change-event IDs.
### Module 11 agent interface implementation evidence
- [x] Added Runbook Agent with runbook-only retrieval and citation outputs.
- [x] Added Change Agent with change-only bounded event retrieval.
- [x] Enforced separate tool/signal scopes and UTC time windows.
- [x] Retrieval validation: 15 focused tests; full validation: 145 passed, 1 skipped; Ruff checks passed.
- [ ] Validate irrelevant, contradictory, stale, missing, and malicious runbook content.
- [ ] Evaluate retrieval separately from final diagnosis generation.
- Exact next task: add adversarial corpus fixtures and retrieval evaluation cases.
### Module 11 adversarial retrieval evidence
- [x] Tested irrelevant and missing retrieval matches.
- [x] Tested contradictory sections without automatic retriever resolution.
- [x] Tested stale/expired filtering.
- [x] Tested malicious runbook content remains inert data with unchanged tool permissions.
- [x] Full validation: `python -m pytest -q` -> 149 passed, 1 skipped; Ruff checks passed.
- [ ] Evaluate retrieval separately from final diagnosis generation and add change-correlation cases.
- Exact next task: add retrieval metrics/evaluation and test deployment correlation versus causation.
### Module 11 retrieval evaluation evidence
- [x] Added retrieval-only precision, recall, hit-rate, and reciprocal-rank metrics.
- [x] Evaluated perfect, partial, miss, and empty-relevance cases.
- [x] Kept retrieval evaluation separate from final diagnosis evaluation.
- [x] Full validation: `python -m pytest -q` -> 153 passed, 1 skipped; Ruff checks passed.
- [ ] Add deployment correlation-versus-causation cases and final Module 11 review.
- Exact next task: test change-event temporal correlation without treating proximity as causation.
### Module 11 change correlation evidence
- [x] Added temporal before/during change-event correlation.
- [x] Excluded distant changes with bounded pre-incident proximity.
- [x] Explicitly prevented correlation results from supporting causation.
- [x] Full validation: `python -m pytest -q` -> 155 passed, 1 skipped; Ruff checks passed.
- [ ] Complete Module 11 final conceptual review and retrieval/change evaluation exercise.
- Exact next task: answer final questions on retrieval grounding, stale knowledge, and correlation versus causation.
### Module 11 final review and completion
- [x] Learner explained why similarity cannot prove root cause and identified deterministic metadata filters.
- [x] Learner preserved contradictory runbook sections with separate citations.
- [x] Learner distinguished runbook guidance, telemetry evidence, and change observations.
- [x] Learner correctly handled malicious runbook instructions as inert data with no new permissions.
- [x] Learner completed temporal-correlation failure analysis without causal promotion.
- [x] Implementation and validation complete: `python -m pytest -q` -> 155 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitation: retrieval is deterministic lexical ranking over a small synthetic corpus; semantic/vector retrieval and full end-to-end diagnosis evaluation remain deferred.
- Exact next task: begin Module 12 on hypothesis formation, contradiction handling, and calibrated confidence.
### Module 12 orientation evidence
- [x] Reviewed the roadmap scope for hypothesis generation, evidence tables, alternatives, verification, critique limits, abstention, and calibrated confidence.
- [ ] Explain why agreement between agents is not independent confirmation.
- [ ] Implement hypothesis and verifier contracts.
- [ ] Validate unsupported causes, conflicting findings, missing signals, and distractors.
- Exact next task: distinguish a candidate hypothesis from a verified conclusion and define evidence obligations.
### Module 12 hypothesis knowledge-check evidence
- [x] Distinguished supporting evidence from evidence establishing a causal mechanism.
- [x] Explained structured verifier inputs and provenance-based independence.
- [x] Distinguished downgrade/contradiction from `insufficient_evidence`.
- [ ] Define hypothesis, verification, evidence-table, and abstention contracts.
- Exact next task: design a structured hypothesis with supporting, contradicting, missing evidence, and calibrated confidence.
### Module 12 calibrated-confidence evidence
- [x] Distinguished evaluated low confidence from unavailable-evidence abstention.
- [ ] Implement structured hypothesis and verification outcome contracts.
- [ ] Add bounded verifier behavior and contradiction tests.
- Exact next task: add hypothesis/evidence-table models with deterministic evidence-ID grounding.
### Module 12 hypothesis contract implementation evidence
- [x] Added `EvidenceTable` with disjoint supporting/contradicting evidence validation.
- [x] Added `HypothesisCandidate` status semantics, including required missing evidence for abstention.
- [x] Added deterministic `VerificationResult` and `verify_hypothesis(...)`.
- [x] Added tests for unknown evidence, contradictory evidence downgrade, and missing-signal abstention.
- [x] Focused validation: 7 passed; full validation: 162 passed, 1 skipped; Ruff check and format check passed.
- [ ] Implement isolated verifier-agent context and bounded critique rounds.
- Exact next task: define verifier input/output contracts and test unsupported, conflicting, missing, and deceptive evidence cases.
### Module 12 verifier boundary implementation evidence
- [x] Added isolated verifier context with forbidden extra fields.
- [x] Added deterministic verifier agent wrapper and critique-round limit.
- [x] Added tests for hidden-context exclusion, out-of-scope evidence, round exhaustion, and one-result-per-candidate behavior.
- [x] Focused validation: 11 passed; full validation: 166 passed, 1 skipped; Ruff check and format check passed.
- [ ] Add model-backed critique rounds and complete final Module 12 review.
- Exact next task: test unsupported causal claims, conflicting specialist findings, missing signals, and deceptive distractors through the verifier boundary.
### Module 12 model-backed critique implementation evidence
- [x] Added structured model critique proposal and provider-neutral callback boundary.
- [x] Added deterministic reconciliation of model evidence claims into verification outcomes.
- [x] Added tests for contradictory critique, unknown citations, and round exhaustion before model invocation.
- [x] Full validation: `python -m pytest -q` -> 169 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete final conceptual review, deceptive-distractor exercise, and Module 12 completion gate.
- Exact next task: explain verifier independence, unsupported causal claims, evidence coverage, and abstention in the final review.
### Module 12 final review and completion
- [x] Explained why model confidence and existing evidence IDs do not prove causation.
- [x] Distinguished `low_confidence` from `insufficient_evidence`.
- [x] Explained why shared evidence does not create independent confirmation.
- [x] Correctly rejected unknown evidence IDs at the deterministic verification boundary.
- [x] Correctly enforced critique-round limits before model invocation.
- [x] Completed the deployment-correlation failure analysis: temporal correlation is useful supporting evidence, but causal deployment involvement remains unverified.
- [x] Implementation and validation complete: `python -m pytest -q` -> 169 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitation: live Gemini verifier prompting and multi-round quality evaluation remain unverified; current model-backed tests use a fake provider callback.
- Exact next task: begin Module 13 on human oversight, authorization, and safe actions.
### Module 13 orientation evidence
- [x] Reviewed the roadmap scope for human approval, authorization, action separation, audit trails, interrupts, and reversibility.
- [ ] Explain authentication versus authorization versus human approval.
- [ ] Define exact action-binding and approval contracts.
- [ ] Implement an approval interrupt and read-only simulated action path.
- Exact next task: answer the two questions on authentication, authorization, and stale approvals.
### Module 13 first knowledge check
- [x] Distinguished authentication from authorization.
- [x] Explained why exact action changes invalidate prior approval.
- [ ] Define action fingerprints and stale-approval detection.
- Exact next task: design the action-plan and approval contracts.
### Module 13 action fingerprint evidence
- [x] Explained why evidence references are part of the approval fingerprint.
- [ ] Define ActionPlan, Approval, and AuditEvent contracts.
- Exact next task: design the approval lifecycle and deterministic validation rules.
### Module 13 approval-contract implementation evidence
- [x] Added action, approval, audit, and validation contracts.
- [x] Added deterministic fingerprint binding for action arguments and evidence references.
- [x] Tested rejection reuse, changed evidence, expiry, unauthorized approval, and duplicate execution.
- [x] Full validation: `python -m pytest -q` -> 178 passed, 1 skipped; Ruff check and format check passed.
- [ ] Implement approval interrupt/resume and durable audit events.
- Exact next task: design the approval pause, resume, and one-time execution flow.
### Module 13 durable approval implementation evidence
- [x] Added durable approval interrupt/resume store and audit events.
- [x] Tested awaiting approval, one-time execution, duplicate resume, crash marker, rejection, and sanitized failures.
- [x] Hardened rejected approvals and failed execution so they cannot be silently reused.
- [x] Full validation: `python -m pytest -q` -> 186 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 13 final conceptual review and workflow-boundary validation.
- Exact next task: explain why UI approval is insufficient, analyze stale/unauthorized approvals, and review duplicate resume behavior.
### Module 13 final review and completion
- [x] Explained authentication, authorization, human approval, exact action fingerprints, and separation of duties.
- [x] Explained stale approvals, rejected-fingerprint blocking, duplicate resume, and uncertain external execution.
- [x] Implementation and validation complete: `python -m pytest -q` -> 186 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitation: external execution reconciliation is not implemented because remediation remains simulated.
- Exact next task: begin Module 14 on reliability, security, and adversarial behavior.

### Module 14 telemetry error mapping implementation
- [x] Added shared `IncidentError` mapping to `TelemetryQueryError`.
- [x] Mapped timeout and dependency failures to stable provider-neutral classifications.
- [x] Mapped cross-incident requests to terminal `incident_scope_violation` errors.
- [x] Validation: 26 focused tests; 197 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Add redaction and safe logging rules at persistence and audit boundaries.
- Exact next task: identify and test raw exception, secret, customer-identifier, and hidden-ground-truth redaction paths.

### Module 14 redaction and safe logging implementation
- [x] Added bounded `sanitize_text` redaction for connection strings, secrets, tokens, authorization values, and customer identifiers.
- [x] Added `IncidentError.from_message` so user-facing structured errors sanitize at construction.
- [x] Applied sanitization to telemetry-to-error mapping.
- [x] Validation: focused redaction/telemetry/audit tests passed; full suite `199 passed, 1 skipped`; Ruff and formatting passed.
- [ ] Add field-aware redaction for structured telemetry/diagnostic payloads and verify hidden-ground-truth exclusion.
- Exact next task: threat-test redaction against nested payloads, headers, exception chains, and audit serialization.

### Module 14 field-aware redaction validation
- [x] Added recursive structured-payload sanitization for nested fields and sensitive headers.
- [x] Added chained-exception sanitization coverage.
- [x] Added audit-style payload redaction tests without mutating executable action plans.
- [x] Validation: 18 focused tests; 202 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Add controlled adversarial tests for prompt injection, hidden-ground-truth leakage, and retry storms.
- Exact next task: threat-test untrusted telemetry/runbook content and bounded failure behavior.

### Module 14 adversarial validation
- [x] Verified poisoned runbook text cannot expand the Runbook Agent tool allowlist.
- [x] Verified hidden ground truth remains outside agent-visible fixture projections.
- [x] Added retry-storm coverage across 20 failing investigations with per-run attempt bounds.
- [x] Validation: 55 focused adversarial tests; 203 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Add controlled partial-backend outage and circuit-breaker recovery behavior.
- Exact next task: test safe degradation when one telemetry dependency is unavailable while other evidence continues.

### Module 14 circuit breaker and partial-backend recovery
- [x] Added deterministic closed/open/half-open circuit-breaker behavior with injected-clock tests.
- [x] Added fail-fast branch behavior when a dependency circuit is open.
- [x] Verified healthy specialist branches continue and produce successful partial results.
- [x] Validation: 12 focused reliability tests; 207 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Add coordinator-owned breaker registry and failure matrix integration.
- Exact next task: connect dependency-specific breakers to coordinator policy and user-visible partial status.

### Module 14 coordinator-owned circuit-breaker registry
- [x] Added coordinator-owned breaker registry keyed by backend, tenant, and environment.
- [x] Added tenant/environment scope fields to investigation tasks.
- [x] Verified same-scope breaker sharing and cross-tenant/environment isolation.
- [x] Verified healthy branches continue when a shared metrics breaker is open.
- [x] Validation: 36 focused registry/parallel tests; 209 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Add failure-matrix status propagation and explicit user-visible partial/inconclusive reporting.
- Exact next task: connect branch circuit outcomes to coordinator failure classifications and report uncertainty.

### Module 14 coverage-status propagation
- [x] Added deterministic `completed`/`inconclusive`/`failed` coverage classification.
- [x] Downgraded overconfident completed reports when specialist evidence is unavailable.
- [x] Preserved healthy evidence and named unavailable specialist branches in the user-visible summary.
- [x] Validation: 34 focused coverage/workflow tests; 211 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Integrate coverage status with end-to-end coordinator/report synthesis and failure-matrix classifications.
- Exact next task: connect coverage summary to the main investigation workflow and report acceptance path.

### Module 14 main workflow coverage integration
- [x] Added specialist branch results to graph state.
- [x] Added an injected investigation runner to the LangGraph path.
- [x] Applied coverage status before report artifact persistence and lifecycle completion.
- [x] Verified partial reports become `inconclusive` and zero-coverage investigations fail.
- [x] Validation: 213 full-suite tests, 1 skipped; Ruff and formatting passed.
- [ ] Complete Module 14 reliability/security gate with failure-matrix integration and controlled adversarial recovery review.
- Exact next task: run the Module 14 final conceptual review and identify remaining untested assumptions.

### Module 14 final review and completion
- [x] Explained timeout versus empty evidence, retry ownership, circuit-open uncertainty, and safe partial completion.
- [x] Explained untrusted runbook boundaries, deterministic authorization, least privilege, incident scope isolation, and sanitized audit data.
- [x] Passed the final conceptual review, debugging task, and failure-matrix design exercise.
- [x] Verified coverage propagation prevents unsupported causal claims when Metrics is unavailable.
- [x] Validation: `python -m pytest -q` -> 213 passed, 1 skipped; Ruff check and format check passed.
- Status: Completed.
- Known limitations: production coordinator wiring and a unified failure matrix for every dependency remain future integration work; live dependency behavior is represented by deterministic fixtures.
- Exact next task: begin Module 15 with evaluation dimensions, baselines, and the first held-out scenario set.
