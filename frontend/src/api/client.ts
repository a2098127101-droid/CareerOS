import type { SceneState, WorkSampleSubmission } from './types'

export class ApiError extends Error {
  status: number
  payload: any

  constructor(message: string, status: number, payload: any) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

function detailMessage(payload: any, fallback: string): string {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (typeof detail?.message === 'string') return detail.message
  if (typeof payload?.message === 'string') return payload.message
  return fallback
}

export async function api<T>(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const headers = new Headers(init.headers || {})
  if (init.body !== undefined && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, {
    credentials: 'same-origin',
    ...init,
    headers,
    signal,
  })
  const payload = await response.json().catch(() => ({}))
  if (response.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.assign(`/login?next=${next}`)
    throw new ApiError('请先登录', response.status, payload)
  }
  if (!response.ok) {
    throw new ApiError(detailMessage(payload, `请求失败 ${response.status}`), response.status, payload)
  }
  return payload as T
}

export const sceneApi = {
  state(signal?: AbortSignal) {
    return api<SceneState>('/api/scene/v1/state', {}, signal)
  },
  contract(signal?: AbortSignal) {
    return api<Record<string, any>>('/api/scene/v1/contract', {}, signal)
  },
}

export const foundationApi = {
  complete(taskId: string, answer: Record<string, any>) {
    return api<any>(`/api/foundation/v1/tasks/${encodeURIComponent(taskId)}/complete`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    })
  },
  agentHint(taskId: string) {
    return api<any>('/api/learner-agent/v1/step', {
      method: 'POST',
      body: JSON.stringify({
        event_type: 'user_message',
        task_id: taskId,
        message: '给我一个最小提示，但不要直接告诉我答案。',
        client_context: { surface: 'spatial-react-foundation' },
        use_model: true,
      }),
    })
  },
}

export const workSampleApi = {
  start() {
    return api<any>('/api/work-samples/v1/start', { method: 'POST' })
  },
  submitV1(value: WorkSampleSubmission) {
    return api<any>('/api/work-samples/v1/v1', { method: 'POST', body: JSON.stringify(value) })
  },
  submitV2(value: WorkSampleSubmission) {
    return api<any>('/api/work-samples/v1/v2', { method: 'POST', body: JSON.stringify(value) })
  },
  submitTransfer(value: WorkSampleSubmission) {
    return api<any>('/api/work-samples/v1/transfer', { method: 'POST', body: JSON.stringify(value) })
  },
}
