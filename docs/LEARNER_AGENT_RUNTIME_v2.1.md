# StepIn Learner Agent Runtime v2.1

StepIn Learner Agent is a stateful practice-coaching agent that can be called by the current StepIn UI or by another authenticated client. It is not a chat wrapper around an LLM. The execution loop owns persistent learner state, deterministic policy, a bounded tool contract, episodic memory, human escalation and runtime evaluation. The model is an optional language layer and cannot select tools or mark capabilities as mastered.

## Architecture

The runtime is split into six first-class components under `app/learner_agent/`.

`State` persists the learner stage, current task, capability confidence, failure streak, diagnosis, recent interventions and last decision in the server-authoritative unified runtime repository. Capability confidence is synchronized from observed practice signals and deliberately distinguishes `developing`, `independent`, `transfer` and `verified`; the Agent never creates a `mastered` state by model assertion.

`Policy` diagnoses the current block and selects exactly one bounded action. The current action space is `ASK`, `HINT`, `EXPLAIN`, `SHOW_RESOURCE`, `REQUEST_EVIDENCE`, `CREATE_REVISION_TASK`, `VERIFY`, `ASSIGN_TRANSFER`, `ADVANCE`, `ESCALATE`, and `WAIT`. The support ladder fades from diagnostic questioning to a minimal hint, then method explanation, process-evidence request, and finally human escalation. A model response cannot change the selected action.

`Tools` is the only adapter between the Agent and the CareerOS/StepIn domain services. The tool contract contains `read_foundation`, `next_hint`, `request_evidence`, `create_revision_task`, `verification_snapshot`, `assign_transfer`, `advance`, and `escalate_human`. There is intentionally no tool for generating a final deliverable or marking a capability as mastered.

`Memory` stores a bounded episodic history, diagnosis counts, action counts and repeated problem patterns per tenant and learner. It uses the same server-authoritative repository and optimistic concurrency as other runtime entities. The history is capped so it remains an operational memory rather than an unbounded transcript dump.

`Execution Loop` performs: observe current practice state; diagnose; choose a bounded action; apply policy guards; persist pending state; execute at most one bounded tool mutation; optionally ask the configured `coach` model route to phrase an `ASK`, `EXPLAIN`, or `SHOW_RESOURCE` intervention; run output leakage evaluation; persist the decision and intervention; update memory; return the new state and evaluation to the client.

`Evaluation` measures direct-answer leakage, over-help, invalid advancement, policy-ladder violations, human-escalation rate, model-use rate and verified-capability count. Model output is checked before it is returned. If a generated intervention exposes a known answer or uses explicit answer-giving language, the runtime discards it and falls back to deterministic safe guidance.

## Standalone HTTP contract

All client integrations use the stable `/api/learner-agent/v1` contract. Authentication, tenant isolation and learner ownership remain enforced by the production CareerOS identity layer.

- `GET /api/learner-agent/v1/manifest` returns the Agent identity, version, guarantees and tool manifest.
- `GET /api/learner-agent/v1/tools` returns the bounded tool contract.
- `GET /api/learner-agent/v1/state` returns persistent learner-Agent state.
- `GET /api/learner-agent/v1/memory` returns the bounded memory snapshot.
- `GET /api/learner-agent/v1/decisions` returns recent Agent decisions.
- `POST /api/learner-agent/v1/observe` records an observation and diagnosis without executing a tool.
- `POST /api/learner-agent/v1/step` runs one complete observe-diagnose-decide-act-verify cycle.
- `POST /api/learner-agent/v1/evaluate` returns aggregate evaluation and can evaluate a supplied sample response.

A web, desktop, LMS, mobile or other client should call the Agent rather than embedding policy rules locally. A typical call is:

```json
{
  "event_type": "task_failed",
  "task_id": "FND-01-order",
  "message": "我还是不知道怎么判断",
  "answer": {},
  "task_result": {
    "ok": false,
    "issues": ["还没有按同一标准完成"]
  },
  "client_context": {
    "surface": "web"
  },
  "use_model": true
}
```

The response contains the fixed Agent decision, any bounded tool result, the persistent learner state, public task context and the current aggregate evaluation. Clients should render the response but must not independently promote capability states or bypass Foundation/Professional gates.

## Model boundary

The existing CareerOS `coach` route is reused as an optional language model route. This keeps provider routing, quota control, PII minimization, retries and circuit breaking inside the existing production gateway. If the model route is unavailable or fails, the Agent continues with deterministic interventions. If the model leaks an answer, the runtime rejects that text and returns the safe fallback instead.

This design intentionally keeps the Agent behaviorally independent but deployment-compatible with the current monolith. The runtime does not import `app.main`, use `sys.modules`, access SQLite directly, or depend on a browser. Because dependencies enter through State/Tools/Repository interfaces, the same runtime can later be moved to a dedicated service without changing the client contract.

## Production gates

The Agent contract audit verifies all eight HTTP routes, all eleven actions, all eight tools, required component files, and the absence of direct `app.main`/SQLite coupling in the runtime/tool layer. The pytest matrix adds owner isolation, observe-only behavior, the fading-support escalation ladder, bounded tool surface, direct-answer leakage detection, malicious model-output rejection, persistent decision memory and aggregate evaluation.

This release does not claim that pedagogical validity is finished. The next evidence gate is empirical: run real learner sessions, label diagnosis correctness and intervention usefulness, then calibrate capability confidence and policy thresholds from observed outcomes rather than increasing model autonomy.