# IncidentLens Learning Tracker

## Current position
- Roadmap: ../roadmap.md
- Module: 11 - Runbook RAG and change intelligence
- Phase: Orient
- Status: In Progress
- Mode: Guided Learning
- Exact current task: Implement a versioned runbook/change corpus and deterministic retrieval filters.
- Last completed evidence: Module 1 completed on 2026-09-10 through source review, learner explanations, project contract draft, failure-analysis review, and design record reconciliation.

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
| 9 | Memory, persistence, checkpoints, and artifacts | In progress | Checked | In progress |
| 10 | Planning, adaptive routing, budgets, and termination | Completed | Checked | Completed |
| 11 | Runbook RAG and change intelligence | Not started | Not checked | Not started |
| 12 | Hypothesis formation, critique, and calibrated confidence | Not started | Not checked | Not started |
| 13 | Human oversight, authorization, and safe actions | Not started | Not checked | Not started |
| 14 | Reliability, security, and adversarial behavior | Not started | Not checked | Not started |
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
- Sources/sections covered: `../roadmap.md` Module 2; Gemini API Function calling; Gemini API Structured outputs; LangChain Tools.
- Learner explanation or answer: Learner traced the loop as orchestrator goal/context -> model reasons about needed evidence -> requests a permitted tool -> application validates/executes and returns bounded observation -> model evaluates observations -> requests more data or returns a structured finding with claims, evidence IDs, and confidence. Learner explained that model output is probabilistic and can be wrong or manipulated, so deterministic application code must validate permissions, arguments, schemas, and limits before executing tools. Learner also explained that Pydantic validates structure, not truth: schema-valid reports can contain invented claims, irrelevant evidence citations, or unsupported conclusions.
- Exercise path/result: Implemented the deterministic loop, Gemini/LangChain adapter boundary, and baseline artifact runner with scripted offline tests. The rotated API key loaded successfully. After the message-protocol fix and one bounded retry, Gemini was reached twice but returned schema-invalid output; no live artifact was written.
- Changed files: src/incidentlens/baseline.py, tests/test_baseline.py, tests/test_live_gemini.py, pyproject.toml, docs/tracker.md, docs/learning.md, docs/design.md; earlier Module 2 files remain listed in prior implementation history.
- Commands and observed results: python -m pytest -q passed with 20 tests and one local google-auth/grpcio FutureWarning; python -m ruff check . passed; python -m ruff format --check . passed; python -m mypy src remains deferred because mypy is not installed; settings loaded the API key without exposing its value; the initial live call rejected gemini-2.5-flash with 404, so the configurable default was updated to gemini-3-flash-preview; offline retry tests passed; the bounded live retry reached the provider twice and ended with InvalidModelResponseError.
- Design decision/evolution: Added a testable single-agent loop boundary. The model client can return raw tool requests or final reports; application code validates the response union, validates tool names/arguments, executes tools, validates results, tracks observations, propagates permitted tool execution errors, and enforces max-step termination. The Gemini/LangChain adapter boundary is implemented and tested offline with fake chat models; live reachability and signed-message replay were exercised, but live final-report parsing remains unsuccessful.
- Untested assumptions: Live Gemini final-report parsing remains unsuccessful; provider token usage is extracted when LangChain exposes it; application-measured latency/model-call/tool-call metadata and offline artifact persistence are implemented; bounded retry handling is implemented; provider error classification remains covered by focused tests rather than broad live sampling; observed local google-auth/grpcio FutureWarning is not yet resolved; `mypy` remains deferred until installed or added to a development environment.
- Weak concepts: Continue assessing retries, rate limits, secret handling, and live Gemini adapter behavior. Learner correctly explained model-client versus deterministic application-code responsibilities, distinguished malformed model output from permitted tool execution failure, and justified isolating Gemini/LangChain behind `ModelClient` to avoid provider coupling.
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
- No Git repository metadata detected, so Git diff/status cannot be used as change evidence until a repository is initialized or the project is moved into one. Roadmap return point: Module 3 Orient.

## Exact next session
- Module and phase: Module 3 - Incident-response domain and realistic telemetry, Orient
- File/function/section: roadmap.md Module 3 Learn section and fixtures/incidents/payment_latency.json
- Next question or exercise: Explain what each telemetry signal can and cannot prove using the Module 3 fixture narratives.
- Next build task: Orient Module 3 and design the telemetry-neutral internal schema.
- Next validation command: `python -m pytest -q`; `python -m ruff check .`; `python -m ruff format --check .`; defer `python -m mypy src` until mypy is installed.




























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