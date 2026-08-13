import { useThree } from '@react-three/fiber'
import { useEffect } from 'react'
import type { QualityTier } from './QualitySystem'

export function ContextRecoveryGuard({ onTier, onLost }: {
  onTier: (tier: QualityTier) => void
  onLost?: () => void
}) {
  const { gl } = useThree()

  useEffect(() => {
    const canvas = gl.domElement
    const handleLost = (event: Event) => {
      event.preventDefault()
      onTier('safe')
      onLost?.()
      try {
        window.sessionStorage.setItem('stepin.spatial.quality.auto', 'safe')
        window.sessionStorage.setItem('stepin.spatial.context_lost', String(Date.now()))
      } catch {
        // Storage can be unavailable in hardened WebView environments.
      }
    }
    const handleRestored = () => {
      onTier('safe')
      try {
        window.sessionStorage.setItem('stepin.spatial.quality.auto', 'safe')
      } catch {
        // Keep runtime recovery independent from storage availability.
      }
    }

    canvas.addEventListener('webglcontextlost', handleLost, false)
    canvas.addEventListener('webglcontextrestored', handleRestored, false)
    return () => {
      canvas.removeEventListener('webglcontextlost', handleLost, false)
      canvas.removeEventListener('webglcontextrestored', handleRestored, false)
    }
  }, [gl, onLost, onTier])

  return null
}
