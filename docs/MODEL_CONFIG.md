# Model Configuration

The six core Agents are independently routable:

Profile, Coach, Writer, Reviewer, Critic, Revision.

Each route supports a primary provider/model and optional fallback. the current runtime also includes retry/backoff and an in-memory circuit-breaker foundation.

For production, add provider capability metadata, streaming, distributed circuit state and budget policies before large-scale rollout.
