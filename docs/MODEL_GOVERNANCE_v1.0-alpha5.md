# Model Governance · v1.0-alpha5

## Capability Registry

Each provider/model pair may record:

- streaming
- JSON Schema
- tools
- vision
- files
- context window
- max output
- reasoning level
- latency class
- input/output cost per million tokens

This allows Agents to declare required capabilities rather than hard-code a specific model name.

## Auto routing foundation

Task defaults currently include capability requirements for Profile, Coach, Writer, Reviewer, Critic and Revision. `provider_id=auto` or `model=auto` can resolve candidate models from enabled provider capability records.

This is a routing foundation. Production policy still needs live availability, provider health, tenant policy and measured evaluation results.

## Streaming

`LLMGateway.stream_complete()` supports a native OpenAI-compatible streaming path when the capability registry marks the model as streaming-capable. If native streaming is unavailable or fails, the gateway falls back truthfully to buffered completion and marks it non-native.

Existing Agent SSE endpoints remain progressive workflow streaming. Native token streaming is not yet wired end-to-end for every Agent/provider.

## Model Evaluation Harness

Metrics:

- success rate
- expected-content rate
- JSON validity rate
- average latency
- input/output token counts
- estimated cost from capability metadata

Evaluation requires a real configured provider to be a live API test. No live provider E2E was available in this build environment.
