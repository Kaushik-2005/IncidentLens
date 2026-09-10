# IncidentLens Learning Tracker

## Current position
- Roadmap: ../roadmap.md
- Module: 3 - Incident-response domain and realistic telemetry
- Phase: Orient
- Status: In Progress
- Mode: Guided Learning
- Exact current task: Read the Module 3 concepts and inspect the recorded fixture before defining the telemetry-neutral schema.
- Last completed evidence: Module 1 completed on 2026-09-10 through source review, learner explanations, project contract draft, failure-analysis review, and design record reconciliation.

## Module progress
| Module | Title | Implementation | Understanding | Overall |
| --- | --- | --- | --- | --- |
| 1 | Multi-agent foundations and project contract | Completed | Checked | Completed |
| 2 | Gemini agent loop and single-agent baseline | Completed | Checked | Completed |
| 3 | Incident-response domain and realistic telemetry | Not started | Not checked | Not started |
| 4 | Tool engineering and the observation boundary | Not started | Not checked | Not started |
| 5 | LangGraph state and deterministic orchestration | Not started | Not checked | Not started |
| 6 | Specialization and context engineering | Not started | Not checked | Not started |
| 7 | Coordination topologies and protocol design | Not started | Not checked | Not started |
| 8 | Parallel investigation and evidence aggregation | Not started | Not checked | Not started |
| 9 | Memory, persistence, checkpoints, and artifacts | Not started | Not checked | Not started |
| 10 | Planning, adaptive routing, budgets, and termination | Not started | Not checked | Not started |
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