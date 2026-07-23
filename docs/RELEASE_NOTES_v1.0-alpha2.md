# Release Notes — v1.0-alpha2 Repository Parity

CareerOS v1.0-alpha2 completes the **code-level SQLAlchemy repository adapter surface** required for the PostgreSQL migration path introduced in alpha1.

Key additions:

- complete SQLAlchemy adapter surface;
- fail-closed PostgreSQL container wiring;
- additional tenant SQL scoping;
- generic Agent fallback cleanup;
- snapshot integrity hardening;
- live PostgreSQL certification harness;
- 61-test regression suite.

This release remains an alpha because the build environment did not provide a real PostgreSQL server/driver for certification. The next release should focus on live PostgreSQL cutover verification and pgvector/Semantic RAG rather than adding more UI pages.
