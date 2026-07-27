# Source provenance for CareerOS v1.5

The active build environment did not contain the previously referenced full `CareerOS-main_v1.4.1_security-trust.zip` source archive. It contained:

- the complete CareerOS v1.4 Canonical Runtime source archive;
- the v1.4.1 H5 release;
- v1.4.1 security, Evidence Trust, migration, test and readiness documentation.

CareerOS v1.5 was therefore produced from the complete v1.4 source baseline. The relevant v1.4.1 security and Evidence Trust constraints were reimplemented and regression-tested before the v1.5 Domain Intelligence model was added.

This release is self-contained. It does not require the missing v1.4.1 archive to build or run.

The automated release suite verifies role restrictions used by the current source, Evidence self-verification prevention, Evidence verification history/invalidation, canonical repository parity, and the v1.5 Claim–Capability–Requirement–Gap chain. Historical documentation is retained for reference and does not override the current source or test results.
