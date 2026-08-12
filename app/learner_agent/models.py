from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentAction(str, Enum):
    ASK = "ASK"
    HINT = "HINT"
    EXPLAIN = "EXPLAIN"
    SHOW_RESOURCE = "SHOW_RESOURCE"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    CREATE_REVISION_TASK = "CREATE_REVISION_TASK"
    VERIFY = "VERIFY"
    ASSIGN_TRANSFER = "ASSIGN_TRANSFER"
    ADVANCE = "ADVANCE"
    ESCALATE = "ESCALATE"
    WAIT = "WAIT"


class DiagnosisCode(str, Enum):
    TASK_MODEL = "TASK_MODEL"
    METHOD_GAP = "METHOD_GAP"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    OUTPUT_GAP = "OUTPUT_GAP"
    REASON_GAP = "REASON_GAP"
    REVISION_PENDING = "REVISION_PENDING"
    TRANSFER_GAP = "TRANSFER_GAP"
    SUCCESS = "SUCCESS"
    PROGRESS = "PROGRESS"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AgentObservationRequest(BaseModel):
    event_type: str = "user_message"
    task_id: str = ""
    message: str = ""
    answer: dict[str, Any] = Field(default_factory=dict)
    task_result: dict[str, Any] = Field(default_factory=dict)
    client_context: dict[str, Any] = Field(default_factory=dict)


class AgentStepRequest(AgentObservationRequest):
    use_model: bool = True


class AgentEvaluationRequest(BaseModel):
    output_text: str = ""
    action: AgentAction | None = None
    task_id: str = ""


class CapabilityState(BaseModel):
    capability_id: str
    label: str = ""
    stage: str = "unobserved"
    confidence: float = 0.0
    attempts: int = 0
    independent: int = 0
    transfer: int = 0
    combined: int = 0
    later_verified_count: int = 0


class LearnerAgentState(BaseModel):
    id: str = "stepin-learner"
    agent_id: str = "stepin-learner"
    protocol_version: str = "2.1"
    owner_user_id: str = ""
    session_id: str = ""
    stage: str = "beginner"
    current_task_id: str = ""
    current_capability_ids: list[str] = Field(default_factory=list)
    diagnosis: DiagnosisCode = DiagnosisCode.PROGRESS
    failure_streak: int = 0
    pending_action: AgentAction = AgentAction.WAIT
    capability_states: dict[str, CapabilityState] = Field(default_factory=dict)
    recent_interventions: list[dict[str, Any]] = Field(default_factory=list)
    last_observation: dict[str, Any] = Field(default_factory=dict)
    last_decision: dict[str, Any] = Field(default_factory=dict)
    last_evaluation: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class AgentDecision(BaseModel):
    decision_id: str
    action: AgentAction
    diagnosis: DiagnosisCode
    reason: str
    response: str = ""
    tool_name: str = ""
    tool_result: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)
    evaluation: dict[str, Any] = Field(default_factory=dict)
