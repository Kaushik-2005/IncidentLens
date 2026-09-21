# Multi-Agent Systems Learning Notes

## Module 1 - Multi-agent foundations and project contract

### Concept and why it exists
Module 1 separates deterministic software workflow from agentic behavior. IncidentLens should not become a collection of named prompts. Each agent must earn its place through distinct context, tools, permissions, or reasoning responsibility.

### Mental model and small example
A deterministic workflow step follows rules the application already knows: validate an incident, enforce state transitions, apply tool allowlists, stop when budgets are exhausted, or require human approval. An agent is useful when the system needs judgment under uncertainty: deciding which evidence matters, whether an error spike is causal or symptomatic, or whether evidence is insufficient.

Example: a workflow can fan out to logs, metrics, and traces at the same time. That is parallel execution, not automatically multi-agent reasoning. Specialist agents are justified only if each branch interprets a scoped evidence domain and returns structured findings.

### Internal behavior
A workflow owns predefined control paths. An agent receives a bounded task, context, tools, output contract, budget, and stopping rule. Its output is proposed data, not trusted truth. Application code must still validate structure, permissions, lifecycle transitions, and evidence references.

### IncidentLens application
IncidentLens starts with a deterministic project contract and proposed lifecycle: `created -> investigating -> awaiting_review -> completed | failed | cancelled`. Triaging and synthesis can be internal phases inside `investigating`, but they are not top-level lifecycle states unless the roadmap is explicitly changed.

Planned specialist agents are defensible when they operate over different evidence domains and tools, such as logs, metrics, traces, and deployment/change data. A synthesis component may combine structured findings, but final claims must cite evidence IDs.

### Boundaries, failure modes, and common mistakes
Common mistakes:
- Treating every specialist name as a real agent boundary.
- Giving every agent every tool and one shared long conversation history.
- Using persona-only agents, such as optimistic/skeptical/senior, without different evidence, tools, or responsibilities.
- Letting a planner freely decide lifecycle transitions or final conclusions.
- Writing final reports without evidence IDs.
- Treating agent agreement as proof.

A stronger design uses a deterministic orchestrator, least-privilege specialists with isolated context, structured evidence artifacts, verification against evidence, and synthesis that distinguishes observations, inference, hypotheses, and uncertainty.

### Alternatives and trade-offs
A single agent is preferable when the investigation is narrow, the context fits cleanly in one prompt, the tools overlap, and coordination would add cost without better evidence. Example: if an alert already points to PostgreSQL connection pool exhaustion, one agent can fetch relevant metrics/logs and confirm or reject that focused hypothesis.

Multiple agents become useful when separation creates measurable value: context isolation, distinct tool permissions, parallel evidence gathering, independently maintained capabilities, or independent verification. The trade-off is extra latency, model calls, token cost, coordination complexity, duplicated work risk, and conflict-resolution work.

### Exercise and validation observations
Learner drafted a project contract covering problem statement, actors, inputs, outputs, constraints, non-goals, lifecycle, system boundary, and three incident narratives.

Review corrections:
- Keep Gemini API as the project provider because it is a core roadmap decision.
- Treat `triaging` and `synthesizing` as possible internal phases while preserving the canonical top-level lifecycle.

Representative scenarios recorded in design notes:
- Database connection-pool exhaustion.
- Bad deployment as likely trigger.
- Misleading database-like symptom caused by downstream payment dependency.

### Interview explanation
IncidentLens should combine deterministic workflow with agents only where uncertainty justifies model judgment. Lifecycle transitions, tool permissions, budgets, schemas, and approval gates should be deterministic because they must be predictable, testable, and recoverable. Specialist agents are defensible when they have distinct evidence sources or tools, such as logs, metrics, and traces. Persona-only agents are usually weaker because they inspect the same evidence and create overlapping opinions rather than clearer boundaries.

### Sources
- Required roadmap section: [Module 1 in roadmap](../roadmap.md)
- LangChain, Multi-agent systems: https://docs.langchain.com/oss/python/langchain/multi-agent
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- AutoGen, Agent and Multi-Agent Applications: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/core-concepts/agent-and-multi-agent-application.html

### My questions, corrections, and revision items
- Learner correctly explained deterministic workflow versus agentic judgment.
- Learner correctly distinguished parallel tool execution from parallel specialist agent investigation.
- Learner correctly identified when a single agent is better than multiple agents for narrow, known-symptom confirmation.
- Continue reinforcing least-context, least-tool, evidence-ID, and deterministic lifecycle boundaries during Module 2 implementation.
## Module 2 - Gemini agent loop and single-agent baseline

### Concept and why it exists
Module 2 introduces the single-agent baseline and the basic agent loop. This is the simplest useful IncidentLens agent: one model-driven investigator with bounded tools, structured contracts, maximum-step termination, and application-owned validation.

The goal is not to build the final multi-agent system yet. The baseline gives us something measurable to compare against later.

### Mental model and small example
An agent loop is a controlled cycle:

1. Application sends the model the incident context, instructions, available tool schemas, and prior observations.
2. The model either asks to call a tool with structured arguments or produces a final answer.
3. Application code validates the requested tool name and arguments.
4. Application code executes the tool and validates/bounds the result.
5. The tool result is returned as an observation in the next model call.
6. The loop stops when the model returns a valid final report or when deterministic limits stop it.

Small IncidentLens example: the model asks to call `lookup_incident_fixture(incident_id="payment-latency-001")`; the app validates that this tool exists and that the incident ID is allowed; the app returns a bounded fixture summary; the model then writes a structured report citing that evidence.

### Internal behavior
Gemini function calling lets the model choose a declared function and provide arguments, but the function is executed by the surrounding application or framework, not by model text alone. Gemini structured outputs can ask the model to produce JSON that follows a schema. LangChain tools use typed signatures or Pydantic/JSON schemas so the model sees tool names, descriptions, and argument schemas.

In the current implementation, `ModelClient` is a protocol. Tests use a scripted model client so the loop boundary is deterministic and does not require network access or secrets.

### IncidentLens application
Implemented so far:
- `src/incidentlens/contracts.py`: Pydantic contracts for incident inputs, evidence, hypotheses, reports, tool calls, and model responses.
- `src/incidentlens/tools.py`: read-only fixture lookup tool and tool registry.
- `src/incidentlens/agent_loop.py`: deterministic loop runner that calls a model client, executes validated tool calls, records observations, and stops at max steps.
- `fixtures/incidents/payment_latency.json`: small synthetic fixture.
- `tests/test_agent_loop.py`: focused tests for the loop boundary and failure cases.

### Boundaries, failure modes, and common mistakes
The model may request an unknown tool, malformed arguments, too many calls, or a final report that is structurally valid but factually unsupported. Application code owns tool execution, permissions, argument validation, result bounds, final schema validation, and loop termination.

Structured output improves parseability; it does not prove that the content is true. The current report schema validates that cited evidence IDs exist, but it still cannot prove that the cited evidence actually supports the claim.

### Alternatives and trade-offs
We could call Gemini directly or through LangChain. The roadmap allows LangChain and requires Gemini through the maintained Google/LangChain integration when implementation begins. Direct SDK calls expose provider mechanics clearly; LangChain gives reusable tool abstractions that will matter later. For this project, the implementation keeps a small model adapter boundary so the rest of the code is not tightly coupled to one call style.

The current increment uses a fake/scripted model first. This gives deterministic tests for the application-owned boundary before introducing API keys, rate limits, network failures, and model variability.

### Exercise and validation observations
Implemented the first baseline increment: Python project metadata, Pydantic contracts, a fixture-backed harmless read-only tool, a tool registry, a deterministic loop runner, explicit model-response validation, and tests using a scripted model client. This intentionally avoids a live Gemini call so the tool boundary and failure behavior are testable without network or secrets.

Validation observed:
- `python -m pytest -q`: 12 passed, with one local google-auth/grpcio FutureWarning from importing the LangChain Google package.
- `python -m ruff check .`: passed after import formatting fixes.
- `python -m ruff format --check .`: passed after formatting.
- `python -m mypy src`: not run successfully because `mypy` is not installed.
- Config import with `PYTHONPATH=src` returned default model `gemini-2.5-flash`.

### Interview explanation
An agent loop is a bounded cycle where the model proposes either a tool call or a final structured report, but application code validates and executes tools, records observations, validates final structure, and enforces termination. Pydantic contracts make outputs parseable and constrain references such as evidence IDs, but they do not prove that a diagnosis is true. Truth still depends on grounded evidence and validation.

### Sources
- Required roadmap section: [Module 2 in roadmap](../roadmap.md)
- Gemini API, Function calling: https://ai.google.dev/gemini-api/docs/function-calling
- Gemini API, Structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- LangChain, Tools: https://docs.langchain.com/oss/python/langchain/tools
- Gemini 2.5 Flash model card: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash

### My questions, corrections, and revision items
- Learner traced the loop as orchestrator goal/context -> model reasons about needed evidence -> requests a permitted tool -> application validates/executes and returns bounded observation -> model evaluates observations -> requests more data or returns a structured finding.
- Learner correctly explained that the model should only request actions; deterministic application code must validate permissions, arguments, schemas, limits, execution, and termination.
- Learner correctly explained that Pydantic validates structure, not truth.
- Learner correctly mapped `model.invoke(...)` to probabilistic reasoning/proposal and `run_agent_loop(...)` plus `ToolRegistry.execute(...)` to deterministic control flow and safety boundaries.
- Added explicit malformed-output and tool-exception handling tests. Malformed model output is rejected at the model boundary as `InvalidModelResponseError`; a permitted tool that cannot satisfy the request raises `ToolExecutionError`.
- Learner correctly explained that malformed output means the model violated the response contract before the loop can interpret the action, while permitted tool execution failure occurs after a valid and authorized request reaches a failing dependency.
- Added `src/incidentlens/model_adapter.py`, a Gemini/LangChain adapter boundary behind `ModelClient`. It builds LangChain messages, parses LangChain tool calls and JSON final reports, and can bind declared tool schemas. Tests use fake chat models, so no API key or network call is required.
- Learner correctly explained that `ModelClient` keeps IncidentLens independent of Gemini/LangChain-specific APIs, supports swapping providers/frameworks, enables fake model tests, and confines provider parsing/tool-binding logic to one place.
- Added `AgentRunMetadata` and `AgentRunResult`. The application now measures model-call count, tool-call count, and elapsed milliseconds. Token fields are present but optional because reliable token usage depends on provider metadata from live model responses.








- Learner correctly distinguished application-measured metadata (model_calls, tool_calls, and elapsed_ms) from provider-reported metadata (input, output, and total tokens). Token fields remain optional because offline fake models and some provider responses may not expose usage, and exact Gemini adapter fields must be confirmed against a live response rather than invented.
- Added src/incidentlens/baseline.py. run_baseline saves a typed, provider-neutral JSON artifact containing the incident, validated report, and run metadata. require_api_key fails before live-client construction when no API key is configured.



\n- Learner correctly explained that max-step exhaustion proves only that no valid final report was reached within the configured budget. It does not identify the cause; repeated tools, weak prompting, insufficient evidence, model reasoning, or tool behavior remain possible. The deterministic loop owns the limit and handling, while model improvements belong at the adapter/prompt boundary.\n

- Learner identified that tool results should be represented as protocol messages tied to the original tool-call ID, rather than inserted as unrelated human text.
- Implemented ToolObservation plus adapter reconstruction of AIMessage and ToolMessage pairs. This preserves the model call/result relationship across stateless adapter invocations and should reduce repeated identical tool requests.


- Live validation after the protocol fix reached Gemini successfully but later encountered a 503 UNAVAILABLE capacity error. This demonstrates why provider failures are separate from malformed model output and why bounded retry policy belongs to deterministic application code.


- Added bounded provider handling. The adapter classifies provider failures as retryable or terminal, while the deterministic loop owns max_model_retries and counts every attempt against max_steps. Usage metadata is normalized from LangChain usage_metadata/response_metadata and remains optional when absent.


- Learner correctly explained that retries must consume the same model-call budget because they incur latency, cost, and provider capacity, and that missing token metadata must remain null because zero and unavailable have different meanings.


- Final review answer: Learner correctly explained that the baseline evaluates process quality such as protocol compliance, budgets, relevant evidence gathering, evidence-ID citations, termination, and schema-valid output. Factual root-cause correctness requires hidden ground truth or independent validation because a well-executed run can still mistake correlation for causation.


- Final review answer: Learner distinguished malformed model output, retryable provider failure, permitted tool execution failure, and unsupported factual conclusion as separate contract, provider, execution, and evidence/reasoning failure layers with different owners.


- Final review answer: Learner correctly separated successful evidence collection from conclusion acceptance. The application may store tool-returned E1-E3 but must flag or reject a high-confidence claim contradicted by E2. Valid IDs establish citation existence, not correct interpretation of all relevant evidence.


- Final review answer: Learner correctly specified that a run after one retryable 503 records two attempts, one retry, successful status, and null token fields when the provider reports no usage.


 - Debugging review: Learner identified immediate retries without backoff/jitter, overbroad provider-error classification, and incomplete artifact history as production risks. They proposed tests for transient versus permanent errors and emphasized that incorrect classification can consume the budget while obscuring the true failure.



### Retry metadata and live validation
The final Module 2 exercise was implemented as a nested ProviderRetryMetadata contract. It records attempts, retries, a small internal enum of sanitized retryable failure kinds, and bounded retry delays. Deterministic application code validates retry configuration, applies capped exponential backoff, counts retries against the model-call budget, and keeps unavailable token usage as null. Offline tests observed 20 passed, with Ruff checks passing. A bounded live run reached Gemini twice after the rotated key was loaded but ended with InvalidModelResponseError; this does not prove factual failure or provider failure, only that the adapter did not receive a schema-valid final response.

### Manual live-test workflow
The Gemini integration test is isolated in tests/test_live_gemini.py and is skipped unless RUN_LIVE_GEMINI=1 is set. This keeps normal test runs deterministic and prevents accidental provider calls. When enabled, it uses the synthetic fixture, the configured retry budget, and writes the validated baseline artifact under artifacts/.

- Live-test follow-up: fenced bare JSON was normalized at the adapter boundary and covered by an offline regression test. The next live run passed that parsing point but hit Gemini 429 RESOURCE_EXHAUSTED after the configured retry budget; quota exhaustion is a provider/account constraint, not evidence of a diagnosis failure.

- Live artifact confirmation: The Gemini 3 baseline produced a schema-valid report after 3 model calls, including 1 service-unavailable retry and 1 fixture tool call. Token metadata was available. This proves the live adapter and artifact path work; it does not prove that the high confidence causal conclusion is factually correct.
## Module 3 - Incident-response domain and realistic telemetry

### Concept and why it exists
Telemetry signals provide complementary but non-equivalent evidence. Metrics show magnitude and timing, logs record application events, and traces localize behavior along a request path. Combining signals improves diagnosis, but correlation still does not automatically prove causation.

### Mental model and small example
For the payment latency fixture, E1 proves elevated checkout latency, E2 proves recorded payment-service timeout events, and E3 localizes added request latency to checkout-api calls to payment-service. Payment-service-side metrics matching the same time window would strengthen the hypothesis through independent corroboration, but would not alone prove causation.

### Learner check
The learner correctly explained what E3 adds beyond E1 and E2, and proposed correlated payment-service latency/error metrics as stronger independent evidence while preserving uncertainty about causation.

### Correlation and time check
The learner correctly explained that IncidentLens should correlate logs and traces using request/trace identifiers plus normalized timestamps and known clock-skew bounds. Time proximity alone is insufficient; when identity or timing cannot be established, the relationship should remain uncertain.

### Evidence-layer classification check
The learner correctly classified user-visible 5xx errors as a symptom, payment-call duration as a contributing-factor localization, and deployment-related database exhaustion as a root-cause hypothesis proposing an underlying causal chain.

### Baseline and timeline check
The learner correctly explained that a peak-only window captures correlation at one moment but not signal evolution. Multiple components may appear unhealthy simultaneously, so onset order and recovery behavior are needed to distinguish causes from cascading symptoms.

### RED and USE check
The learner correctly mapped rate, errors, and duration to RED, and database utilization, saturation, and connection errors to USE. They also identified the key evidence distinction: hypothetical investigative signals such as request rate or pool saturation must not be reported as observed because the current fixture contains only E1 latency metrics, E2 timeout logs, and E3 trace localization.

### Span relationship check
The learner correctly identified trace ID, span ID, and parent span ID as the core fields needed to establish a span relationship. Additional service/resource identity and timing fields are needed to interpret ownership and incident-window relevance.

### Ground-truth leakage check
The learner correctly identified that returning a root_cause field from the fixture loader leaks evaluator-only information into the agent context, invalidating the investigation and its measured accuracy.

### Manual diagnosis exercise
The learner completed a disciplined diagnosis of the payment latency fixture. They identified E1 as the latency symptom, E2 as recorded timeout events, and E3 as dependency-path localization. They assigned a medium-confidence payment-service degradation hypothesis, proposed a network alternative, listed missing causal/deployment/resource evidence, and suggested bounded RED/USE and change-history queries. The conclusion correctly localized degradation without claiming definitive root cause.
### Telemetry contract design
Implemented the first Module 3 contract increment in src/incidentlens/telemetry.py. Agent-facing records are provider-neutral, versioned, timezone-aware, and preserve original plus normalized timestamps, correlation IDs, payload, and provenance. Evaluator fixtures may contain hidden ground truth, but load_agent_fixture projects explicitly to AgentIncidentFixture and excludes hidden fields. Validation rejects naive timestamps, non-UTC normalized timestamps, inconsistent normalization, and invalid incident windows.

### Fixture and edge-case increment
Added payment_failure.json and resource_exhaustion.json with metric, log, trace, partial, and distractor-ready structures. Added deterministic records_for_trace ordering and manifest record-reference validation. Tests cover missing signal availability, partial-record warnings, out-of-order records, invalid references, and both new fixtures.


### Module 3 build increment
The manifest now supports load profile, fault injection, timeline events, expected evidence IDs, distractors, and affected services. The loader uses a fail-fast policy for malformed structure, while intentionally partial records preserve is_partial and validation_warnings. records_in_window returns deterministic normalized-time results and an empty list for valid windows with no records. records_for_trace groups shared trace IDs and sorts by normalized timestamp. Three standardized evaluator fixtures now cover payment failure, service latency, and database resource exhaustion; hidden ground truth remains evaluator-only.

### OpenTelemetry follow-up
The later OpenTelemetry Demo integration remains proposed. It will require a local containerized demo, collector/exporter configuration, and resources for the demo services plus telemetry backends. Recorded JSON fixtures remain the reproducible test and teaching mode even after live integration.
- Validation confirmation: Telemetry-focused tests passed 16/16 and the complete suite passed 37 tests with 1 live test skipped by default. This confirms the new fixture, schema, correlation, partial-record, malformed-record, and empty-window behaviors under deterministic tests.

- Live validation confirmation: The learner confirmed the opt-in Gemini live-case test works end to end against recorded synthetic telemetry, including report artifact generation.

### Final conceptual review
The learner passed all five Module 3 review questions. They correctly explained signal capabilities and limits, trace-ID correlation over timestamp proximity, preservation of original and normalized timestamps, ground-truth exclusion through the agent fixture projection, and the distinction between symptoms, contributing factors, and root-cause hypotheses.

### Final debugging review
The learner passed the debugging exercise by identifying timezone relabeling, implicit ground-truth projection, ambiguous inclusive window boundaries, unvalidated query bounds, and the incorrect conversion of empty evidence into a no-incident conclusion. They correctly emphasized that retrieved telemetry describes available evidence, not necessarily the complete real-world event.

### Module 3 completion
Module 3 review is complete. The learner demonstrated signal boundaries, identity-based correlation, timestamp provenance, evidence-layer distinctions, baseline/recovery reasoning, hidden-ground-truth isolation, and safe empty/partial query semantics. The implementation and tests now provide the telemetry-neutral foundation for Module 4 tool engineering.

## Module 4 - Tool engineering and the observation boundary

### Concept and why it exists
A tool is a capability and authorization boundary, not merely a callable function. The model proposes a tool request, while deterministic application code validates the tool name, arguments, scope, permissions, limits, execution, and result.

### Learner check
The learner correctly assigned out-of-scope file rejection to the deterministic tool/application layer before file access, and identified resolved-root validation as necessary for path traversal and alternate path forms.

### Narrow typed tool check
The learner correctly explained why a structured metrics query is safer than arbitrary SQL: it constrains metric selection, time bounds, limits, access scope, and audit representation while reducing injection and expensive-query risk.

### Bounds and truncation check
The learner correctly explained that truncated metrics must propagate into report limitations and unknowns, constrain the claim to available data, and may reduce confidence rather than being silently ignored.

### Tool error taxonomy check
The learner correctly distinguished a successful empty result from a timeout: zero records after a completed query is known absence within scope, while a timeout means evidence availability is unknown because retrieval did not complete.

### Provenance and raw evidence check
The learner correctly explained that raw tool results are evidence while agent summaries are interpretations. Preserving raw artifacts enables citation verification, contradiction detection, re-evaluation, and auditability across later report stages.

### Deterministic preprocessing check
The learner correctly specified that trace summaries must preserve evidence identity, provenance, correlation IDs, timing, service/operation context, outcomes, relevant attributes, completeness flags, and stable raw-evidence references. They correctly separated volume reduction from causal conclusion.

### Module 4 bounded metrics tool increment
Implemented a provider-neutral TelemetryQueryResult with explicit success, partial, dependency-error, and invalid-query statuses. Result invariants prevent contradictory error/truncation/count combinations. The query_metrics tool uses typed arguments, UTC time bounds, a maximum one-hour window, a maximum result limit, and active-incident scope. It never exposes SQL, filesystem paths, or arbitrary source selectors. Empty successful results remain distinct from errors, and truncated results retain partial status.

### Module 4 final conceptual review
The learner passed the four review questions. They correctly explained tools as deterministic capability and authorization boundaries, justified typed bounded queries over arbitrary SQL, distinguished empty/partial/timeout/invalid outcomes, and explained why truncation, provenance, and raw evidence references must propagate through findings. They also articulated the request-to-claim provenance chain.

### Final debugging exercise
The learner identified seven deterministic-boundary defects in a metrics tool: missing active-incident scope, unbounded time and result limits, non-unique query IDs, uncategorized backend failures, hard-coded truncation, trusted raw rows, and missing record validation. They correctly connected each defect to scope authorization, resource bounds, auditability, semantic error handling, completeness, normalization, and evidence integrity.

### Final implementation exercise
The learner designed and validated `TelemetryQueryResult` with distinct success, partial, dependency-error, and invalid-query outcomes. They correctly explained that a successful empty result means the query completed with no matches, while a timeout leaves evidence availability unknown. The complete trace-record example preserved identity, timestamps, correlation IDs, payload, and provenance.

### Module 4 status
The core Module 4 evidence gate is satisfied: the learner explained telemetry as observation rather than automatic truth and demonstrated bounded outputs and explicit least-privilege permissions. The implemented increment is `query_metrics` over agent-projected recorded fixtures plus `ToolRegistry.restrict_to`. Broader log, trace, change, time-series, and critical-path tools remain scoped as future extensions.

## Module 5 - LangGraph state and deterministic orchestration

### Concept and why it exists
Graph state is authoritative application data used for routing, validation, recovery, and terminal decisions. Conversation messages are model context, not the application database.

### Learner check
The learner correctly explained that status, model-call counts, and reports belong in typed graph state because they must be deterministic, checkpointable, and usable for routing. They correctly assigned lifecycle transition authority to the deterministic orchestrator and identified schema, required-step, and evidence-reference validation before completion. Clarification: evidence-ID existence proves reference integrity, not factual or causal support.

### IncidentLens application
The current baseline keeps observations and lifecycle control inside a local loop. Module 5 will make lifecycle state explicit and place validation, triage, investigation, synthesis, failure, cancellation, budgets, and terminal invariants in graph-owned state. Raw telemetry remains outside graph messages; state should carry bounded summaries and artifact references.

### My questions, corrections, and revision items
Next exercise: define a minimal typed investigation state and legal transition table before selecting LangGraph APIs.

### State-design exercise
The learner defined `IncidentGraphState` with stable incident identity, lifecycle status, current node, evidence references, report, counters, and sanitized errors. The transition contract correctly models forward-only normal progress, failure/cancellation from active states, and terminal states. The learner identified invalid skip, backward, and terminal transitions and added invariants for validated completion reports, monotonic counters, immutable incident identity, existing evidence artifacts, and deterministic completion authority. Terminology correction recorded: use `SYNTHESIZING`; `current_node` is execution metadata while `status` is lifecycle state.

### Nodes, edges, and reducers check
The learner correctly explained that parallel specialist nodes must not mutate shared lifecycle status because they are workers, not workflow authorities. They correctly selected deterministic deduplicating merge behavior for evidence references, producing `['E1', 'E2', 'E3']` from overlapping branch outputs.

### Deterministic counter update increment
Implemented `src/incidentlens/workflow_state.py::record_usage`. Usage updates accept only nonnegative increments, derive new totals from existing state, and preserve incident identity. Focused validation passed 9 workflow-state tests and Ruff check passed.

### LangGraph lifecycle implementation
Implemented `src/incidentlens/workflow_graph.py` using LangGraph 1.2.11. The graph has explicit validation, triage, investigation, and synthesis nodes with conditional routing to terminal states. Lifecycle transitions remain owned by `workflow_state.py`; the injected report factory represents the model/report boundary and is never allowed to choose lifecycle status. Cancellation is an explicit state input, report failures become sanitized `FAILED` state, and raw provider exceptions are not copied into graph state.

Validation exposed and corrected a graph-output detail: LangGraph returns the final Pydantic state as a mapping, so consumers must treat graph output as serialized state and revalidate it at their boundary.

### Graph execution and transition coverage
Added execution inspection for the compiled graph and expanded lifecycle tests across active cancellation and terminal rejection paths. The graph emits the expected node sequence `validate -> triage -> investigate -> synthesize`, routes terminal states to `END`, and preserves deterministic transition ownership. Full validation passed 66 tests with 1 live test skipped.

### Module 5 completion review pending
Implementation evidence is complete, but the module remains pending final conceptual review and failure-analysis answers.

### Module 5 final review
The learner passed the final review. They correctly distinguished authoritative graph state from model message history, explained why raw telemetry should remain in an evidence store, assigned lifecycle ownership to deterministic orchestration, described deduplicating evidence reducers, and justified terminal routing to `END`. In the failure-analysis task, they correctly rejected `COMPLETED` with a missing report, placed validation at the transition boundary, distinguished bounded correction from unrecoverable failure, and required sanitized shared error state.

### Module 5 completion
Module 5 completed with typed lifecycle state, deterministic transitions, monotonic usage tracking, explicit LangGraph nodes and conditional edges, cancellation and failure paths, graph execution inspection, transition coverage, and final conceptual/failure-analysis review.

## Module 6 - Specialization and context engineering

### Concept and why it exists
A separate agent is justified by a defensible boundary, not by a different name or persona. The boundary should change the agent's objective, visible context, permitted tools, output contract, budget, or stopping rule.

### IncidentLens application
The planned Logs, Metrics, and Traces specialists should receive isolated incident briefs plus only their evidence-domain summaries and tools. The existing `ToolRegistry.restrict_to` provides the application primitive for least-privilege tool exposure. The model must not receive unrelated specialist conclusions during initial investigation, which reduces anchoring and duplicated reasoning.

### My questions, corrections, and revision items
Module 6 begins with role-boundary justification before agent implementation.

### Role-boundary knowledge check
The learner correctly rejected a skeptical persona as insufficient because disagreement is not a verification method. They defined Verification/Contradiction as a concrete responsibility: validate claims and citations, search counter-evidence, and detect unsupported causal jumps. They correctly restricted Metrics Agent access to the incident brief and metric domain while excluding logs, traces, deployments, arbitrary files/SQL, hidden ground truth, and other incidents.

### Isolated-context knowledge check
The learner correctly defined Metrics Agent input as incident scope, affected services, normalized time window, neutral incident description, and bounded metric access. They correctly excluded other agents' conclusions, non-metric telemetry, hidden ground truth/evaluator labels, arbitrary SQL/filesystem/cross-incident access, and final synthesis reports to prevent anchoring, contamination, leakage, and capability escalation.

### Module 6 specialist boundary implementation
Implemented `src/incidentlens/specialists.py` with versioned role contracts for Logs, Metrics, and Traces specialists. Each contract defines objective, domain-specific tools, signal types, budgets, output schema, and stopping rule. `SpecialistContext` is an isolated, extra-forbidden input model that filters evidence to the role's signal domain and contains no peer conclusions, hypotheses, or evaluator data. `SpecialistFinding` distinguishes observation, inference, and hypothesis claims, requires unique evidence IDs, and supports deterministic citation validation.

The current implementation defines `search_logs`, `query_metrics`, `search_traces`, and `get_trace` as role capabilities, but only `query_metrics` is currently backed by a runtime tool. The other capabilities remain explicitly deferred rather than exposed as working tools.

Validation: `python -m pytest -q` passed 71 tests with 1 live test skipped; Ruff check and format check passed.

### Module 6 runtime tool increment
Implemented bounded `search_logs`, `search_traces`, and `get_trace` capabilities in `src/incidentlens/telemetry_tools.py`. Each tool validates typed UTC windows and limits where applicable, enforces the active incident scope, preserves provider-neutral `TelemetryRecord` results, and returns structured query metadata. Trace retrieval uses stable trace IDs and deterministic record ordering. Focused specialist-tool tests passed 5 tests; full validation passed 76 tests with 1 live test skipped.

### Role-confusion validation
Added parameterized tests for Logs, Metrics, and Traces contexts. Each specialist now has test evidence that unrelated signal domains are excluded, peer conclusions and ground truth are absent, and runtime registries expose only declared tools. Focused tests passed 15; full validation passed 81 tests with 1 live test skipped.

### Missing-evidence validation
Added tests for empty domain context across all specialist roles. Missing telemetry remains an explicit empty observation; it does not become a health or absence claim. Findings require at least one real evidence ID, and citation validation rejects invented IDs when the available evidence set is empty. Full validation passed 86 tests with 1 live test skipped.

### Module 6 final review
The learner passed all five conceptual questions and the failure-analysis task. They correctly justified specialist separation through distinct capabilities and evidence scopes, identified anchoring and confirmation bias, handled empty/partial metrics without unsupported conclusions, separated tool permissions from signal permissions, and rejected structurally valid but ungrounded evidence citations. They correctly classified leaked logs, peer conclusions, and expected root cause as context-construction or ground-truth-isolation violations, while distinguishing unauthorized tool calls as a separate authorization failure.

### Module 6 completion
Module 6 completed with versioned Logs, Metrics, and Traces contracts, isolated context construction, least-privilege runtime registries, structured evidence-linked findings, role-confusion tests, missing-evidence tests, and final conceptual/failure-analysis review.

## Module 7 - Coordination topologies and protocol design

### Concept and why it exists
Coordination topology defines who assigns work, how agents communicate, where shared results live, and who resolves conflicts. IncidentLens should begin with a centralized coordinator and explicit specialist contracts rather than decentralized peer-to-peer coordination.

### IncidentLens application
The coordinator should issue bounded task envelopes to Logs, Metrics, and Traces specialists. Specialists should return structured findings or artifact references through typed contracts. Initial investigations remain independent; deterministic aggregation and later verification combine results. The coordinator owns routing, budgets, duplicate detection, and termination.

### My questions, corrections, and revision items
Module 7 begins with topology comparison and selection before implementing inter-agent messages.

### Topology and task-envelope check
The learner correctly selected centralized supervisor/workers coordination for IncidentLens because it preserves deterministic routing, budgets, permissions, lifecycle control, and auditability while allowing specialist independence. They correctly identified peer-to-peer risks including duplicate work, circular handoffs, uncontrolled calls, and inconsistent state. Their task envelope includes task identity, incident scope, role, neutral objective, time and service scope, tools, signal types, permitted evidence, budgets, and output contract.

### Message-contract knowledge check
The learner correctly explained that `task_id` and `agent_id` provide provenance, traceability, role enforcement, and duplicate/retry detection. They correctly treated duplicate findings as idempotent delivery rather than independent evidence and proposed a stable finding ID or task/execution key so duplicates do not inflate confidence or counts.

### Module 7 coordination-contract implementation
Implemented `src/incidentlens/coordination.py` with versioned `InvestigationTask` and `SpecialistFindingMessage` contracts. Semantic validation checks task, incident, role, and evidence scope. `FindingInbox` provides deterministic idempotency: exact retries are ignored, conflicting duplicate finding IDs are rejected, and unknown task IDs are rejected before storage.

Validation: coordination tests passed 8 tests; full validation passed 94 tests with 1 live test skipped. The learner has passed topology, task-envelope, and message-contract conceptual checks; final Module 7 review remains pending.

### Module 7 coordinator and topology implementation
Implemented deterministic coordinator task creation from specialist role contracts, with incident/time/service scope and role-specific evidence references. Added small router, handoff, and supervisor-workers pattern labs plus a typed decision matrix; supervisor-workers is selected for IncidentLens because it preserves centralized routing and auditability while supporting independent specialist work. The coordinator accepts findings through `FindingInbox`, preserving semantic validation and idempotency.

Validation: focused coordination tests passed 11 tests; full validation passed 97 tests with 1 live test skipped. Final Module 7 conceptual review remains pending.

### Module 7 final review
The learner passed all five conceptual questions and the failure-analysis task. They correctly justified centralized supervisor-workers coordination, distinguished task instructions from specialist findings, explained semantic validation before storage, defined exact versus conflicting duplicate handling, and kept topology under deterministic architectural control. They correctly rejected a finding with mismatched incident, role, and evidence scope before duplicate processing, and identified agent identity as an additional coordinator-owned check.

### Module 7 completion
Module 7 completed with topology comparison labs, supervisor-workers selection, versioned task/finding contracts, semantic validation, deterministic coordinator task creation, idempotent finding intake, incompatible-message tests, and final conceptual/failure-analysis review.

### Module 8 fan-out/fan-in check
The learner correctly explained that parallel specialist execution reduces latency and supports independent evidence gathering, while introducing races, duplicates, nondeterministic ordering, partial failures, load, and conflicting state mutation risks. They correctly handled Logs/Traces success plus Metrics timeout as a useful partial investigation: preserve successful findings, retain the timeout as unavailable evidence, and mark overall coverage incomplete without inferring metric health.

### Module 8 deterministic aggregation check
The learner correctly explained why completion order cannot define aggregate ordering: network, model, retry, and backend timing vary across runs. They identified stable ordering benefits for reproducibility, tests, serialization, deduplication, debugging, and auditability, while correctly noting that order must not imply evidentiary importance.

### Module 8 parallel runner implementation
Implemented `src/incidentlens/parallel_investigation.py` with typed branch outcomes, semaphore-bounded execution, per-branch timeouts, sanitized worker failures, cancellation classification, returned-finding validation, and stable Logs/Metrics/Traces result ordering. Replaced the skipped async test with `asyncio.run` so timeout behavior is actually executed without adding an unneeded pytest plugin.

Validation: focused parallel tests passed 5 tests; full validation passed 102 tests with 1 live test skipped. Global deadline behavior, cancellation of already-running sibling tasks, and deterministic aggregate reducers remain next concerns.

### Module 8 completion implementation
Completed the parallel runner with a global investigation deadline, cancellation of unfinished branches, preservation of completed sibling results, deterministic `FindingInbox` aggregation, duplicate-finding suppression, and sequential-versus-concurrent latency comparison. The corrected async tests execute real timeout and failure behavior without relying on a missing pytest plugin.

Validation: focused parallel tests passed 8 tests; full validation passed 105 tests with 1 live test skipped. Final Module 8 conceptual review and failure-analysis exercise remain pending.

### Module 8 final review
The learner passed all five conceptual questions and the failure-analysis task. They correctly explained fan-out/fan-in, stable ordering, per-branch versus global deadlines, duplicate suppression, and partial-result policy. They correctly preserved successful Logs/Traces findings, represented Metrics timeout and pending Traces work distinctly, rejected automatic global failure when a valid partial report remains possible, and stated that timeout never proves metric health or absence.

### Module 8 completion
Module 8 completed with bounded concurrent specialist execution, per-branch and global deadlines, cancellation handling, structured partial results, deterministic role-order fan-in, FindingInbox aggregation, duplicate suppression, controlled latency comparison, and final conceptual/failure-analysis review.

### Module 9 knowledge check
The learner correctly distinguished graph state, checkpoints, artifacts, and long-term memory. They explained that resume should reuse validated completed tool results to avoid cost, inconsistent changing telemetry, duplicate evidence, and repeated side effects, while rerunning only incomplete or policy-approved work. They correctly described thread-scoped checkpoints as state for one investigation and cross-investigation memory as deliberately shared operational knowledge. Refinement: long-term memory requires explicit promotion, provenance, retention, and poisoning controls.
### Module 9 checkpoint recovery exercise
The learner correctly handled both crash windows. When a validated evidence artifact exists but the checkpoint is stale, recovery should reconcile the artifact using a stable task/tool execution identity and reuse it without repeating the query. When neither checkpoint completion nor artifact commit exists, the pending read may be retried under normal budget and retry policy. The distinction prevents duplicate evidence and preserves truthful recovery.
### Module 9 artifact and versioning check
The learner correctly required incident and execution-scope validation for artifact references, rejecting cross-incident artifacts as integrity violations. They correctly required checkpoint schema-version validation before state restoration, allowing only deterministic migration or a sanitized unsupported-version failure; unknown versions must never be guessed.
### Module 9 persistence implementation
Implemented `src/incidentlens/persistence.py` with versioned `StoredArtifact` and `Checkpoint` contracts. `ArtifactStore` uses stable path-safe IDs, atomic JSON replacement, exact-duplicate idempotency, conflict detection, corruption classification, and incident-scope validation. `CheckpointStore` validates persisted JSON and rejects unsupported state versions before restoration.

Validation: `python -m pytest -q` passed 113 tests with 1 live test skipped; Ruff check and format check passed. LangGraph checkpointer integration, artifact references in graph state, and restart/resume orchestration remain pending.
### Module 9 LangGraph checkpoint exercise
Integrated an optional LangGraph checkpointer and interrupt-before configuration into `build_incident_graph`. The workflow can pause before investigation and resume with the same stable `thread_id`; focused workflow tests passed 6 tests. Durable artifact references are not yet connected to graph state.
### Module 9 artifact-aware resume validation
Completed the graph checkpoint exercise by resuming with the same stable thread ID and verifying that synthesis persisted a durable report artifact and added its reference to graph state. Focused state, graph, and persistence tests passed. The test validates artifact-backed resume after interruption; broader stale-reference and duplicate-resume validation remain pending.
### Module 9 remaining persistence safeguards
Added explicit unavailable-artifact handling, checkpoint reference validation within incident scope, configurable artifact byte and count limits, atomic checkpoint writes, durable evidence artifacts, and duplicate-resume assertions. Full validation passed 118 tests with 1 live test skipped; Ruff checks passed.
### Module 9 final review and completion
The learner correctly distinguished graph state, checkpoints, artifacts, and long-term memory; explained artifact-before-checkpoint commit ordering; rejected missing and cross-incident artifacts as recovery integrity failures; required stable thread IDs; and rejected unknown checkpoint versions without deterministic migration. Implementation evidence covers artifact-aware graph resume, durable evidence/report artifacts, duplicate-resume idempotency, missing/corrupt/version-invalid data, size limits, and retention. Full validation passed 119 tests with 1 live test skipped. Module 9 completed. Filesystem persistence and a dedicated recovery service boundary remain production-oriented limitations.
## Module 10 - Planning, adaptive routing, budgets, and termination

### Concept and why it exists
Planning determines which investigation work is worth doing, while deterministic orchestration decides what is authorized, bounded, and finished. Module 10 addresses the trade-off between gathering enough independent evidence and avoiding unnecessary agents, duplicate work, runaway follow-ups, and unbounded cost.

### Mental model and small example
The model may propose: `query metrics for payment-service` because a trace finding leaves a dependency-health gap. The coordinator validates that proposal against the active incident, role/tool permissions, duplicate-task rules, and remaining budget before dispatching it. The model proposes; application code authorizes and terminates.

### Internal behavior
A plan should be a typed set of bounded tasks with stable IDs, objectives, dependencies, and budgets. Routing should use deterministic rules for known constraints and bounded model judgment only where evidence creates a genuine information gap. Termination should check global deadlines, call/tool/token limits, follow-up-round limits, duplicate or circular tasks, and report sufficiency.

### IncidentLens application
The existing `InvestigationCoordinator` creates deterministic specialist tasks and `run_parallel` bounds execution. Module 10 adds complexity-aware selection, one bounded follow-up round, and a coordinator-owned termination decision without allowing the planner to mutate lifecycle state.

### Boundaries, failure modes, and common mistakes
A model-generated plan can under-delegate, request every specialist, repeat an existing task, create a circular dependency, or request impossible evidence. Each is a proposal-validation problem, not a reason to let the model control budgets or lifecycle transitions. Budget exhaustion should produce a partial or inconclusive report when possible, not a fabricated complete diagnosis.

### Alternatives and trade-offs
Static decomposition is predictable and cheap but may waste work on narrow incidents. Fully model-generated planning adapts to evidence but is harder to bound and audit. A hybrid approach is appropriate: deterministic baseline tasks plus at most one validated, budgeted follow-up round.

### Exercise and validation observations
Orientation started; knowledge check pending.

### Interview explanation
The coordinator owns authorized planning, execution routing, budgets, and termination. The model can identify evidence gaps and propose follow-up tasks, but deterministic code validates, deduplicates, bounds, dispatches, and decides when the investigation ends.

### Sources
- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [LangGraph: Multi-agent workflows](https://docs.langchain.com/oss/python/langchain/multi-agent)

### My questions, corrections, and revision items
- Knowledge check pending: explain why a model plan cannot directly create unlimited tasks or end the workflow.
### Module 10 planning ownership check
The learner correctly explained why static planning needs bounded adaptive follow-up, why model-generated plans require deterministic validation, and why duplicate or over-budget proposals must not execute. Refinement: duplicate detection must use a coordinator-owned canonical task fingerprint over normalized scope/objective/tool parameters, not a model-supplied identity alone.
### Module 10 budget and termination check
The learner correctly treated model and tool budgets as separate deterministic resources. They rejected a change follow-up when the tool budget was exhausted, preserved remaining model capacity for synthesis, and required the final report to describe the skipped investigation as an unknown limitation rather than evidence that no change occurred.
### Module 10 follow-up contract check
The learner correctly designed a model-only `FollowUpProposal` containing an evidence gap and motivating evidence, without authorization or budget fields. They defined deterministic grounding, role, idempotency, round, budget, and deadline checks, and correctly kept validation side-effect-free until scheduling.
### Module 10 follow-up scheduling implementation
Implemented deterministic `InvestigationCoordinator.schedule_follow_up(...)` in `src/incidentlens/coordination.py`. Accepted model proposals are converted into scoped `InvestigationTask` objects using role-owned tools, signal types, and bounded budgets. Scheduled tasks are registered with `FindingInbox`, coordinator-local canonical task keys prevent duplicate scheduling even with stale caller context, and active incident scope is enforced before task creation.

Validation: coordination tests passed 17 tests; full validation passed 125 tests with 1 live test skipped; Ruff check and format check passed. Complexity-aware baseline selection, explicit plan contracts, budget accounting across the full investigation, and deterministic termination remain pending.
### Module 10 planning, budget, and termination implementation
Implemented deterministic `IncidentComplexity` classification and role-selection policy, a mutable `BudgetLedger`, explicit `TerminationDecision` reasons, and coordinator-owned follow-up scheduling. Simple incidents select only metrics; broader incidents select all available specialists. Follow-up tasks are validated, scope-checked, permission-derived, budget-bounded, registered for findings, and deduplicated before scheduling.

Validation: coordination tests passed 22 tests; full validation passed 130 tests with 1 live test skipped; Ruff check and format check passed. Final Module 10 conceptual review remains pending.
### Module 10 final review and completion
The learner correctly assigned model proposal versus deterministic coordinator ownership, justified complexity-aware specialist selection, handled independent model/tool budget exhaustion, and explained duplicate/circular follow-up risks. They correctly rejected a deployment proposal after the follow-up limit and required a truthful unresolved deployment limitation rather than a negative causal conclusion. Module 10 completed with deterministic complexity policy, global budget ledger, termination decisions, bounded follow-up scheduling, and 130 passing tests with 1 live test skipped.
## Module 11 - Runbook RAG and change intelligence

### Concept and why it exists
IncidentLens needs operational knowledge and deployment history, but these sources answer different questions from telemetry. Retrieval can provide relevant runbook guidance or change-event context; it cannot turn semantic similarity into proof of root cause.

### Mental model and small example
- **Retrieval:** fetches existing documents or events matching a query and deterministic metadata filters.
- **Memory:** persists knowledge intentionally across investigations.
- **Tool call:** performs a bounded application action, such as querying change events or retrieving a runbook section.

A runbook section saying "connection pool exhaustion can cause checkout timeouts" is guidance. A metric or log record showing pool exhaustion during the incident is incident evidence. The final report must cite and label them separately.

### Internal behavior
Retrieved documents need stable IDs, exact section citations, service/version metadata, validity windows, and provenance. Filters should be applied deterministically before or alongside ranking. Stale, contradictory, missing, or malicious retrieved text must remain untrusted content and must not override system instructions or evidence contracts.

### IncidentLens application
Module 11 adds a small versioned runbook corpus and a Change Agent for deployment/configuration events. Both remain read-only and bounded. The Runbook Agent provides procedural guidance; the Change Agent provides change-event observations that can support or contradict a deployment hypothesis.

### Boundaries, failure modes, and common mistakes
Semantic similarity is not causal evidence. A highly similar runbook can be outdated or generic. A deployment occurring near an incident is correlation, not proof of causation. Retrieved text may contain prompt injection, so it must be passed as quoted data with citations, not instructions.

### Alternatives and trade-offs
Keyword retrieval is simple and auditable but can miss paraphrases. Vector retrieval improves semantic recall but needs metadata filters, version handling, and grounding checks. Hybrid retrieval is preferred for the small corpus: deterministic filters plus lexical/semantic ranking, with exact source citations.

### Exercise and validation observations
Orientation started; knowledge check pending.

### Interview explanation
Telemetry tells us what happened in the incident; runbooks tell us how operators commonly respond; change retrieval tells us what changed. Retrieval can support investigation and next steps, but only time-bounded, provenance-linked telemetry and change observations should support incident claims.

### Sources
- [LangChain: Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [OWASP: LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

### My questions, corrections, and revision items
- Knowledge check pending: explain why a relevant runbook section cannot prove the current incident root cause.
### Module 11 retrieval-boundary knowledge check
The learner correctly distinguished runbook guidance from current-incident evidence, identified service/environment/version/status/validity metadata filters, kept deployment events separate from telemetry, and treated retrieved prompt-injection content as untrusted data subject to deterministic permissions and budgets.
### Module 11 citation-grounding check
The learner correctly explained that stable document/section identifiers provide auditable provenance, while similarity scores explain ranking rather than truth or applicability. They described the claim -> citation -> source section chain and preserved metadata/validity inspection.
### Module 11 retrieval contract implementation
Added `src/incidentlens/retrieval.py` with versioned provider-neutral `RunbookSection`, `RunbookCitation`, and `ChangeEvent` contracts. Runbook filtering enforces service, environment, active status, UTC-aware validity windows, and half-open temporal semantics before any ranking. Retrieval tests cover irrelevant, deprecated, expired, missing, and naive-time inputs.

Validation: focused retrieval tests passed 8 tests; full validation passed 138 tests with 1 live test skipped; Ruff checks passed. Ranking, corpus loading, Runbook Agent, Change Agent, and retrieval evaluation remain pending.
### Module 11 versioned corpus and retrieval implementation
Added `RunbookCorpus` with schema-version validation, unique document/section IDs, JSON loading, deterministic lexical ranking, bounded limits, metadata-first filtering, and exact `RunbookCitation` outputs. Retrieval scores explain ranking only; citations preserve source identity and content. Full validation passed 142 tests with 1 live test skipped; Ruff checks passed.
### Module 11 Runbook and Change Agent implementation
Added isolated read-only `RunbookAgent` and `ChangeAgent` interfaces with separate query contracts, allowed tools, and signal scopes. Runbook retrieval returns exact citations; Change retrieval returns bounded, UTC-windowed, deterministically ordered change events with stable change IDs. Full validation passed 145 tests with 1 live test skipped; Ruff checks passed.
### Module 11 adversarial retrieval validation
Added adversarial tests for irrelevant, contradictory, stale/expired, missing, and malicious runbook content. Contradictory sections remain separate citations; missing matches return no retrieval evidence; malicious text remains inert quoted data and does not expand Runbook Agent permissions. Full validation passed 149 tests with 1 live test skipped; Ruff checks passed.
### Module 11 retrieval evaluation implementation
Added retrieval-only `RetrievalMetrics`, citation identity keys, and deterministic evaluation for precision, recall, hit rate, and reciprocal rank. Evaluation compares retrieved runbook citations against labeled relevant section IDs and does not judge final diagnosis correctness. Full validation passed 153 tests with 1 live test skipped; Ruff checks passed.
### Module 11 change correlation validation
Added deterministic temporal change correlation with before/during incident relations, bounded pre-incident proximity, stable ordering, and an explicit `supports_causation=False` marker. Tests verify nearby versus distant deployments and invalid windows. Full validation passed 155 tests with 1 live test skipped; Ruff checks passed.
### Module 11 final review and completion
The learner correctly explained that similarity scores rank text but do not prove current incident facts, required deterministic metadata eligibility before ranking, preserved contradictory runbook sections, separated guidance from telemetry evidence, and treated deployment timing as correlation rather than causation. They correctly rejected malicious runbook instructions as authority while preserving them as auditable untrusted content. Module 11 completed with versioned runbook/change contracts, isolated agents, deterministic retrieval/evaluation, adversarial tests, and 155 passing tests with 1 live test skipped.
## Module 12 - Hypothesis formation, critique, and calibrated confidence

### Concept and why it exists
An incident investigation must generate plausible explanations without promoting them to facts. Module 12 separates candidate hypotheses, supporting and contradicting evidence, missing evidence, verification, abstention, and confidence calibration.

### Mental model and small example
A trace may show that checkout requests spend time in `payment-service`. A candidate hypothesis is: "payment-service degradation contributed to the latency." That is not yet a verified root cause. Verification must check counter-evidence, alternative explanations, evidence completeness, and causal gaps.

### Internal behavior
A hypothesis should identify its claim kind, supporting evidence IDs, contradicting evidence IDs, missing evidence, confidence, and limitations. A verifier receives structured findings and raw evidence references independently from the generator and can downgrade, reject, or mark a hypothesis `insufficient_evidence`.

### IncidentLens application
The existing report and specialist finding contracts already preserve evidence IDs and confidence. Module 12 adds a Hypothesis Agent and a distinct Verifier Agent with different context and instructions, bounded critique rounds, and explicit abstention.

### Boundaries, failure modes, and common mistakes
Multiple agents agreeing may reflect shared prompts, shared evidence, or the same anchoring error; agreement is not independent confirmation. A plausible unsupported cause, a missing signal, or a deceptive distractor must not receive high confidence merely because the explanation sounds coherent.

### Alternatives and trade-offs
Reflection can catch omissions but adds model calls and may amplify correlated errors. Debate can expose alternatives but can create false consensus. A bounded verifier with structured evidence checks is preferred over unconstrained persona debate.

### Exercise and validation observations
Orientation started; knowledge check pending.

### Interview explanation
A hypothesis is a proposed causal explanation; verification tests it against supporting, contradicting, and missing evidence. Confidence reflects evidence quality and coverage, not how many agents repeat the same claim. When evidence is insufficient, the system should abstain.

### Sources
- [AutoGen: Reflection](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/reflection.html)
- [AutoGen: Multi-agent debate](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/multi-agent-debate.html)
- [Reflexion paper](https://arxiv.org/abs/2303.11366)

### My questions, corrections, and revision items
- Knowledge check pending: explain why a high-confidence hypothesis can still be unsupported.
### Module 12 hypothesis and verification boundary check
The learner correctly distinguished supporting evidence from causal mechanism evidence, explained why verification must inspect structured claims and evidence references, separated weak/contradictory evidence from missing evidence, and explained why agent agreement is not independent confirmation when evidence overlaps.
### Module 12 abstention check
The learner correctly distinguished low confidence, where available evidence permits a weak evaluation, from `insufficient_evidence`, where required evidence is unavailable and the system must abstain rather than imply a weakly supported conclusion.
### Module 12 implementation evidence
- [x] Added structured `EvidenceTable` and `HypothesisCandidate` contracts with forbidden extra fields.
- [x] Enforced disjoint supporting and contradicting evidence IDs.
- [x] Enforced explicit missing evidence for `insufficient_evidence` hypotheses.
- [x] Added deterministic `VerificationResult` and `verify_hypothesis(...)` grounding behavior.
- [x] Unknown evidence IDs are rejected before verification classification.
- [x] Conflicting evidence downgrades a hypothesis to `low_confidence`.
- [x] Missing required signals produce `insufficient_evidence`, not a factual negative conclusion.
- [x] Focused validation: `python -m pytest tests\\test_hypotheses.py -q` -> 7 passed.
- [x] Full validation: `python -m pytest -q` -> 162 passed, 1 skipped; Ruff check and format check passed.
- [ ] Add a separate verifier-agent boundary and bounded critique rounds.
### Module 12 verifier boundary evidence
- [x] Added isolated `VerifierContext` containing only incident summary, candidate hypotheses, and collected evidence.
- [x] Forbidden unexpected context fields such as peer conclusions and hidden ground truth.
- [x] Added `VerifierAgent` with a deterministic maximum critique-round boundary.
- [x] Rejects unknown hypothesis IDs and out-of-scope evidence before review.
- [x] Focused validation: `python -m pytest tests\\test_hypotheses.py -q` -> 11 passed.
- [x] Full validation: `python -m pytest -q` -> 166 passed, 1 skipped; Ruff check and format check passed.
- [ ] Add model-backed critique behavior and final Module 12 conceptual review.
### Module 12 model-backed critique evidence
- [x] Added provider-neutral `ModelCritiqueProposal` for untrusted model output.
- [x] Added `VerifierAgent.review_with_model(...)` without leaking provider-specific APIs into the contract.
- [x] Deterministically validates proposal schema, hypothesis identity, cited evidence IDs, and critique-round budget before acceptance.
- [x] Deterministically derives final verification status; model text cannot promote unsupported evidence to a verified cause.
- [x] Tests cover conflicting model critique, unknown evidence, malformed boundary behavior, and no model call after round exhaustion.
- [x] Full validation: `python -m pytest -q` -> 169 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete final Module 12 conceptual review and deceptive-distractor exercise.
### Module 12 final review
The learner correctly explained that model confidence is not proof, that evidence IDs must be checked for relevance and causal sufficiency, and that shared evidence prevents agent agreement from being treated as independent confirmation. The deployment example was correctly classified as `insufficient_evidence`: D1 and M1 establish temporal ordering, while T1 localizes latency, but no evidence establishes a deployment-specific mechanism or rollback effect. The final wording preserved the unresolved causal gap without claiming the deployment was harmless.
## Module 13 — Human oversight, authorization, and safe actions

### Concept and why it exists
Module 13 begins with the distinction between authentication, authorization, and human approval. Authentication identifies the actor; authorization determines whether that identity may request or perform a capability; approval is explicit human consent for one exact proposed action. A UI prompt is not a server-side security boundary.

### IncidentLens application
IncidentLens remains read-only by default. A remediation-capable path will initially create a simulated action plan, bind approval to the incident, action, arguments, evidence references, policy version, approver, and expiry, then revalidate those fields before one execution.

### My questions, corrections, and revision items
- Explain why authentication alone does not authorize a rollback.
- Explain why changing action arguments invalidates an existing approval.
### Module 13 authentication, authorization, and approval check
The learner correctly explained that authentication proves identity but not permission, and that authorization must verify role, environment scope, and action authority. The learner also correctly explained that approval must bind to exact action arguments: changing a rollback target from v2.4 to v2.5 creates a new action requiring fresh approval.
### Module 13 action fingerprint check
The learner correctly explained that evidence references belong in the action fingerprint. Approval therefore binds the exact action, parameters, and supporting justification; changing evidence invalidates the prior approval even when action arguments are unchanged.
### Module 13 approval-contract implementation
- [x] Added `ActionPlan`, `Approval`, `AuditEvent`, and `ApprovalValidationError` contracts in `src/incidentlens/approval.py`.
- [x] Action fingerprints include incident, action type, target, arguments, evidence references, and policy version.
- [x] Rejected fingerprints cannot be reused; changed arguments or evidence require a new approval.
- [x] Validation covers authorization, expiry, action/fingerprint matching, and duplicate execution.
- [x] Focused validation: `python -m pytest tests\\test_approval.py -q` -> 9 passed.
- [x] Full validation: `python -m pytest -q` -> 178 passed, 1 skipped; Ruff check and format check passed.
- [ ] Add an approval interrupt/resume path and durable audit-event recording.
### Module 13 durable approval interrupt/resume
- [x] Added durable `ApprovalStore` records with `awaiting_approval`, `executing`, `executed`, and `failed` states.
- [x] Approval requests and execution are recorded as sanitized audit events.
- [x] Resume pauses without approval and reuses completed execution results.
- [x] Crash recovery at `executing` returns `indeterminate` and does not repeat the executor.
- [x] Rejected action fingerprints cannot be approved later.
- [x] Focused validation: `python -m pytest tests\\test_approval_store.py -q` -> 8 passed.
- [x] Full validation: `python -m pytest -q` -> 186 passed, 1 skipped; Ruff check and format check passed.
- [ ] Complete Module 13 final review and verify unauthorized/stale approval cases at the workflow boundary.
### Module 13 final review
The learner correctly explained why frontend approval is not a backend security control, why changed action arguments or evidence require a new fingerprint and approval, and why rejected fingerprints must remain blocked. The learner correctly distinguished approver authorization from approval of one exact action. For a crash after `executing`, the learner identified the external side effect as ambiguous and recommended reconciliation rather than blind retry; this matches the implementation's `indeterminate` recovery result.

### Module 14 telemetry error mapping implementation
Added shared `IncidentError` mapping to telemetry query errors. Timeout, rate-limit, service-unavailable, authorization, and unknown dependency classifications now map to stable IncidentLens error categories. Cross-incident fixture requests retain the existing `invalid_query` result semantics while carrying a terminal `incident_scope_violation` error. Validation observed 26 focused telemetry tests and 197 full-suite tests passing with one live test skipped; Ruff and formatting checks passed.

### Module 14 redaction and safe-error implementation
Added `sanitize_text` and `IncidentError.from_message` in `src/incidentlens/errors.py`. The boundary redacts common connection strings, secret/token/API-key/authorization assignments, and customer identifiers, and bounds user-facing error text to 500 characters. Telemetry mappings sanitize backend messages before constructing shared errors. Focused redaction, telemetry, and approval tests passed; full validation observed 199 passed and 1 skipped.

Known limitation: this is a deterministic error-text boundary, not a complete structured-payload redactor. Raw telemetry payloads and future diagnostic sinks need separate field-aware controls before production use.

### Module 14 field-aware redaction validation
Extended the redaction boundary with recursive `sanitize_structured` handling for nested mappings, lists, headers, customer identifiers, and diagnostic payloads. Added `sanitize_exception` coverage for chained causes and verified that audit-style payloads do not retain secret values. The sanitizer intentionally operates on diagnostic copies and does not mutate executable action plans or fingerprints.

Validation: focused redaction/audit tests passed 18 tests; full suite passed 202 tests with one live test skipped; Ruff and formatting checks passed.

### Module 14 adversarial validation
Existing retrieval and fixture-loader tests verify that prompt-injection text remains inert runbook data and hidden ground truth is excluded from agent-visible fixtures. Added retry-storm coverage showing 20 failing investigations are each bounded to two model attempts, for a deterministic maximum of 40 calls. Focused adversarial validation passed 55 tests; full validation passed 203 tests with one live test skipped.

### Module 14 circuit breaker and partial-backend recovery
Added `CircuitBreaker` with closed, open, and half-open states, injected-clock tests, fail-fast behavior, and recovery probes. Parallel investigation branches can receive dependency-specific breakers; an open metrics dependency returns a failed branch while logs and traces continue successfully. Focused reliability validation passed 12 tests; full validation passed 207 tests with one live test skipped.

Known limitation: breaker state is currently supplied per specialist branch. A coordinator-owned registry keyed by backend, tenant, and environment remains deferred.

### Module 14 coordinator-owned circuit-breaker registry
Replaced the per-branch limitation with `CircuitBreakerRegistry`, keyed by backend, tenant, and environment. Investigation tasks now carry tenant/environment scope, and parallel branches resolve shared dependency breakers through the coordinator registry. Tests verify same-scope sharing and tenant/environment isolation while healthy sibling branches continue during an open metrics circuit.

Validation: focused registry/parallel tests passed 36 tests; full suite passed 209 tests with one live test skipped; Ruff and formatting checks passed.

### Module 14 coverage-status propagation
Added deterministic coverage summarization at the parallel aggregation boundary. All successful branches preserve `completed`; mixed success and unavailable/failed branches downgrade the report to `inconclusive` with unavailable specialist names; no successful branches produce `failed`. The report summary records the evidence-coverage limitation rather than presenting a completed diagnosis as fully supported.

Validation: focused coverage/workflow tests passed 34 tests; full suite passed 211 tests with one live test skipped; Ruff and formatting checks passed.

### Module 14 main workflow coverage integration
Wired specialist branch results into `IncidentGraphState` and the LangGraph investigation/synthesis path. The synthesis boundary now applies deterministic coverage status before artifact persistence: mixed branch outcomes produce an `inconclusive` report, while no successful specialist produces a failed lifecycle with sanitized coverage context. Validation passed 213 tests with one live test skipped.

### Module 14 final review and completion
The final review established the central reliability invariant: an unavailable dependency is unknown evidence, not an empty successful query. The learner correctly assigned retry policy to the dependency/tool or model-adapter layer, global budgets and termination to the coordinator, and report acceptance to deterministic coverage/grounding validation. The learner also correctly explained that circuit-open Metrics evidence can yield a completed but explicitly inconclusive report when Logs and Traces support a valid limited result; workflow `FAILED` is reserved for inability to produce any valid report.

The debugging exercise identified the fan-in-to-synthesis defect: if Metrics `unavailable` is lost, synthesis can promote resource saturation to unsupported causation. The implemented coverage boundary now preserves healthy evidence, names unavailable branches, downgrades mixed coverage to `inconclusive`, and fails only when no specialist evidence remains. The failure-matrix exercise correctly separated model-provider failure, dependency timeout, scope violation, prompt injection, and stale approval ownership and continuation rules.

Validation: `python -m pytest -q` passed 213 tests with one skipped; Ruff check and format check passed. Remaining revision items are production coordinator wiring and a unified failure matrix across all dependency classes. Module 15 begins with evaluation dimensions, single-agent and deterministic baselines, ablations, and observability.

### Pre-Module 15 integration gap closure
The repository review found that several reliability boundaries were tested in isolation but were not carrying their structured outcomes through the next layer. The implementation now accepts a coordinator-supplied model-call budget at the agent-loop boundary, consumes one budget unit before every initial call or retry, and raises a sanitized `model_budget_exhausted` error before invocation when no budget remains. Retry delay jitter is injectable so tests and production policy can use bounded randomized delays without hiding the retry count.

Specialist branch results now preserve an `IncidentError` alongside the compatibility error string. Circuit-open and timeout outcomes therefore retain stable classification, retryability, component, correlation ID, and safe user messaging through fan-in. Role-specific recorded-fixture registries are also constructed from each specialist contract rather than relying on a broad shared registry.

The graph-facing `CoordinatorRuntime` now composes deterministic specialist tasks with bounded parallel fan-out/fan-in, validates the active incident scope, and supplies branch results to synthesis. Report acceptance also downgrades a completed report when a hypothesis explicitly carries unresolved evidence requirements, so the model cannot promote an admitted evidence gap to a completed causal conclusion.

The remaining coordinator seams are now concrete: tool budgets are consumed before tool execution, workflow failures retain a sanitized `IncidentError` in graph state, the model-backed specialist worker converts only evidence-linked hypotheses into scoped findings, and `list_changes` plus reproducible runbook/change fixtures are available as bounded capabilities. This completes the pre-evaluation composition work without claiming that evaluation metrics or product APIs already exist.

Checkpoint recovery now validates both state version and tool-contract version. Unsupported tool contracts are rejected before resume, and a sanitized recovery error states that no investigation actions executed. Added tests cover shared-budget refusal, scoped role registries, structured circuit-open metadata, and incompatible tool-contract rejection.

Validation available in the current environment: all edited Python files compiled successfully with `py_compile`; `git diff --check` passed. The full pytest/Ruff suite could not be rerun because the current shell has no Python packages installed; the prior recorded suite remains 213 passed, 1 skipped. The deterministic report acceptance boundary is now mandatory; Module 15 will compare this against model-backed verifier variants and measure the trade-offs.

## Module 15 — Evaluation, ablations, observability, and optimization

### Concept and why it exists
Agent systems should be evaluated by whether they satisfy the intended outcome contract, not only by whether they reproduce one expected sequence of tool calls. Exact-path evaluation is useful for diagnosing process failures, but it should not reject a valid investigation merely because it gathered equivalent evidence in a different order.

### IncidentLens application
IncidentLens needs both outcome/grounding evaluation and trajectory/process evaluation. Outcome evaluation checks diagnosis correctness, evidence grounding, contradiction handling, calibrated confidence, and abstention. Trajectory evaluation checks permitted tools, incident scope, budgets, loops, duplicate work, latency, and recovery behavior.

### Knowledge check
The learner correctly explained that different valid tool orders should not automatically fail when the final report is grounded and calibrated. The learner also correctly explained that a temporally correlated deployment claim must fail outcome/grounding verification even if the agent followed the expected tool sequence. This establishes the distinction between how the system worked and whether the result is valid.

### Sources
- [LangSmith evaluation types](https://docs.langchain.com/langsmith/evaluation-types)
- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)

### My questions, corrections, and revision items
- Preserve multiple valid investigation paths while enforcing deterministic safety and grounding invariants.

### Evaluation contract implementation
Added `src/incidentlens/evaluation.py` with evaluator-owned scenarios, agent-visible scenario projections, variant/split contracts, result and aggregate schemas, grounding checks, evidence precision/recall, root-cause matching, abstention checks, split validation, and a versioned dataset loader. Added `fixtures/evaluation/scenarios.json` with development and held-out scenarios. The loader projects evaluator fixtures through the existing agent-safe telemetry boundary. Added `tests/test_evaluation.py` for hidden-label exclusion, citation grounding, metric calculations, abstention, split selection, dataset uniqueness, and run-configuration consistency. Aggregate calculation and runtime variant execution remain the next increment.

### Agent/evaluator projection check
The learner correctly explained that `AgentScenarioView` creates a structural trust boundary around evaluator-only ground truth and makes leakage regression-testable. Important refinement: the boundary must also be enforced by fixture loaders and tool registries; hiding fields in a Pydantic projection is insufficient if an agent can still retrieve the evaluator-owned fixture source directly.
- Deterministic evaluators should enforce objective authorization, scope, citation, and budget invariants. A rubric-based judge may assess clarity and calibration, but only after deterministic grounding checks; human review calibrates whether judge scores match expert judgment.

### Evaluator contract exercise
The learner designed deterministic checks for citation existence, incident scope/provenance, unavailable-evidence propagation, completion invariants, and confidence/status consistency. They designed an LLM rubric covering causal support, evidence-gap handling, confidence calibration, alternatives, and claim wording. The expected result correctly downgraded the deployment-causation claim to `insufficient_evidence`/inconclusive while allowing lifecycle completion if the report explicitly communicated the limitation. The learner also correctly distinguished invalid citations from valid citations that do not establish causation.

Implementation note: deterministic missing-evidence checks require explicit report obligations or a policy mapping claim types to required evidence categories; they must not infer causal sufficiency from citation existence alone.

### Evaluation execution implementation
Added the first executable evaluation harness in `src/incidentlens/evaluation.py`. `evaluate_execution` scores one variant execution against evaluator-only labels, while `aggregate_results` calculates quality, efficiency, and recovery aggregates without exposing hidden labels to the agent. `run_variant_evaluation` selects one split, projects each scenario through `AgentScenarioView`, invokes a supplied variant runner, and returns versioned per-scenario and aggregate results.

The harness explicitly checks that a fixture's manifest incident ID matches the evaluation scenario ID. This prevents a mislabeled fixture from silently evaluating one incident under another scenario's ground truth. A held-out deterministic runner test demonstrates the execution path without claiming that the production workflow is already connected.

Validation in the current environment: all edited Python files compiled with `py_compile`, and `git diff --check` passed. Full pytest and Ruff execution remains unverified because their packages are unavailable in the current shell.

### Deterministic baseline and trajectory evaluator
Connected the fixture-backed deterministic baseline through `deterministic_variant_runner`. It reads only the `AgentScenarioView` fixture path, converts available telemetry into evidence, and derives a bounded heuristic hypothesis from observable signal content; it never reads `hidden_ground_truth`.

Added `TrajectoryTrace` and deterministic process checks for unauthorized tool requests, scope violations, and budget exhaustion. These are scored independently from grounded outcome metrics, so a valid report reached through a different permitted tool order can pass while an unsafe request fails even if the report looks correct. Aggregate results now include trajectory success, unauthorized-request count, and duplicate-call counts.

Validation: `py_compile` and `git diff --check` passed. `python -m pytest tests\\test_evaluation.py -q` was attempted but could not run because `pytest` is not installed in the active interpreter.

### Comparable variant runs and persistence
Added `EvaluationRunSet` and `EvaluationRunStore` so results from multiple variants can be compared only when they use the same split and cover the same scenario IDs. `run_variant_suite` accepts provider-neutral runner adapters, evaluates each variant with the same evaluator, and optionally persists the complete versioned run set atomically. This gives the deterministic baseline, single-agent baseline, full multi-agent system, and no-verifier ablation a common comparison boundary without forcing their implementations into the evaluator.

The adapter boundary is intentional: the evaluator owns scoring and comparability, while each workflow variant owns execution and supplies sanitized measurements. A run with different scenarios cannot be silently compared to another run.

### Named workflow variant adapters
Added `VariantRunnerAdapter` and `build_variant_adapters` to bind the deterministic baseline plus injected single-agent, full multi-agent, and no-verifier implementations to stable evaluator variant names. The adapter validates that each implementation returns the provider-neutral `VariantExecution` contract. This keeps orchestration-specific model calls outside the evaluator while making the four-way ablation wiring explicit and testable.

### Single-agent baseline adapter
Implemented `SingleAgentRunner` as the first concrete model-backed adapter. It creates an `IncidentInput` from `AgentScenarioView`, builds a registry from the projected fixture rather than the evaluator fixture, runs the existing bounded `run_agent_loop_with_metadata`, and records model/tool counts, latency, and requested tool names. The model client is injected, so tests can use a scripted model and production code can supply the configured provider adapter. Shared model/tool budgets remain injectable at this boundary.

### Full multi-agent runner adapter
Implemented `MultiAgentRunner` over `CoordinatorRuntime`. It deterministically builds Logs, Metrics, and Traces tasks from the agent-visible fixture, runs the injected specialist worker with bounded parallelism and deadlines, aggregates only validated findings, synthesizes an evidence-linked report, and applies branch coverage so dependency failures become `inconclusive` rather than empty evidence. The runner keeps worker/model construction injected; this makes the coordinator path testable without coupling the evaluator to a provider.

### No-verifier ablation runner
Added `MultiAgentWithoutVerifierRunner` as an explicit ablation. It shares task construction, specialist execution, fan-in, synthesis, coverage handling, and measurements with the multi-agent path, but deliberately has no verification step. This isolates the verifier's contribution: differences in unsupported claims or calibration can be compared while the investigation path remains otherwise constant.

### Variant comparison and persistence
Added `EvaluationComparison` and `compare_variant_runs`. The comparison requires both variants to be present in one validated `EvaluationRunSet`, then reports right-minus-left deltas for grounding, root-cause accuracy, unsupported claims, abstention, latency, model/tool calls, cost, and trajectory success. Persisting the aligned run set before comparing keeps the comparison reproducible and prevents mismatched scenario populations from producing misleading conclusions.

### Verifier wiring for the full multi-agent variant
Connected the existing deterministic `VerifierAgent` to `MultiAgentRunner`. Specialist findings are converted into verifier-owned `HypothesisCandidate` and `EvidenceTable` contracts; verification results then update report confidence, supporting/contradicting evidence, missing-evidence obligations, and report status. `MultiAgentWithoutVerifierRunner` explicitly disables this step while retaining the same specialist path. This makes the ablation boundary concrete: verifier impact is measured after identical fan-out/fan-in execution.

### Repeated development trials
Added `run_repeated_evaluation` and `aggregate_repeated_runs`. Each trial calls a runner factory so model/agent state is fresh, evaluates the same split, persists a unique run-set ID, and summarizes mean and population standard deviation for quality, efficiency, recovery, and trajectory metrics. The helper can be used on development scenarios during tuning; held-out scenarios remain a separate final evaluation population.

### Frozen held-out evaluation
Added `run_held_out_evaluation`, which hard-codes the `held_out` split and runs the frozen configuration once through the same persistence boundary. The held-out regression test confirms that only `db-exhaustion-001` is evaluated. This prevents a caller from accidentally treating development scenarios as final generalization evidence or repeatedly tuning against the held-out case.

Execution note: the active interpreter could not execute the held-out run because `langgraph` is not installed; `pytest` is also unavailable. No held-out metric is claimed until the dependency-enabled command completes.

Held-out execution was subsequently run with the configured dependency-enabled interpreter through `scripts/run_held_out_evaluation.py`. The run evaluated only `db-exhaustion-001` and persisted `artifacts/evaluation/held-out-final.json`. The deterministic variant produced grounded rate 1.0, root-cause accuracy 1.0, unsupported-claim rate 0.0, abstention quality 1.0, trajectory success 1.0, and recovery rate 1.0. Because this is one scenario and one deterministic variant, it does not establish broad system or multi-agent generalization.

### Evaluation failure review
The first dependency-enabled run reported 11 failures and 14 passes. The failures identified contract mismatches rather than one systemic runner failure: evaluator leakage must be checked structurally, report `Evidence` uses `source` rather than telemetry `signal_type`, malformed fixtures fail before identity checks, and missing signal branches correctly produce `inconclusive` coverage. These fixes were applied and the follow-up dependency-enabled run passed 25 evaluation tests.

### Dataset leakage and held-out evaluation check
The learner correctly explained that repeatedly tuning prompts against all five visible scenarios turns them into development data and can overfit the benchmark. They correctly identified the sixth untouched scenario as evidence of generalization rather than memorization of known failures. The learner also preserved the boundary between agent-visible scenario projections and evaluator-only hidden ground truth.

### Baselines and ablations exercise
The learner designed a four-variant comparison covering deterministic workflow, single-agent baseline, full multi-agent system, and multi-agent without verifier. The matrix tests architecture hypotheses rather than assuming multi-agent superiority. It correctly identifies the full-system versus no-verifier comparison as the key verifier ablation and pairs quality measures such as grounded diagnosis, unsupported claims, and abstention with latency, calls, tokens, cost, and recovery metrics.

### Module 15 final conceptual review
The learner correctly explained that one passing held-out scenario supports only a narrow generalization claim for the tested variant, not broad IncidentLens or multi-agent generalization. They correctly described a verifier benefit as a controlled, repeated ablation result with the quality improvement reported alongside latency, calls, tokens, and cost trade-offs. They explained why means must be paired with variability such as standard deviation for non-deterministic agents.

For the causal-language review, the learner correctly separated deterministic citation/provenance validation from semantic calibration: valid deployment evidence can still support only temporal correlation, so the causal claim must be downgraded. In the failure-analysis exercise, they correctly classified a valid report with unavailable Metrics and an explicitly unverified saturation hypothesis as lifecycle `COMPLETED` with diagnostic `insufficient_evidence`, not as a grounding failure or unsupported claim. They correctly required the report to state that Metrics were unavailable because the circuit was open.

Remaining Module 15 evidence: manually compare a sample with automated scores and record judge-calibration limitations. The frozen held-out artifact is now preserved.

### Human/judge calibration contract
Added `HumanReview`, `JudgeCalibrationResult`, and `calibrate_judge`. The contract records a blinded human judgment beside an automated qualitative judgment and reports agreement plus explicit disagreement IDs. This supports calibration without promoting an LLM judge—or a single reviewer—to ground-truth authority. A real review sample still needs to be collected and documented after the frozen held-out run.

The human review artifact at `artifacts/evaluation/human_reviews.json` is now complete. Reviewer `reviewer-001` judged the deterministic diagnosis `supported`, agreeing with the automated judgment. Calibration produced 1/1 agreement (100%) with zero disagreements. This is still a one-sample calibration result and should not be generalized to all scenarios or judges.

### Full-suite regression review
The full suite exposed a compatibility gap: older evidence-only fixtures were still used by specialist registry tests after the evaluator loader became schema-specific. `load_agent_fixture` now adapts those legacy fixtures only at the safe agent boundary; `load_evaluator_fixture` remains strict and continues to require evaluator manifests and hidden-label separation. The report acceptance wording also preserves the established unresolved-evidence message contract.

Validation: the dependency-enabled full test suite was rerun after these fixes and passed. Combined with the 25 focused evaluation tests, the evaluator and existing repository regression suite are green.

### Development comparison entry point
Added `scripts/run_development_comparison.py`. It constructs fresh Gemini-backed single-agent, full multi-agent, and no-verifier adapters for each trial, keeps the deterministic baseline in the same run set, runs only the development split, aggregates repeated-trial variability, and persists each run set under `artifacts/evaluation/`. It requires the configured `INCIDENTLENS_GOOGLE_API_KEY`; no live model result is claimed until the script is executed with that configuration.

### Offline reproducibility comparison
Added the `--offline` mode to the same entry point. It uses `OfflineEvaluationModel`, which reads only the safe agent fixture projection and returns deterministic structured reports. This separates evaluator and coordinator plumbing from Gemini quota, network, and provider variance.

The three-trial offline run completed all four variants successfully. Deterministic, single-agent, full multi-agent, and no-verifier variants all achieved grounded rate, root-cause accuracy, abstention quality, recovery, and trajectory success of 1.0 on the two development scenarios. The verifier ablation therefore showed no difference in this scripted run: unsupported-claim rate was 0.0 for both variants. Full multi-agent used three model calls per scenario on average; the scripted model made no tool calls, so this is a reproducibility/plumbing result, not evidence that the real Gemini verifier improves diagnosis quality.

The live Gemini comparison remains a separate failure record: quota exhaustion caused multi-agent recovery to remain 0.0 across three trials and single-agent recovery to be 0.33. Those runs must not be interpreted as architecture-quality evidence. A valid live comparison requires healthy branch completion and should report quality and provider recovery separately.

### Module 15 final completion review
The learner correctly explained that tool order is a trajectory property while grounded causal support is an outcome invariant. They distinguished offline evaluation-pipeline evidence from live Gemini generalization, explained why failed executions must not count as vacuously grounded, and described a controlled verifier ablation with repeated held-out trials and quality/cost trade-offs.

In the final failure-analysis exercise, the learner correctly classified Metrics circuit-open plus Logs/Traces success as lifecycle `COMPLETED` with diagnostic `insufficient_evidence`. They separated deterministic citation and availability checks from LLM semantic causal evaluation. Their proposed invariant rejects a supported or high-confidence hypothesis only when `requires_metrics=true` and Metrics is unavailable, preserving valid completed-but-inconclusive reports.

Module 15 remains implementation-incomplete because a real rubric-based LLM judge comparison and explicit token/cost estimation are not yet implemented; the offline scripted comparison is intentionally only a reproducibility and plumbing result.
### Module 15 completion review
Module 15 is complete for the reproducible evaluation scope. The evaluator separates deterministic citation and trajectory checks from semantic judgment, keeps evaluator-only ground truth outside `AgentScenarioView`, and treats failed model executions as recovery failures rather than vacuously grounded reports. The held-out artifact remains limited evidence: one scenario cannot establish broad generalization.

The five-review calibration artifact records 5/5 agreement between automated judgments and independent human judgments. The three-trial offline verifier ablation produced equivalent results for the scripted workload, so it demonstrates comparable plumbing rather than verifier benefit. Token measurements now propagate through variant execution, specialist branches, evaluation results, and aggregate artifacts. Live Gemini failures remain a provider-health limitation and are not used to claim architecture quality.

The exact reproducible checks are `python .\\scripts\\report_module15.py`, `python -m py_compile ...`, `python -m pytest -q`, `python -m ruff check .`, and `python -m ruff format --check .`. The first command reports calibration; the remaining dependency-enabled checks must be run in the project environment when available.

### Module 16 entry point
Module 16 begins at the application boundary: define the investigation job lifecycle and expose create, status, report, approve, and cancel operations without weakening the existing authorization, checkpoint, evidence, and report-validation boundaries.
