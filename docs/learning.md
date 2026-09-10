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