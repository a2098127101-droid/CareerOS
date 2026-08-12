import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ApiError, sceneApi } from '../api/client'
import type { SceneState } from '../api/types'

type SceneStateContextValue = {
  scene: SceneState | null
  loading: boolean
  refreshing: boolean
  error: string
  lastSyncedAt: string
  refresh: () => Promise<void>
}

const SceneStateContext = createContext<SceneStateContextValue | null>(null)

export function SceneStateProvider({ children }: { children: ReactNode }) {
  const [scene, setScene] = useState<SceneState | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [lastSyncedAt, setLastSyncedAt] = useState('')
  const active = useRef<AbortController | null>(null)

  const load = useCallback(async (initial = false) => {
    active.current?.abort()
    const controller = new AbortController()
    active.current = controller
    initial ? setLoading(true) : setRefreshing(true)
    try {
      const next = await sceneApi.state(controller.signal)
      if (!next.authority?.readOnly || next.authority?.clientMayPromoteCapability !== false) {
        throw new Error('SceneState authority contract is invalid')
      }
      setScene(next)
      setLastSyncedAt(next.generatedAt)
      setError('')
    } catch (value) {
      if (controller.signal.aborted) return
      setError(value instanceof ApiError || value instanceof Error ? value.message : 'SceneState 同步失败')
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    void load(true)
    const timer = window.setInterval(() => void load(false), 15000)
    const onFocus = () => void load(false)
    window.addEventListener('focus', onFocus)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
      active.current?.abort()
    }
  }, [load])

  const value = useMemo<SceneStateContextValue>(() => ({
    scene,
    loading,
    refreshing,
    error,
    lastSyncedAt,
    refresh: () => load(false),
  }), [scene, loading, refreshing, error, lastSyncedAt, load])

  return <SceneStateContext.Provider value={value}>{children}</SceneStateContext.Provider>
}

export function useSceneState() {
  const value = useContext(SceneStateContext)
  if (!value) throw new Error('useSceneState must be used inside SceneStateProvider')
  return value
}
