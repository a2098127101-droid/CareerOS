# StepIn Foundation v1.9.0 integration snapshot

This directory stages the StepIn Foundation v1.9.0 implementation against the current CareerOS production main line.

## Why this is staged instead of overwriting main

`CareerOS/main` is currently `v1.5 production-final` with Domain Intelligence, production deployment, RLS/security hardening and locked CI. StepIn v1.9.0 evolved from the previously available v1.4 source line. Replacing root files wholesale would regress production work.

This branch therefore preserves the Foundation implementation as an auditable integration set:

- new Foundation ability/progress domain files;
- Foundation API router and contract audit;
- v1.9 Foundation regression tests;
- post-foundation direction discovery, cross-task aggregation, expression and mini-project services;
- Foundation runtime/release/Windows/test documentation.

The complete local v1.8.0 → v1.9.0 text patch was generated and audited during staging, but the conflicting root overlays are intentionally not copied over production files in this PR. Patch SHA-256: `5be459da3eb343fba4f19fdab37d058775f99af681636c0e33999374d6bcd58b`.

The validated StepIn v1.9.0 release package SHA-256 is `e83bdd4642e5ab572579d99d93e3f2a3141bb40aef6f8787f6112ee3d7ad0b57`.

## Production integration points

The v1.9 implementation changes these existing StepIn files and therefore requires a real merge against current production code rather than replacement:

- `app/main.py`
- `app/today_next.py`
- `app/practice_runtime.py`
- `app/interaction2.py`
- `app/routers/practice.py`
- `app/static/student.html`
- `app/static/teacher.html`
- `app/static/interaction2.css`
- `app/static/workbench-shell.js`
- version/readme/release wiring

## Recommended merge order

1. Merge the new Foundation domain files and router into current production main.
2. Port Foundation service/router wiring into production `app/main.py` without removing Domain Intelligence, RLS, production deployment or current CI.
3. Port Today Next and Practice gating changes against the current production runtime.
4. Reconcile the student/teacher Foundation UI with the current production workspace.
5. Extend the locked production CI matrix with Foundation tests and the 8-route contract audit.
6. Run the full current production test/security/release matrix before merging.

Do **not** wholesale replace production `app/main.py`, security/deployment configuration, repository layer, or current CI with the older-base StepIn copies.
