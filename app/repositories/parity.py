from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryParityReport:
    complete: tuple[str, ...]
    pending: tuple[str, ...]
    live_postgres_verified: bool = False

    @property
    def percent(self) -> int:
        total = len(self.complete) + len(self.pending)
        return int(len(self.complete) / total * 100) if total else 100

    @property
    def code_parity_complete(self) -> bool:
        """All required repository adapters exist and pass deterministic contract tests."""
        return not self.pending

    @property
    def production_cutover_ready(self) -> bool:
        """Stricter than code parity: requires a live PostgreSQL integration certification."""
        return self.code_parity_complete and self.live_postgres_verified


CORE_PARITY = RepositoryParityReport(
    complete=(
        "sessions",
        "identity",
        "artifacts",
        "evidence",
        "evidence_graph",
        "workflows",
        "collaboration",
        "knowledge",
        "jobs",
        "models",
        "commercial",
        "storage_registry",
        "projects",
    ),
    pending=(),
    live_postgres_verified=False,
)
