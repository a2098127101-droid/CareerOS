export type VerificationLevel = 'unobserved' | 'signal' | 'evidence' | 'verified_evidence'

export interface CapabilityVerification {
  capabilityId: string
  name: string
  plain: string
  verificationLevel: VerificationLevel
  verificationVersion: string
  confidence: number
  metrics: {
    distinctTaskContexts: number
    foundationAttempts: number
    guided: number
    independent: number
    revisionSuccesses: number
    transferSuccesses: number
    verifiedEvidenceCount: number
  }
  requirements: Record<string, boolean>
  nextRequired: string[]
  sources: Array<Record<string, unknown>>
  authority: 'server'
  clientMayPromote: false
}

export interface SpatialNode {
  id: string
  kind: 'workstation' | 'project' | 'evidence' | 'artifact' | 'capability' | 'trajectory_event' | string
  label: string
  zone: string
  state: string
  refId: string
  data: Record<string, any>
  authority: 'server'
  readOnly: true
}

export interface SpatialConnection {
  id: string
  from: string
  to: string
  relation: string
  authority: 'server'
}

export interface WorkSampleMaterialTicket {
  id: string
  subject: string
  deadline: string
  impact: string
  status?: string
  detail?: string
}

export interface WorkSampleState {
  id: string
  version: string
  unlocked: boolean
  status: string
  definition: {
    id: string
    version: string
    title: string
    roleContext: string
    deliverable: string
    constraints: string[]
    materials: {
      messages: Array<{ id: string; time: string; from: string; text: string }>
      tickets: WorkSampleMaterialTicket[]
      customerSignals: Array<{ id: string; type: string; text: string }>
    }
    transfer: {
      title: string
      roleContext: string
      materials: WorkSampleMaterialTicket[]
    }
  }
  v1: Record<string, any>
  supervisorFeedback: string[]
  v2: Record<string, any>
  transferSubmission: Record<string, any>
  artifactId: string
  evidenceIds: string[]
  unlockReason: string
  authority: 'server'
}

export interface SceneState {
  ok: true
  sceneStateVersion: string
  generatedAt: string
  authority: {
    source: 'server'
    readOnly: true
    clientMayPromoteCapability: false
    clientMayVerifyEvidence: false
    clientMayRewriteTrajectory: false
    allowedClientEffects: string[]
  }
  identity: {
    userId: string
    displayName?: string
    role?: string
    tenantId?: string
  }
  session: { tenantId: string; ownerUserId: string; sessionId: string }
  foundation: {
    mode: string
    foundationComplete: boolean
    professionalUnlocked: boolean
    progress: number
    completed: number
    total: number
    currentTask?: FoundationTask | null
    abilities: Array<Record<string, any>>
    [key: string]: any
  }
  agent: {
    state: Record<string, any>
    trajectorySummary: Record<string, any>
    metrics: Record<string, any>
  }
  trajectory: { items: Array<Record<string, any>>; summary: Record<string, any> }
  projects: { items: Array<Record<string, any>>; count: number }
  evidence: { items: Array<Record<string, any>>; count: number }
  artifacts: { items: Array<Record<string, any>>; count: number }
  capabilities: {
    version: string
    levels: VerificationLevel[]
    policy: Record<string, string>
    summary: Record<VerificationLevel, number>
    items: CapabilityVerification[]
  }
  workSample: WorkSampleState
  spatial: {
    contract: string
    nodes: SpatialNode[]
    connections: SpatialConnection[]
    zones: string[]
  }
}

export interface FoundationTask {
  id: string
  title: string
  intro?: string
  why?: string
  type: string
  abilities?: string[]
  hintBudget?: number
  data?: Record<string, any>
}

export interface WorkSampleSubmission {
  priority_ticket_ids: string[]
  handoff: string
  work_notes: string
}
