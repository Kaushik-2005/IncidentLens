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
