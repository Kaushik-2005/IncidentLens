# IncidentLens — Multi-Agent Systems Learning Roadmap

## Purpose

This roadmap teaches how to design, build, test, evaluate, and explain a production-oriented multi-agent system. The project is **IncidentLens**, a multi-agent incident investigation assistant that analyzes logs, metrics, traces, deployment events, and runbooks to produce evidence-backed root-cause hypotheses.

The goal is not to maximize the number of agents. The goal is to learn when multiple agents improve context isolation, parallel investigation, tool selection, and verification—and when a deterministic workflow or one agent is better.

This is a module-based curriculum. A module can take multiple sessions. Progress is based on demonstrated understanding and working evidence, not time spent.

## Final project outcome

Given an incident such as “checkout failures rose after a deployment,” IncidentLens will:

1. Create a bounded investigation plan.
2. Route work to specialized telemetry agents.
3. Run independent investigations concurrently where appropriate.
4. Preserve each agent's evidence without flooding every context.
5. Form and challenge root-cause hypotheses.
6. Ask for human approval before any simulated remediation.
7. Produce a structured incident report with confidence and evidence references.
8. Resume interrupted investigations safely.
9. Expose traces, latency, token use, cost estimates, and evaluation results.
10. Demonstrate measurable value over a single-agent baseline.

## Chosen stack

- Python 3.12+
- Gemini API through the maintained Google/LangChain integration
- LangChain for models, prompts, tools, retrieval, and structured outputs
- LangGraph for explicit state, routing, parallel branches, persistence, and interrupts
- Pydantic for state and message contracts
- FastAPI for the application API
- OpenTelemetry Demo as the live telemetry source
- Recorded JSON/JSONL or SQLite incident fixtures for fast local development
- Prometheus-compatible metrics, OpenSearch-compatible logs, and Jaeger-compatible traces
- PostgreSQL-backed LangGraph checkpoints for the production-oriented stage; in-memory or SQLite persistence during early development
- LangSmith and/or OpenTelemetry for agent execution traces
- pytest, Ruff, and mypy or Pyright for validation
- Docker Compose for the final local demonstration

Exact package versions and the Gemini model name must be selected from supported versions when implementation begins. Keep the model configurable; do not embed a model name or API key in source code.

## Scope boundaries

### Core scope

- Read-only incident investigation
- Synthetic or public telemetry only
- One coordinator and multiple genuinely specialized agents
- Structured, evidence-linked inter-agent outputs
- Deterministic safeguards around agentic decisions
- Single-agent baseline, multi-agent evaluation, and ablation studies
- Local deployment and reproducible demonstration

### Out of scope for the core project

- Automatic production remediation
- Access to employer or confidential telemetry
- A fully distributed agent runtime
- Kubernetes as a prerequisite
- Training or fine-tuning a foundation model
- Building a full observability backend from scratch
- Claiming autonomous SRE capability from a limited synthetic evaluation

## System vocabulary

- **Environment:** The incident data, telemetry backends, runbooks, deployments, and user input the system can observe or affect.
- **Agent:** A model-driven component with a bounded role, private context, permitted tools, output contract, and stopping conditions.
- **Workflow:** Code-defined control flow. Some nodes can be deterministic and some agentic.
- **Tool:** A typed capability through which an agent reads data or proposes an action.
- **Coordinator:** The component that decomposes work, delegates tasks, tracks budgets, and synthesizes results.
- **Artifact:** A durable structured result, such as a query result or investigation report, referenced by ID instead of repeatedly copied through prompts.
- **Ground truth:** Hidden scenario metadata used only for evaluation.

## Learning and completion method

For every module:

1. Learn the concepts and their trade-offs.
2. Answer a focused knowledge check.
3. Attempt a small exercise before receiving a full solution unless explicitly requested.
4. Build one coherent IncidentLens increment.
5. Run relevant validation and record actual results.
6. Update `docs/learning.md`, `docs/design.md`, and `docs/tracker.md`.

Implementation and understanding are separate. Existing code, a passing test, or Codex-generated work does not by itself prove understanding.

---

## Module 1 — Multi-agent foundations and project contract

### Learn

- Agent, environment, observation, action, policy, state, autonomy, and feedback loops
- Workflow versus agent; deterministic orchestration versus model-directed decisions
- Single-agent, multi-agent, and ordinary software pipelines
- Centralized versus decentralized coordination
- Cooperative versus competitive agents
- Why multi-agent systems help: context isolation, specialization, parallelism, and independently maintained capabilities
- Why they fail: duplicated work, coordination overhead, error propagation, shared-context confusion, non-termination, latency, and token cost
- Criteria for deciding that a component deserves to be an agent

### Build

- Write the IncidentLens problem statement, actors, inputs, outputs, constraints, and non-goals.
- Define the initial incident lifecycle: `created -> investigating -> awaiting_review -> completed | failed | cancelled`.
- Draw the proposed system boundary while labeling every component as planned.
- Write three representative incident narratives and the expected investigation outcome.

### Evidence and completion gate

- Explain why IncidentLens may benefit from multiple agents.
- Identify at least two parts that should remain deterministic.
- Explain one case where a single agent should be used instead.
- Project contract and initial design are recorded without claiming implementation.

### Sources

- [LangChain: Multi-agent systems](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [Anthropic: Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [AutoGen: Agent and multi-agent applications](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/core-concepts/agent-and-multi-agent-application.html)

---

## Module 2 — Gemini agent loop and single-agent baseline

### Learn

- The agent loop: model inference, tool request, tool execution, observation, and termination
- Gemini function calling and structured output
- Tool schemas, argument validation, result validation, and model/tool responsibility boundaries
- System instructions, role prompts, tool descriptions, and context construction
- Why application code—not the model—executes tools and enforces permissions
- Sampling, model variability, rate limits, retries, and secret handling

### Build

- Create the Python project structure and configuration boundary.
- Integrate the Gemini API through a configurable model adapter.
- Implement one harmless tool and a minimal tool-calling loop.
- Define Pydantic contracts for `IncidentInput`, `Evidence`, `Hypothesis`, and `InvestigationReport`.
- Create a **single-agent IncidentLens baseline** that operates on one small recorded incident fixture.

### Validate

- Unit-test tool argument and result validation.
- Test malformed model output, unknown tool requests, tool exceptions, and maximum-step termination.
- Save baseline output, latency, model calls, and token usage when available.

### Evidence and completion gate

- Trace one complete agent loop in your own words.
- Explain why structured output does not guarantee factual correctness.
- Baseline handles one happy path and fails safely on invalid tool use.

### Sources

- [Gemini API: Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Gemini API: Structured outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [LangChain: Tools](https://docs.langchain.com/oss/python/langchain/tools)

---

## Module 3 — Incident-response domain and realistic telemetry

### Learn

- Logs, metrics, traces, spans, resources, attributes, events, and context propagation
- RED and USE-style operational signals
- Correlation IDs, trace IDs, timestamps, clock skew, aggregation windows, and cardinality
- Symptoms versus contributing factors versus root cause
- Baselines, anomalies, cascading failures, partial failures, and recovery windows
- Synthetic telemetry, reproducibility, provenance, and hidden ground truth

### Build

- Define a versioned telemetry-neutral internal schema.
- Create an incident manifest format containing load profile, fault injection, timeline, affected services, expected evidence, distractors, and hidden ground truth.
- Add at least three recorded fixtures: payment failure, service latency, and resource exhaustion or memory growth.
- Create a fixture loader that prevents ground truth from entering agent-visible context.
- Document the later OpenTelemetry Demo integration and its resource requirements.

### Validate

- Verify trace-log correlation and timestamp normalization in fixtures.
- Test malformed records, missing signals, out-of-order events, and empty query windows.
- Confirm that agents cannot access the ground-truth directory through any tool.

### Evidence and completion gate

- Diagnose a small fixture manually before asking an agent to diagnose it.
- Explain what each telemetry signal can and cannot prove.
- Demonstrate ground-truth separation with a test.

### Sources

- [OpenTelemetry: Observability primer](https://opentelemetry.io/docs/concepts/observability-primer/)
- [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/)
- [OpenTelemetry Demo feature flags](https://opentelemetry.io/docs/demo/feature-flags/)
- [OpenTelemetry Demo load generator](https://opentelemetry.io/docs/demo/services/load-generator/)

---

## Module 4 — Tool engineering and the observation boundary

### Learn

- Tools as capability and security boundaries
- Narrow, typed tools versus one broad `do_everything` tool
- Resource-oriented interfaces, pagination, filtering, time bounds, and result limits
- Tool error taxonomy: invalid request, unavailable dependency, timeout, partial result, and authorization failure
- Idempotent reads, side effects, provenance, citations, and untrusted tool output
- When deterministic preprocessing should compress telemetry before an LLM sees it

### Build

- Implement read-only tools such as `search_logs`, `query_metrics`, `search_traces`, `get_trace`, and `list_changes` over recorded fixtures.
- Return bounded structured results with source IDs, query parameters, time range, truncation status, and errors.
- Add a tool registry with explicit per-agent allowlists.
- Add deterministic helpers for time-series summaries and trace critical-path extraction.

### Validate

- Test schema validation, time-range limits, pagination, injection-like input, oversized results, and dependency errors.
- Confirm that a tool cannot read outside its allowed incident scope.

### Evidence and completion gate

- Explain why telemetry data is an observation, not automatically trustworthy evidence.
- Demonstrate bounded outputs and agent-specific tool permissions.

### Sources

- [Gemini API: Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Model Context Protocol: Architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [OWASP: LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

---

## Module 5 — LangGraph state and deterministic orchestration

### Learn

- Graph state, nodes, edges, reducers, conditional routing, commands, and subgraphs
- State machines and explicit lifecycle transitions
- Shared state versus private agent context
- Deterministic control flow around probabilistic model calls
- State invariants, schema evolution, and avoiding unbounded message history

### Build

- Represent the incident lifecycle as a LangGraph state graph.
- Add deterministic validation, triage, investigation, and report nodes around the baseline agent.
- Keep raw telemetry outside graph messages; store references and bounded summaries.
- Add explicit failure and cancellation states.

### Validate

- Test every legal and illegal state transition.
- Verify maximum-step and terminal-state behavior.
- Inspect a graph execution and reconcile it with the documented design.

### Evidence and completion gate

- Explain graph state ownership and why chat history is not an adequate application database.
- Demonstrate deterministic rejection of an invalid transition.

### Sources

- [LangGraph: Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph: Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

---

## Module 6 — Specialization and context engineering

### Learn

- Role specialization versus arbitrary personas
- Context engineering: what each agent sees, does not see, and may retrieve
- Private scratch state, shared evidence, least context, and context contamination
- Prompt and tool ownership
- Capability overlap, duplicated investigation, and responsibility gaps
- Agent identity and lifecycle

### Build

- Extract three specialists from the baseline: Logs Agent, Metrics Agent, and Traces Agent.
- Give each agent a role contract containing objective, allowed tools, input schema, output schema, budget, and stopping rule.
- Store prompts as versioned configuration.
- Require all findings to cite evidence IDs and distinguish observation from inference.

### Validate

- Test that every agent is blocked from unapproved tools.
- Compare relevant-context size with the single-agent baseline.
- Run role-confusion and missing-evidence cases.

### Evidence and completion gate

- Justify each agent boundary using different tools, context, or reasoning responsibility.
- Remove or merge any agent that lacks a defensible boundary.

### Sources

- [LangChain: Multi-agent systems and context engineering](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [AutoGen: Agent identity and lifecycle](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/core-concepts/agent-identity-and-lifecycle.html)

---

## Module 7 — Coordination topologies and protocol design

### Learn

- Supervisor/subagents, router, handoff, sequential pipeline, group chat, blackboard, and custom workflow patterns
- Centralized orchestration versus decentralized peer coordination
- Message passing, shared-state coordination, and artifact references
- Task envelopes: objective, scope, inputs, tools, expected output, deadline, and budget
- Delegation quality, overlap detection, conflict resolution, and escalation
- Awareness of agent-to-agent protocols without prematurely distributing the runtime

### Build

- Implement small pattern labs for router, handoff, and supervisor-worker coordination.
- Record a decision matrix comparing patterns for IncidentLens.
- Select the initial production topology; default candidate: centralized coordinator with parallel specialist workers and deterministic aggregation.
- Define versioned inter-agent message contracts.

### Validate

- Use the same incident to compare correctness, calls, tokens, latency, duplicated work, and failure behavior across patterns.
- Test invalid, stale, duplicated, and incompatible messages.

### Evidence and completion gate

- Explain why IncidentLens selects one topology and rejects alternatives for its core flow.
- Demonstrate that agents interact through explicit contracts rather than arbitrary shared conversation history.

### Sources

- [LangChain: Multi-agent patterns](https://docs.langchain.com/oss/python/langchain/multi-agent)
- [AutoGen: Multi-agent design patterns](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/intro.html)
- [Google A2A Protocol](https://a2a-protocol.org/latest/)

---

## Module 8 — Parallel investigation and evidence aggregation

### Learn

- Sequential versus concurrent execution
- Fan-out/fan-in, map-reduce, barriers, stragglers, cancellation, and backpressure
- Async I/O versus threads/processes
- Shared-state race conditions and reducer semantics
- Result ordering, duplicate completion, partial success, and bounded concurrency
- Aggregation without losing provenance or minority evidence

### Build

- Run Logs, Metrics, and Traces agents concurrently.
- Add per-agent deadlines, a global concurrency limit, and an investigation deadline.
- Aggregate structured findings deterministically before model synthesis.
- Preserve partial results when one specialist times out.

### Validate

- Compare sequential and concurrent latency using the same scenario.
- Inject a slow, failed, and duplicated worker result.
- Verify deterministic aggregation and stable evidence references.

### Evidence and completion gate

- Explain what parallelism improves and what new failure modes it creates.
- Demonstrate a useful partial report when one agent is unavailable.

### Sources

- [LangGraph: Use the graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
- [AutoGen: Concurrent agents](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/concurrent-agents.html)

---

## Module 9 — Memory, persistence, checkpoints, and artifacts

### Learn

- Working state, conversation memory, episodic memory, semantic memory, and durable application data
- Thread-scoped checkpoints versus cross-thread stores
- Memory retrieval, retention, invalidation, provenance, privacy, and poisoning
- Checkpoint/replay semantics and resumable execution
- Artifact storage to avoid lossy “game of telephone” summaries
- State versioning and compatibility with in-flight runs

### Build

- Add LangGraph checkpointing with stable investigation IDs.
- Store evidence and reports as durable artifacts referenced from graph state.
- Resume an interrupted investigation without repeating completed tool work unnecessarily.
- Add retention and size limits; do not build free-form self-modifying memory.

### Validate

- Restart mid-investigation and resume from a checkpoint.
- Test stale artifact references, corrupted checkpoints, duplicate resumes, and incompatible state versions.

### Evidence and completion gate

- Explain the difference between graph state, a checkpoint, an artifact, and long-term memory.
- Demonstrate truthful recovery after interruption.

### Sources

- [LangGraph: Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph: Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)

---

## Module 10 — Planning, adaptive routing, budgets, and termination

### Learn

- Static decomposition versus model-generated plans
- Breadth-first versus depth-first investigation
- Replanning based on evidence gaps
- Rule-based, model-based, and hybrid routing
- Termination conditions, evidence sufficiency, recursion limits, loop detection, and diminishing returns
- Per-agent and global budgets for time, steps, tools, tokens, and cost

### Build

- Add a Coordinator that emits structured task envelopes.
- Scale investigation effort according to incident complexity.
- Allow one bounded follow-up round when evidence is insufficient.
- Add deterministic termination and budget enforcement outside the model.

### Validate

- Test under-delegation, duplicate tasks, excessive fan-out, circular delegation, and impossible evidence requests.
- Confirm that budget exhaustion produces a partial, uncertainty-aware report.

### Evidence and completion gate

- Explain who owns planning, execution, and termination.
- Demonstrate that a simple incident does not spawn every agent.

### Sources

- [Anthropic: How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [LangGraph: Multi-agent workflows](https://docs.langchain.com/oss/python/langchain/multi-agent)

---

## Module 11 — Runbook RAG and change intelligence

### Learn

- Retrieval versus memory versus tool calls
- Chunking, metadata, hybrid retrieval, reranking, filters, and citation grounding
- Query rewriting and multi-hop retrieval
- Versioned operational knowledge and stale-runbook risk
- Deployment/change correlation versus causation
- Retrieval evaluation: recall, precision, relevance, faithfulness, and answer correctness

### Build

- Add a Runbook Agent with a small versioned corpus.
- Add a Change Agent that analyzes deployment and configuration events.
- Use deterministic metadata filters for service, version, and validity window.
- Require citations to exact runbook sections and change-event IDs.

### Validate

- Test irrelevant, contradictory, stale, missing, and malicious runbook content.
- Evaluate retrieval separately from final diagnosis generation.

### Evidence and completion gate

- Explain why semantic similarity alone is not evidence of root cause.
- Demonstrate a report that distinguishes telemetry evidence from runbook guidance.

### Sources

- [LangChain: Retrieval](https://docs.langchain.com/oss/python/langchain/retrieval)
- [OWASP: LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

---

## Module 12 — Hypothesis formation, critique, and calibrated confidence

### Learn

- Hypothesis generation, evidence tables, alternative explanations, and falsification
- Reflection, critic/reviewer loops, debate, voting, consensus, and judge agents
- Correlated agent errors and why agreement is not independent confirmation
- Evidence coverage, contradiction handling, abstention, and calibrated uncertainty
- When critique adds value and when it adds only cost

### Build

- Add a Hypothesis Agent that ranks candidate causes.
- Add a Verifier Agent with different context and instructions from the hypothesis generator.
- Require supporting, contradicting, and missing evidence for every hypothesis.
- Limit critique to a fixed number of rounds and allow `insufficient_evidence`.

### Validate

- Test plausible but unsupported causes, conflicting agents, missing signals, and deceptive distractors.
- Compare diagnosis quality with and without the verifier.

### Evidence and completion gate

- Explain why multiple agents agreeing does not automatically increase confidence.
- Demonstrate at least one case where verification corrects the initial hypothesis.

### Sources

- [AutoGen: Reflection](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/reflection.html)
- [AutoGen: Multi-agent debate](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/multi-agent-debate.html)
- [Reflexion paper](https://arxiv.org/abs/2303.11366)

---

## Module 13 — Human oversight, authorization, and safe actions

### Learn

- Human-in-the-loop review, approval, edit, rejection, and escalation
- Authentication versus authorization versus human approval
- Read, propose, approve, and execute capability separation
- Least privilege, capability allowlists, audit trails, and separation of duties
- Interrupt/resume behavior and repeated side effects
- Reversible versus irreversible remediation

### Build

- Add an approval interrupt before any simulated remediation.
- Keep IncidentLens read-only by default; remediation tools initially generate plans only.
- Bind approval to the exact incident, action, arguments, evidence, and version.
- Record approval, rejection, edit, expiration, and actor identity in an audit event.

### Validate

- Test stale approval, changed arguments after approval, duplicate resume, rejection, and unauthorized approval.
- Verify that resuming a node cannot repeat a side effect.

### Evidence and completion gate

- Explain why a host approval prompt cannot replace server-side authorization.
- Demonstrate that no simulated action executes without valid bound approval.

### Sources

- [LangGraph: Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [OWASP: Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)

---

## Module 14 — Reliability, security, and adversarial behavior

### Learn

- Agent failure propagation and graceful degradation
- Timeouts as uncertain outcomes; bounded retries with backoff and jitter
- Retry ownership, idempotency, deduplication, circuit breakers, and bulkheads
- Prompt injection through telemetry and runbooks
- Tool-result poisoning, confused deputy problems, data exfiltration, excessive agency, and denial-of-wallet attacks
- Secret management, sensitive-data redaction, tenant/incident isolation, and safe logging
- Versioned prompts, tools, state, and deployment compatibility

### Build

- Add timeout, retry, circuit-breaker, and concurrency policies around model and telemetry dependencies.
- Add incident-scoped authorization to every tool.
- Treat telemetry and retrieved text as untrusted data, not instructions.
- Add redaction, safe audit logging, and configurable global cost limits.
- Create a failure matrix mapping failures to owner, retry policy, fallback, and user-visible status.

### Validate

- Inject model rate limits, backend timeouts, malformed output, prompt injection, cross-incident access, retry storms, and partial backend outages.
- Verify safe degradation and no secret or hidden ground-truth leakage.

### Evidence and completion gate

- Threat-model the complete data and control flow.
- Demonstrate at least three controlled failure recoveries and two blocked adversarial cases.

### Sources

- [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)
- [OWASP: Agentic AI Threats and Mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/)
- [OpenTelemetry: Handling sensitive data](https://opentelemetry.io/docs/security/handling-sensitive-data/)

---

## Module 15 — Evaluation, ablations, observability, and optimization

### Learn

- Outcome evaluation versus exact-path evaluation
- Deterministic checks, reference answers, rubric-based LLM judges, and human review
- Judge bias, leakage, non-determinism, and evaluator calibration
- Component, trajectory, and end-state evaluation
- Baselines, regression suites, ablation studies, confidence intervals, and repeated runs
- Agent observability: traces, model calls, tool calls, handoffs, errors, latency, tokens, cost, and decision patterns
- Quality/latency/cost trade-offs and evidence-driven optimization

### Build

- Create a versioned evaluation set with train/development and held-out scenarios.
- Compare deterministic workflow, single-agent baseline, multi-agent system, and multi-agent-without-verifier variants.
- Measure root-cause accuracy, evidence precision/recall, report completeness, abstention quality, tool efficiency, latency, token use, estimated cost, and failure recovery.
- Instrument the agent graph and generate a reproducible evaluation report.
- Optimize one measured bottleneck without weakening correctness or safety.

### Validate

- Run repeated trials for non-deterministic configurations.
- Manually review a sample and compare human judgments with automated scores.
- Verify evaluators cannot access hidden labels during system execution.

### Evidence and completion gate

- Present evidence showing where the multi-agent design helps, hurts, or makes no meaningful difference.
- Do not claim superiority if the evaluation does not support it.
- Record limitations, dataset size, model/configuration, and reproducibility details.

### Sources

- [LangSmith: Evaluation](https://docs.langchain.com/langsmith/evaluation)
- [Anthropic: Multi-agent evaluation lessons](https://www.anthropic.com/engineering/multi-agent-research-system)
- [OpenTelemetry: Generative AI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)

---

## Module 16 — Productization, live telemetry, and resume-grade capstone

### Learn

- API boundaries, asynchronous long-running jobs, streaming progress, cancellation, and status polling
- Configuration, schema versioning, health/readiness checks, and graceful shutdown
- Local persistence, migrations, concurrency limits, and resource ownership
- Containerization, deployment compatibility, and reproducible demos
- Operational runbooks, limitations, and truthful production-readiness claims
- Explaining architecture, trade-offs, evaluation, failures, and personal contribution in interviews

### Build

- Expose investigation create/status/report/approve/cancel endpoints through FastAPI.
- Add a minimal UI or CLI showing the incident timeline, agent progress, evidence, hypotheses, and final report.
- Integrate the OpenTelemetry Demo in minimal mode and generate at least one live scenario using its load generator and failure flags.
- Preserve recorded-fixture mode for fast demonstrations and CI.
- Containerize IncidentLens and document one-command local startup.
- Produce an architecture diagram, demo script, evaluation summary, limitations, and resume bullets grounded in measured results.

### Validate

- Run formatting, type, unit, integration, security, and end-to-end checks.
- Run a clean-environment setup and an interrupted-investigation recovery test.
- Demonstrate one correct diagnosis, one partial-backend failure, one abstention, and one rejected remediation.
- Reconcile code, tracker, learning notes, design history, diagrams, and measured claims.

### Evidence and completion gate

- Explain the system end to end without relying on generated notes.
- Defend why each agent exists and what would happen if it were removed.
- Show measured comparison with the single-agent baseline.
- State limitations and what would change for real production telemetry.

### Sources

- [OpenTelemetry Demo: Docker deployment](https://opentelemetry.io/docs/demo/docker-deployment/)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [LangGraph: Application structure](https://docs.langchain.com/oss/python/langgraph/application-structure)

---

## Optional advanced extensions

These do not block completion of the core roadmap:

- Replace fixture tools with an MCP telemetry server and compare direct tool binding with MCP.
- Experiment with Google ADK or AutoGen and compare runtime abstractions with LangGraph.
- Use an A2A-compatible boundary for a remotely hosted specialist while retaining server-side authorization.
- Add dynamic model routing between a faster and a stronger Gemini model.
- Add queue-backed distributed workers and study delivery, leases, idempotency, and backpressure.
- Add chaos testing against Kubernetes only after the Docker Compose system is stable.
- Add multimodal investigation of dashboard screenshots while retaining raw numeric evidence.
- Evaluate heterogeneous models to reduce correlated errors.

## Final competency checklist

At completion, you should be able to:

- Decide whether a problem needs one agent, multiple agents, or a deterministic workflow.
- Design agent roles around explicit context, tools, permissions, and output contracts.
- Implement supervisor, routing, handoff, sequential, and parallel patterns.
- Explain centralized and decentralized coordination trade-offs.
- Build bounded, secure, observable tool interfaces.
- Manage state, memory, checkpoints, artifacts, and resumable execution.
- Handle partial failures, retries, timeouts, cancellation, and non-termination.
- Use critique and human oversight without assuming they guarantee correctness.
- Threat-model prompt injection, tool abuse, excessive agency, and data leakage.
- Evaluate multi-agent value against a strong single-agent baseline.
- Measure and optimize quality, latency, tokens, and cost.
- Deploy and explain a truthful, reproducible, resume-worthy system.
