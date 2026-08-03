# CareerOS v1.5.2 UI Interaction Regression

Date: 2026-07-28

## Scope

This regression verifies the visible Student and Teacher workspace controls as a complete contract:

`visible control -> browser handler -> authenticated API -> persisted/read-back state -> user feedback`.

It preserves the existing Agent Runtime, Multi-Model Gateway, RAG, Structured Job Store,
Evidence Ledger/Graph, Artifact Versioning, Teacher Feedback, AI Task Center and workflow stores.

## Automated results

- Python compile: PASS
- JavaScript syntax (`ui.js`, `student-workspace.js`, `teacher-workspace.js`): PASS
- Pytest: **166 passed, 1 dependency deprecation warning**
- UI/API contract integration: PASS
- Student/teacher RBAC integration: PASS
- Workspace module capability contract: PASS

The warning comes from the installed FastAPI TestClient compatibility layer recommending
`httpx2`; it is not a product test failure.

## Browser results

Browser: Codex in-app Chromium surface against the local authenticated FastAPI runtime.

Student:

- Seven business workspace panels opened successfully.
- Notifications, account and Inspector profile actions opened successfully.
- Evidence was created through the UI and read back from the backend.
- Mobile viewport 390x844: sidebar hidden, mobile navigation visible, no horizontal overflow.

Teacher:

- Ten business/system workspace panels opened successfully.
- Workspace selector, help, notifications and account actions opened successfully.
- A task was created through the UI, read back, and updated to completed.
- Native `window.prompt` incompatibility was found and replaced with a CareerOS modal.
- Mobile viewport 390x844: sidebar hidden, mobile navigation visible, horizontal overflow fixed.

Final clean-tab console check: **0 errors, 0 warnings**.

## Explicit boundaries

- The interview UI calls the real configured Reviewer route. No production model key was added
  during this regression, so external model-provider success was not claimed.
- File parsing remains covered by API tests; no personal file was uploaded during browser QA.
- Production certification is still separate from this UI regression and requires the configured
  observability, TLS/domain, external model and other infrastructure gates.
