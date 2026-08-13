import { Line } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../../api/types'
import type { Alpha5Theme } from './ThemeSystem'

function capabilityPosition(index: number, total: number): THREE.Vector3 {
  const ring = index % 2 === 0 ? 2.45 : 1.58
  const angle = (index / Math.max(1, total)) * Math.PI * 2 + (index % 2) * .28
  return new THREE.Vector3(Math.cos(angle) * ring, 3.45 + Math.sin(index * 1.7) * .42, -5.95 + Math.sin(angle) * .78)
}

function evidencePosition(index: number): THREE.Vector3 {
  const col = index % 3
  const row = Math.floor(index / 3)
  return new THREE.Vector3(-6.0 + (col - 1) * .78, 1.1 + row * .56, -1.45)
}

function Flow({ curve, color, speed, seed }: { curve: THREE.QuadraticBezierCurve3; color: string; speed: number; seed: number }) {
  const count = 32
  const geometry = useMemo(() => {
    const value = new THREE.BufferGeometry()
    value.setAttribute('position', new THREE.BufferAttribute(new Float32Array(count * 3), 3))
    return value
  }, [])
  const material = useMemo(() => new THREE.PointsMaterial({ color, size: .065, transparent: true, opacity: .86, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }), [color])

  useFrame((state) => {
    const attribute = geometry.getAttribute('position') as THREE.BufferAttribute
    for (let i = 0; i < count; i += 1) {
      const t = (i / count + state.clock.elapsedTime * speed * .075 + seed * .137) % 1
      const point = curve.getPoint(t)
      const wave = Math.sin(t * Math.PI * 8 + state.clock.elapsedTime * 2.2 + seed) * .035
      attribute.setXYZ(i, point.x, point.y + wave, point.z)
    }
    attribute.needsUpdate = true
    material.opacity = .58 + Math.sin(state.clock.elapsedTime * 1.4 + seed) * .18
  })

  return <points geometry={geometry} material={material} frustumCulled={false} />
}

export function EvidenceFlowField({ nodes, connections, theme }: { nodes: SpatialNode[]; connections: SpatialConnection[]; theme: Alpha5Theme }) {
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const evidenceIndex = new Map(evidence.map((node, index) => [node.id, index]))
  const capabilityIndex = new Map(capabilities.map((node, index) => [node.id, index]))
  const flows = connections
    .filter((connection) => String(connection.relation || '') === 'contributes_to')
    .map((connection, index) => {
      const e = evidenceIndex.get(connection.from)
      const c = capabilityIndex.get(connection.to)
      if (e === undefined || c === undefined) return null
      const start = evidencePosition(e)
      const end = capabilityPosition(c, capabilities.length)
      const midpoint = start.clone().lerp(end, .5)
      midpoint.y += 1.4 + (index % 4) * .16
      midpoint.z += .8
      return {
        id: `${connection.from}:${connection.to}`,
        curve: new THREE.QuadraticBezierCurve3(start, midpoint, end),
        seed: index + 1,
      }
    })
    .filter((item): item is { id: string; curve: THREE.QuadraticBezierCurve3; seed: number } => Boolean(item))
    .slice(0, 20)

  return (
    <group>
      {flows.map((flow) => {
        const points = flow.curve.getPoints(36).map((p) => [p.x, p.y, p.z] as [number, number, number])
        return (
          <group key={flow.id}>
            <Line points={points} color={theme.accent} lineWidth={1.2} transparent opacity={.14 + theme.dataEnergy * .07} />
            <Line points={points} color={theme.secondary} lineWidth={.45} transparent opacity={.28 + theme.dataEnergy * .06} />
            <Flow curve={flow.curve} color={theme.accent} speed={theme.particleSpeed} seed={flow.seed} />
          </group>
        )
      })}
    </group>
  )
}
