# CareerOS v1.2 Architecture

## Target architecture

```text
Unified CareerOS UI
        |
Service / Adapter boundary
  +-----+------------------+
  |                        |
LocalDemoAdapter        ApiAdapter
  |                        |
State Schema v2          FastAPI
                           |
                  Domain / Service layer
                           |
               Repository abstractions
                 |       |       |
              SQLite  PostgreSQL  external services
```

## Current implementation status

The v1.2 H5 introduces the adapter boundary and runtime switch. Provider operations already cross that boundary in API mode. Most legacy Showcase CRUD still runs through the local state implementation and must be migrated incrementally to entity services.

## State-driven domain flow

```text
Experience / Evidence
        |
        v
Capability derivation
        |
        v
Target Job Requirements
        |
        v
Evidence matching
        |
        +--> Matched / Partial / Missing
        |
        v
Capability Gap
        |
        v
Action Tasks
        |
        v
Artifact / Review / Revision (existing platform capabilities)
```

The H5 v1.2 removes several fixed display values and derives active job match, gaps, capability scores and dashboard counts from current state.

## Open API Gateway

```text
Business Agent
    |
Model Gateway
    |
Provider Adapter
    +-- OpenAI Responses
    +-- OpenAI-compatible
    +-- Anthropic
    +-- Gemini
    +-- Custom REST
          |
          +-- configurable auth
          +-- request template
          +-- response mapping
          +-- model discovery
```

Business code should depend on the model gateway rather than vendor SDKs.

## Security boundary

- API keys are encrypted in backend provider storage.
- Public provider lists return masked API keys.
- Header names considered sensitive are masked in provider-list responses.
- Extra headers are treated as **non-secret configuration** in v1.2; do not store credentials there.
- H5 Demo mode does not persist API keys.
- H5 API mode sends credentials only to the backend provider endpoint.

## Remaining architectural debt

1. Complete entity-wide Service/Adapter migration.
2. Persist Evidence/Claim/Capability/JobRequirement link tables in the canonical backend domain model.
3. Finish router/service extraction from the large FastAPI composition module.
4. Eliminate remaining direct SQLite compatibility access from legacy modules.
5. Complete production runtime certification on real infrastructure.
