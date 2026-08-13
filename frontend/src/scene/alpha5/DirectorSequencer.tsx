import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { SpatialNode } from '../../api/types'
import type { Alpha5Event } from './ThemeSystem'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Shot = {
  at: number
  position: Vec3
  target: Vec3
  fov: number
}

type Sequence = {
  duration: number
  shots: Shot[]
}

const BASE_SHOTS: Record<Focus, Shot> = {
  hub: { at: 0, position: [0, 7.2, 18.4], target: [0, 2.15, -.2], fov: 40 },
  foundation: { at: 0, position: [-4.95, 4.1, 7.4], target: [-2.95, 1.45, -.7], fov: 36 },
  'work-sample': { at: 0, position: [5.0, 4.0, 7.25], target: [2.95, 1.45, -.7], fov: 36 },
}

const EVENT_SEQUENCES: Record<Alpha5Event['kind'], Sequence> = {
  evidence_verified: {
    duration: 5.2,
    shots: [
      { at: 0, position: [-1.2, 6.0, 12.2], target: [-5.8, 2.4, -2.0], fov: 38 },
      { at: 1.25, position: [-7.4, 3.2, 2.1], target: [-6.0, 2.35, -2.05], fov: 31 },
      { at: 3.05, position: [-5.15, 4.6, -1.1], target: [-5.95, 2.4, -2.05], fov: 27 },
      { at: 4.25, position: [-1.0, 6.2, 11.8], target: [-3.2, 2.6, -1.6], fov: 37 },
    ],
  },
  capability_awakened: {
    duration: 6.6,
    shots: [
      { at: 0, position: [0, 6.7, 13.2], target: [0, 3.35, -6.05], fov: 38 },
      { at: 1.2, position: [4.1, 4.9, -1.9], target: [0, 3.3, -6.1], fov: 30 },
      { at: 2.85, position: [0, 3.8, -2.8], target: [0, 3.4, -6.15], fov: 24 },
      { at: 4.35, position: [-4.1, 5.2, -2.0], target: [0, 3.4, -6.1], fov: 29 },
      { at: 5.45, position: [0, 6.6, 12.7], target: [0, 2.8, -4.7], fov: 37 },
    ],
  },
  work_sample_stage: {
    duration: 5.6,
    shots: [
      { at: 0, position: [6.6, 4.6, 8.5], target: [4.9, 2.1, 2.0], fov: 37 },
      { at: 1.2, position: [7.5, 3.6, 3.4], target: [5.15, 2.0, 1.9], fov: 30 },
      { at: 2.85, position: [4.4, 3.0, 4.5], target: [5.0, 1.9, 1.75], fov: 27 },
      { at: 4.4, position: [5.0, 4.2, 7.2], target: [3.0, 1.5, -.6], fov: 35 },
    ],
  },
}

function smooth(value: number) {
  const x = THREE.MathUtils.clamp(value, 0, 1)
  return x * x * (3 - 2 * x)
}

function interpolateShot(sequence: Sequence, time: number) {
  const shots = sequence.shots
  if (time <= shots[0].at) return shots[0]
  for (let i = 0; i < shots.length - 1; i += 1) {
    const a = shots[i]
    const b = shots[i + 1]
    if (time <= b.at) {
      const p = smooth((time - a.at) / Math.max(.001, b.at - a.at))
      return {
        at: time,
        position: [
          THREE.MathUtils.lerp(a.position[0], b.position[0], p),
          THREE.MathUtils.lerp(a.position[1], b.position[1], p),
          THREE.MathUtils.lerp(a.position[2], b.position[2], p),
        ] as Vec3,
        target: [
          THREE.MathUtils.lerp(a.target[0], b.target[0], p),
          THREE.MathUtils.lerp(a.target[1], b.target[1], p),
          THREE.MathUtils.lerp(a.target[2], b.target[2], p),
        ] as Vec3,
        fov: THREE.MathUtils.lerp(a.fov, b.fov, p),
      }
    }
  }
  return shots[shots.length - 1]
}

export function DirectorSequencer({ focus, event }: { focus: Focus; event: Alpha5Event | null; nodes: SpatialNode[] }) {
  const { camera } = useThree()
  const target = useRef(new THREE.Vector3(...BASE_SHOTS[focus].target))
  const activeEvent = useRef<string>('')
  const sequenceStart = useRef(0)
  const returning = useRef(false)
  const desiredFocus = useMemo(() => BASE_SHOTS[focus], [focus])

  useEffect(() => {
    if (!event || event.id === activeEvent.current) return
    activeEvent.current = event.id
    sequenceStart.current = performance.now() / 1000
    returning.current = false
  }, [event])

  useFrame((_, delta) => {
    const perspective = camera as THREE.PerspectiveCamera
    let shot = desiredFocus
    const active = event && activeEvent.current === event.id
    if (active) {
      const sequence = EVENT_SEQUENCES[event.kind]
      const elapsed = performance.now() / 1000 - sequenceStart.current
      if (elapsed <= sequence.duration) {
        shot = interpolateShot(sequence, elapsed)
      } else {
        returning.current = true
      }
    }

    const speed = returning.current || !active ? 2.35 : 7.5
    const k = 1 - Math.exp(-delta * speed)
    camera.position.lerp(new THREE.Vector3(...shot.position), k)
    target.current.lerp(new THREE.Vector3(...shot.target), k)
    camera.lookAt(target.current)
    perspective.fov = THREE.MathUtils.damp(perspective.fov, shot.fov, speed, delta)
    perspective.updateProjectionMatrix()

    if (returning.current) {
      const distance = camera.position.distanceTo(new THREE.Vector3(...desiredFocus.position))
      if (distance < .06) {
        returning.current = false
        activeEvent.current = ''
      }
    }
  }, -2)

  return null
}
