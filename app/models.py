from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

Track = Literal["成长赛道", "就业赛道", "待确认"]
DocumentType = str
ProviderKind = Literal["openai_responses", "openai_compatible", "anthropic", "gemini", "custom_rest"]
ProviderAuthType = Literal["bearer", "api_key_header", "api_key_query", "basic", "oauth2_client_credentials", "custom_headers", "none"]
AgentTask = Literal["profile", "coach", "writer", "reviewer", "critic", "revision"]


class StudentProfile(BaseModel):
    name: str = ""
    school: str = ""
    major: str = ""
    grade: str = ""
    degree: str = ""
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    internships: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    target_job: str = ""
    target_industry: str = ""
    target_cities: list[str] = Field(default_factory=list)
    expected_salary: str = ""
    competition_goal: str = ""
    evidence_text: str = ""


class ProfilePatch(BaseModel):
    name: str | None = None
    school: str | None = None
    major: str | None = None
    grade: str | None = None
    degree: str | None = None
    interests: list[str] | None = None
    skills: list[str] | None = None
    internships: list[str] | None = None
    projects: list[str] | None = None
    target_job: str | None = None
    target_industry: str | None = None
    target_cities: list[str] | None = None
    expected_salary: str | None = None
    competition_goal: str | None = None
    evidence_text: str | None = None


class TrackInput(BaseModel):
    grade_level: int = Field(default=2, ge=1, le=8)
    career_goal_clarity: int = Field(default=3, ge=1, le=5)
    internship_count: int = Field(default=0, ge=0, le=50)
    project_count: int = Field(default=0, ge=0, le=50)
    has_clear_target_job: bool = False


class TrackRecommendation(BaseModel):
    recommended_track: Track
    growth_score: int = Field(ge=0, le=100)
    employment_score: int = Field(ge=0, le=100)
    reasons: list[str]
    caveat: str


class ReviewDimension(BaseModel):
    name: str
    score: int = Field(ge=0, le=20)
    evidence: list[str] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)


class ReviewReport(BaseModel):
    total_score: int = Field(ge=0, le=100)
    dimensions: list[ReviewDimension]
    fatal_issues: list[str] = Field(default_factory=list)
    structural_issues: list[str] = Field(default_factory=list)
    surface_issues: list[str] = Field(default_factory=list)
    overall_comment: str
    revision_priority: list[str] = Field(default_factory=list)


class EvidenceAudit(BaseModel):
    passed: bool
    unsupported_numbers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class KnowledgeRef(BaseModel):
    source_id: str
    title: str
    chunk_id: str
    score: float = 0
    excerpt: str = ""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str | None = None
    knowledge_refs: list[KnowledgeRef] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    tenant_id: str = "demo-org"
    class_id: str = "default"
    student_id: str = ""
    student_user_id: str = ""
    stage: str = "profile"
    profile: StudentProfile = Field(default_factory=StudentProfile)
    track: Track = "待确认"
    track_recommendation: TrackRecommendation | None = None
    document_type: DocumentType | None = None
    draft: str = ""
    review: ReviewReport | None = None
    revised_draft: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
    teacher_note: str = ""


class ProfileExtractRequest(BaseModel):
    text: str


class TrackRecommendRequest(BaseModel):
    session_id: str
    signals: TrackInput


class DraftRequest(BaseModel):
    session_id: str
    document_type: str = Field(min_length=1, max_length=120)
    extra_instructions: str = ""


class ReviewRequest(BaseModel):
    session_id: str
    draft: str | None = None


class ReviseRequest(BaseModel):
    session_id: str
    draft: str | None = None
    review: ReviewReport | None = None


class ChatRequest(BaseModel):
    session_id: str
    message: str


class TeacherNoteRequest(BaseModel):
    note: str


class TeacherFeedbackRequest(BaseModel):
    content: str = Field(min_length=1, max_length=6000)
    teacher_name: str = Field(default="Advisor", max_length=80)
    priority: Literal["normal", "medium", "high"] = "normal"


class AITaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    task_type: str = Field(default="custom", max_length=80)
    session_id: str = ""
    tenant_id: str = "demo-org"
    priority: Literal["normal", "medium", "high"] = "normal"
    payload: dict = Field(default_factory=dict)


class AITaskUpdateRequest(BaseModel):
    status: Literal["todo", "doing", "done", "cancelled"] | None = None
    priority: Literal["normal", "medium", "high"] | None = None


class ProviderUpsert(BaseModel):
    provider_id: str = Field(min_length=2, max_length=60, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=80)
    kind: ProviderKind
    base_url: str
    api_key: str | None = None
    default_model: str
    enabled: bool = True
    timeout_seconds: int = Field(default=90, ge=5, le=600)
    extra_headers: dict[str, str] = Field(default_factory=dict)
    # Vendor-neutral connection settings. These are persisted as encrypted-secret-free
    # provider metadata so new REST/compatible providers do not require schema changes.
    auth_type: ProviderAuthType = "bearer"
    auth_header_name: str = Field(default="Authorization", max_length=120)
    auth_prefix: str = Field(default="Bearer", max_length=80)
    api_key_query_name: str = Field(default="key", max_length=120)
    oauth_token_url: str = Field(default="", max_length=2000)
    oauth_client_id: str = Field(default="", max_length=500)
    oauth_scope: str = Field(default="", max_length=1000)
    oauth_audience: str = Field(default="", max_length=1000)
    chat_path: str = Field(default="", max_length=1000)
    http_method: Literal["GET", "POST", "PUT", "PATCH"] = "POST"
    models_path: str = Field(default="", max_length=1000)
    request_template: dict = Field(default_factory=dict)
    response_path: str = Field(default="", max_length=500)
    models_response_path: str = Field(default="", max_length=500)
    query_params: dict[str, str] = Field(default_factory=dict)
    allow_private_network: bool = False


class UnifiedRuntimeEntityUpsert(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)
    expected_version: int | None = Field(default=None, ge=1)
    idempotency_key: str = Field(default="", max_length=200)


class UnifiedRuntimeCollectionReplace(BaseModel):
    items: list[dict] = Field(default_factory=list)


class UnifiedRuntimeStateValue(BaseModel):
    value: object | None = None


class UnifiedRuntimeImportRequest(BaseModel):
    data: dict = Field(default_factory=dict)
    mode: Literal["replace", "merge"] = "replace"


class WorkspaceEvidenceUpsert(BaseModel):
    id: str = Field(default="", max_length=200)
    title: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=2, max_length=120000)
    proof: str = Field(default="", max_length=12000)
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    verified: bool = False
    expected_version: int | None = Field(default=None, ge=1)



class WorkspaceEvidenceVerificationDecision(BaseModel):
    decision: Literal["submit_review", "verified", "partial", "rejected", "contradicted"]
    reason: str = Field(default="", max_length=12000)
    confidence: float = Field(default=1.0, ge=0, le=1)
    method: str = Field(default="human_review", max_length=80)

class WorkspaceArtifactUpsert(BaseModel):
    id: str = Field(default="", max_length=200)
    title: str = Field(min_length=1, max_length=240)
    type: str = Field(default="custom", max_length=120)
    content: str = Field(default="", max_length=500000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)
    expected_version: int | None = Field(default=None, ge=1)


class WorkspaceTaskUpsert(BaseModel):
    id: str = Field(default="", max_length=200)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=6000)
    type: str = Field(default="custom", max_length=80)
    status: Literal["todo", "done", "completed", "cancelled"] = "todo"
    priority: Literal["normal", "medium", "high", "Normal", "High"] = "normal"
    origin_type: str = Field(default="manual", max_length=80)
    origin_id: str = Field(default="", max_length=200)
    expected_version: int | None = Field(default=None, ge=1)


class WorkspaceUserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=160)
    role: str = Field(default="student", max_length=80)
    password: str = Field(default="", max_length=200)
    invite_only: bool = True


class WorkspaceInterviewUpsert(BaseModel):
    id: str = Field(default="", max_length=200)
    question: str = Field(default="", max_length=6000)
    answer: str = Field(default="", max_length=30000)
    scores: dict = Field(default_factory=dict)
    feedback: str = Field(default="", max_length=12000)
    expected_version: int | None = Field(default=None, ge=1)





class WorkspaceCoachRequest(BaseModel):
    message: str = Field(min_length=1, max_length=30000)
    mode: str = Field(default="coach", max_length=80)


class WorkspaceInterviewEvaluateRequest(BaseModel):
    question: str = Field(min_length=1, max_length=6000)
    answer: str = Field(min_length=1, max_length=30000)
    target_job: str = Field(default="", max_length=300)


class WorkspacePPTReviewRequest(BaseModel):
    slides: list[dict] = Field(default_factory=list, max_length=200)
    target_job: str = Field(default="", max_length=300)


class WorkspaceInterviewEvaluation(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)
    relevance: int = Field(ge=0, le=100)
    evidence: int = Field(ge=0, le=100)
    specificity: int = Field(ge=0, le=100)
    role_fit: int = Field(ge=0, le=100)
    feedback: str = Field(max_length=12000)
    risks: list[str] = Field(default_factory=list, max_length=20)


class WorkspacePPTReviewResult(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    narrative: int = Field(ge=0, le=100)
    evidence: int = Field(ge=0, le=100)
    logic: int = Field(ge=0, le=100)
    role_fit: int = Field(ge=0, le=100)
    density: int = Field(ge=0, le=100)
    issues: list[dict] = Field(default_factory=list, max_length=100)
    summary: str = Field(max_length=12000)


class DomainRecomputeRequest(BaseModel):
    job_id: str = Field(default="", max_length=200)
    reason: str = Field(default="manual recompute", max_length=500)


class DomainClaimUpsert(BaseModel):
    claim_text: str = Field(min_length=3, max_length=12000)
    claim_type: str = Field(default="manual", max_length=80)
    expected_version: int | None = Field(default=None, ge=1)
    reason: str = Field(default="manual claim edit", max_length=500)


class DomainGapStatusUpdate(BaseModel):
    status: Literal["open", "planned", "in_progress", "resolved", "accepted", "dismissed"]
    expected_version: int | None = Field(default=None, ge=1)
    reason: str = Field(default="gap status update", max_length=500)

class RouteUpsert(BaseModel):
    task: AgentTask
    provider_id: str
    model: str
    fallback_provider_id: str | None = None
    fallback_model: str | None = None
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4000, ge=128, le=64000)




class ModelCapabilityUpsert(BaseModel):
    provider_id: str = Field(min_length=2, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    supports_streaming: bool = False
    supports_json_schema: bool = False
    supports_tools: bool = False
    supports_vision: bool = False
    supports_files: bool = False
    context_window: int = Field(default=0, ge=0)
    max_output: int = Field(default=0, ge=0)
    reasoning_level: Literal["none", "low", "medium", "high"] = "none"
    latency_class: Literal["unknown", "fast", "balanced", "slow"] = "unknown"
    input_cost_per_million: float = Field(default=0, ge=0)
    output_cost_per_million: float = Field(default=0, ge=0)
    metadata: dict = Field(default_factory=dict)


class ModelRecommendationRequest(BaseModel):
    task: str = Field(default="", max_length=80)
    required_capabilities: list[str] = Field(default_factory=list, max_length=20)
    min_context_window: int = Field(default=0, ge=0)
    max_input_cost_per_million: float | None = Field(default=None, ge=0)
    max_output_cost_per_million: float | None = Field(default=None, ge=0)
    prefer_latency: Literal["any", "fast", "balanced"] = "any"


class ModelEvalCaseInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    expected_contains: list[str] = Field(default_factory=list, max_length=30)
    expect_json: bool = False


class ModelEvaluationRequest(BaseModel):
    provider_id: str = Field(min_length=2, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    task: str = Field(default="evaluation", max_length=80)
    cases: list[ModelEvalCaseInput] = Field(min_length=1, max_length=50)


class ProviderTestRequest(BaseModel):
    provider_id: str
    model: str | None = None


class ProviderPlaygroundRequest(BaseModel):
    provider_id: str
    model: str | None = None
    system: str = Field(default="You are a helpful assistant.", max_length=20000)
    user: str = Field(min_length=1, max_length=100000)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=1000, ge=1, le=64000)


class ProviderModelsRequest(BaseModel):
    provider_id: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    scope: str = "global"
    top_k: int = Field(default=5, ge=1, le=20)
    effective_year: str = Field(default="", max_length=16)


class KnowledgeTextIngest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)
    scope: str = "global"
    tags: list[str] = Field(default_factory=list)
    category: str = "other"
    authority: str = "internal"
    effective_year: str = ""
    priority: int = Field(default=50, ge=0, le=100)


class RAGEvalCaseInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    expected_source_id: str = Field(default="", max_length=200)
    expected_source_title: str = Field(default="", max_length=300)
    expected_authority: str = Field(default="", max_length=80)
    expected_year: str = Field(default="", max_length=16)
    required_terms: list[str] = Field(default_factory=list, max_length=50)
    scope: str = Field(default="global", max_length=80)
    notes: str = Field(default="", max_length=1000)


class RAGEvaluationRequest(BaseModel):
    cases: list[RAGEvalCaseInput] = Field(min_length=1, max_length=200)


class EvidenceVerificationRequest(BaseModel):
    claim_ids: list[str] = Field(default_factory=list, max_length=300)


class ManualClaimVerificationRequest(BaseModel):
    status: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "UNVERIFIED"]
    confidence: float = Field(default=1.0, ge=0, le=1)
    reason: str = Field(default="", max_length=4000)


class JobMatchRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=160)


class KnowledgeSourceUpdate(BaseModel):
    title: str | None = None
    scope: str | None = None
    tags: list[str] | None = None
    active: bool | None = None
    category: str | None = None
    authority: str | None = None
    effective_year: str | None = None
    priority: int | None = Field(default=None, ge=0, le=100)


# ---------- Production authentication / tenant models ----------
Role = Literal["super_admin", "school_admin", "teacher", "student", "platform_admin", "organization_admin", "advisor", "participant"]


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Role
    display_name: str = Field(default="", max_length=120)
    ttl_hours: int = Field(default=72, ge=1, le=720)


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    password: str = Field(min_length=10, max_length=512)
    display_name: str = Field(default="", max_length=120)


class UserLifecycleUpdateRequest(BaseModel):
    status: Literal["active", "disabled", "archived"]


class MembershipRoleUpdateRequest(BaseModel):
    role: Role


class PrivacyConsentRequest(BaseModel):
    policy_version: str = Field(min_length=1, max_length=80)
    purpose: str = Field(default="service", max_length=120)
    granted: bool = True
    source: str = Field(default="ui", max_length=80)


class DataSubjectRequestCreate(BaseModel):
    request_type: Literal["export", "delete"]
    notes: str = Field(default="", max_length=1000)


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=512)
    display_name: str = Field(min_length=1, max_length=120)
    tenant_id: str = Field(min_length=2, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=512)
    tenant_id: str | None = Field(default=None, max_length=120)
    role: Role | None = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=10, max_length=512)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    new_password: str = Field(min_length=10, max_length=512)


class TenantCreateRequest(BaseModel):
    tenant_id: str = Field(min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=200)
    tenant_type: Literal["organization", "school", "training", "enterprise", "individual"] = "organization"
    product_preset: Literal["career_development", "campus_career", "career_competition", "career_service", "enterprise_talent"] = "career_development"


class TenantProductConfigRequest(BaseModel):
    tenant_type: Literal["organization", "school", "training", "enterprise", "individual"] | None = None
    product_preset: Literal["career_development", "campus_career", "career_competition", "career_service", "enterprise_talent"] | None = None
    settings: dict | None = None


class TenantBrandingRequest(BaseModel):
    branding: dict = Field(default_factory=dict)


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=512)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    tenant_id: str | None = Field(default=None, max_length=120)


class ClassCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    tenant_id: str | None = Field(default=None, max_length=120)


class ClassMemberRequest(BaseModel):
    user_id: str = Field(min_length=2, max_length=120)
    role: Literal["teacher", "student", "advisor", "participant"]



class SubscriptionUpdateRequest(BaseModel):
    plan_id: Literal["free", "professional", "enterprise"]


class AnalyticsEventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=120)
    session_id: str = Field(default="", max_length=160)
    properties: dict = Field(default_factory=dict)


class BillingCheckoutRequest(BaseModel):
    plan_id: Literal["free", "professional", "enterprise"]
    success_url: str = Field(default="", max_length=1000)
    cancel_url: str = Field(default="", max_length=1000)


class WorkflowTemplateCreateRequest(BaseModel):
    preset_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    steps: list[dict] = Field(min_length=1, max_length=50)


class WorkflowTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    steps: list[dict] | None = Field(default=None, min_length=1, max_length=50)


class ArtifactTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    kind: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    renderer: str = Field(default="structured_text", max_length=100)
    review_rubric: str = Field(default="general_v1", max_length=120)
    presets: list[str] = Field(default_factory=list, max_length=20)
    schema_definition: dict = Field(default_factory=dict, alias="schema")


class ArtifactTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    label: str | None = Field(default=None, max_length=160)
    aliases: list[str] | None = Field(default=None, max_length=50)
    renderer: str | None = Field(default=None, max_length=100)
    review_rubric: str | None = Field(default=None, max_length=120)
    presets: list[str] | None = Field(default=None, max_length=20)
    schema_definition: dict | None = Field(default=None, alias="schema")
