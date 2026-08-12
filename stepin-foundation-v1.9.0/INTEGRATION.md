# StepIn Foundation v1.9.0 integration snapshot

This directory stages the StepIn Foundation v1.9.0 implementation against the current CareerOS production main line.

## Why this is staged instead of overwriting main

`CareerOS/main` is currently `v1.5 production-final` with Domain Intelligence, production deployment, RLS/security hardening and locked CI. StepIn v1.9.0 evolved from the previously available v1.4 source line. Replacing root files wholesale would regress production work.

This branch therefore preserves the Foundation implementation as an auditable integration set:

- new Foundation ability/progress domain files;
- Foundation API router and contract audit;
- v1.9 Foundation regression tests;
- a complete text patch from StepIn v1.8.0 to v1.9.0;
- Foundation runtime/release/Windows/test documentation.

## Recommended merge order

1. Merge the new Foundation domain files and router into current production main.
2. Port the v1.9 wiring from the patch into production `app/main.py` without removing Domain Intelligence, production RLS, deployment or CI.
3. Port Today Next and Practice gating changes against the current production runtime.
4. Reconcile the student/teacher Foundation UI with the current production workspaces.
5. Extend the locked production CI matrix with Foundation tests, then run the complete production release gates.

Do **not** wholesale replace production `app/main.py`, security/deployment configuration, or current CI using the older-base overlay represented by the patch.
