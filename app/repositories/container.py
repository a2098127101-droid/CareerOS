from __future__ import annotations

from dataclasses import dataclass

from ..artifact_store import ArtifactStore
from ..auth_store import AuthStore
from ..collaboration_store import CollaborationStore
from ..commercial_store import CommercialStore
from ..evidence_graph import EvidenceGraphStore
from ..evidence_store import EvidenceStore
from ..job_store import JobStore
from ..knowledge import KnowledgeStore
from ..model_store import ModelConfigStore
from ..storage import StorageRegistry
from ..store import SessionStore
from ..workflow_store import WorkflowStore
from ..unified_runtime_store import UnifiedRuntimeStore
from ..template_registry import TemplateRegistry
from ..embedding_gateway import EmbeddingGateway
from ..retrieval import RerankerGateway
from ..domain_intelligence import DomainIntelligenceStore
from ..core.database import DatabaseCapabilityReport, database_capabilities, create_database_engine, BASELINE_METADATA, schema_health
from .parity import CORE_PARITY


@dataclass
class RepositoryContainer:
    """Dependency container that isolates application wiring from storage implementation.

    SQLite remains the local/development compatibility runtime. v1.0-beta1 implements SQLAlchemy
    repository adapters for the full persistence surface; live PostgreSQL cutover remains fail-closed
    until the target environment has a PostgreSQL driver, provisioned Alembic schema, and integration verification.
    """

    backend: str
    sessions: SessionStore
    identity: AuthStore
    artifacts: ArtifactStore
    evidence: EvidenceStore
    evidence_graph: EvidenceGraphStore
    workflows: WorkflowStore
    collaboration: CollaborationStore
    knowledge: KnowledgeStore
    jobs: JobStore
    models: ModelConfigStore
    commercial: CommercialStore
    storage_registry: StorageRegistry
    templates: TemplateRegistry
    runtime_entities: object
    domain_intelligence: object
    capabilities: DatabaseCapabilityReport

    @classmethod
    def build_sqlite(
        cls,
        *,
        db_path: str,
        app_secret_key: str,
        session_ttl_hours: int,
        embedding_gateway: EmbeddingGateway,
        reranker_gateway: RerankerGateway | None = None,
        database_url: str = "",
        app_env: str = "development",
    ) -> "RepositoryContainer":
        caps = database_capabilities(
            database_url=database_url,
            db_path=db_path,
            repository_backend="sqlite",
            app_env=app_env,
        )
        engine = create_database_engine("", db_path)
        template_registry = TemplateRegistry(engine)
        return cls(
            backend="sqlite",
            sessions=SessionStore(db_path),
            identity=AuthStore(db_path, session_ttl_hours=session_ttl_hours),
            artifacts=ArtifactStore(db_path),
            evidence=EvidenceStore(db_path),
            evidence_graph=EvidenceGraphStore(db_path),
            workflows=WorkflowStore(db_path, template_registry=template_registry),
            collaboration=CollaborationStore(db_path),
            knowledge=KnowledgeStore(
                db_path,
                embedding_gateway=embedding_gateway,
                reranker_gateway=reranker_gateway,
            ),
            jobs=JobStore(db_path),
            models=ModelConfigStore(db_path, app_secret_key),
            commercial=CommercialStore(db_path),
            storage_registry=StorageRegistry(db_path),
            templates=template_registry,
            runtime_entities=UnifiedRuntimeStore(db_path),
            domain_intelligence=DomainIntelligenceStore(db_path),
            capabilities=caps,
        )

    @classmethod
    def build_postgresql(
        cls,
        *,
        db_path: str,
        database_url: str,
        app_secret_key: str,
        session_ttl_hours: int,
        embedding_gateway: EmbeddingGateway,
        reranker_gateway: RerankerGateway | None = None,
        app_env: str = "development",
    ) -> "RepositoryContainer":
        if not CORE_PARITY.code_parity_complete:
            pending = ", ".join(CORE_PARITY.pending)
            raise RuntimeError(f"PostgreSQL repository parity incomplete: {pending}")
        caps = database_capabilities(
            database_url=database_url, db_path=db_path, repository_backend="postgresql", app_env=app_env
        )
        if caps.blockers:
            raise RuntimeError("PostgreSQL runtime blocked: " + "; ".join(caps.blockers))
        engine = create_database_engine(database_url, db_path)
        template_registry = TemplateRegistry(engine)
        health = schema_health(engine)
        if not health["ready"]:
            sample = ", ".join(health["missing"][:8])
            raise RuntimeError(
                "PostgreSQL schema is not at the CareerOS v1 baseline. Run `alembic upgrade head` before startup. "
                f"Missing tables: {sample}"
            )
        from .postgres import (
            PostgresArtifactRepository, PostgresCollaborationRepository, PostgresCommercialRepository,
            PostgresEvidenceGraphRepository, PostgresEvidenceRepository, PostgresIdentityRepository,
            PostgresJobRepository, PostgresKnowledgeRepository, PostgresModelConfigRepository,
            PostgresSessionRepository, PostgresStorageRegistry, PostgresWorkflowRepository, PostgresUnifiedRuntimeRepository, PostgresDomainIntelligenceRepository,
        )
        return cls(
            backend="postgresql",
            sessions=PostgresSessionRepository(engine, BASELINE_METADATA),
            identity=PostgresIdentityRepository(engine, session_ttl_hours=session_ttl_hours),
            artifacts=PostgresArtifactRepository(engine),
            evidence=PostgresEvidenceRepository(engine),
            evidence_graph=PostgresEvidenceGraphRepository(engine),
            workflows=PostgresWorkflowRepository(engine, template_registry=template_registry),
            collaboration=PostgresCollaborationRepository(engine),
            knowledge=PostgresKnowledgeRepository(
                engine,
                embedding_gateway=embedding_gateway,
                reranker_gateway=reranker_gateway,
            ),
            jobs=PostgresJobRepository(engine),
            models=PostgresModelConfigRepository(engine, app_secret_key),
            commercial=PostgresCommercialRepository(engine),
            storage_registry=PostgresStorageRegistry(engine),
            templates=template_registry,
            runtime_entities=PostgresUnifiedRuntimeRepository(engine),
            domain_intelligence=PostgresDomainIntelligenceRepository(engine),
            capabilities=caps,
        )

    @classmethod
    def build_sqlalchemy_core_for_testing(
        cls, *, engine, db_path: str, app_secret_key: str, session_ttl_hours: int,
        embedding_gateway: EmbeddingGateway, reranker_gateway: RerankerGateway | None = None,
    ) -> dict[str, object]:
        """Build only repositories with SQLAlchemy parity.

        This is used for deterministic contract/parity tests on SQLite and can target PostgreSQL when
        a live driver/server is available. It builds the complete SQLAlchemy repository surface.
        """
        from .postgres import (
            PostgresArtifactRepository, PostgresCollaborationRepository, PostgresCommercialRepository,
            PostgresEvidenceGraphRepository, PostgresEvidenceRepository, PostgresIdentityRepository,
            PostgresJobRepository, PostgresKnowledgeRepository, PostgresModelConfigRepository,
            PostgresSessionRepository, PostgresStorageRegistry, PostgresWorkflowRepository, PostgresUnifiedRuntimeRepository, PostgresDomainIntelligenceRepository,
        )
        return {
            "sessions": PostgresSessionRepository(engine, BASELINE_METADATA),
            "identity": PostgresIdentityRepository(engine, session_ttl_hours=session_ttl_hours),
            "artifacts": PostgresArtifactRepository(engine),
            "evidence": PostgresEvidenceRepository(engine),
            "evidence_graph": PostgresEvidenceGraphRepository(engine),
            "workflows": PostgresWorkflowRepository(engine),
            "collaboration": PostgresCollaborationRepository(engine),
            "knowledge": PostgresKnowledgeRepository(
                engine,
                embedding_gateway=embedding_gateway,
                reranker_gateway=reranker_gateway,
            ),
            "jobs": PostgresJobRepository(engine),
            "models": PostgresModelConfigRepository(engine, app_secret_key),
            "commercial": PostgresCommercialRepository(engine),
            "storage_registry": PostgresStorageRegistry(engine),
            "runtime_entities": PostgresUnifiedRuntimeRepository(engine),
            "domain_intelligence": PostgresDomainIntelligenceRepository(engine),
        }
