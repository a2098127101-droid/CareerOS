import { Html } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Alpha5Theme } from './ThemeSystem'

type Mode = 'assembled' | 'exploded' | 'ghost'
type Vec3 = [number, number, number]

const COUNT = 24

function baseTarget(index: number): THREE.Vector3 {
  const col = index % 4
  const row = Math.floor(index / 4) % 3
  const layer = Math.floor(index / 12)
  return new THREE.Vector3((col - 1.5) * .34, (row - 1) * .28, (layer - .5) * .24)
}

function explodedTarget(index: number): THREE.Vector3 {
  const base = baseTarget(index)
  const angle = index * 2.3999632297
  const radius = 1.15 + (index % 5) * .14
  return base.clone().add(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(index * .93) * .72, Math.sin(angle) * radius * .72))
}

function FragmentSet({ origin, mode, color, energy = 1 }: { origin: Vec3; mode: Mode; color: string; energy?: number }) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const geometry = useMemo(() => new THREE.BoxGeometry(.28, .2, .16, 1, 1, 1), [])
  const material = useMemo(() => new THREE.MeshPhysicalMaterial({
    color,
    metalness: .68,
    roughness: .16,
    clearcoat: 1,
    clearcoatRoughness: .05,
    emissive: new THREE.Color(color),
    emissiveIntensity: .18,
  }), [color])
  const positions = useMemo(() => Array.from({ length: COUNT }, (_, i) => explodedTarget(i).multiplyScalar(.35)), [])
  const velocities = useMemo(() => Array.from({ length: COUNT }, () => new THREE.Vector3()), [])
  const dummy = useMemo(() => new THREE.Object3D(), [])

  useFrame((state, delta) => {
    if (!mesh.current) return
    const dt = Math.min(.033, delta)
    for (let i = 0; i < COUNT; i += 1) {
      const target = mode === 'assembled' ? baseTarget(i) : mode === 'exploded' ? explodedTarget(i) : explodedTarget(i).multiplyScalar(.58)
      const p = positions[i]
      const v = velocities[i]
      const spring = target.clone().sub(p).multiplyScalar(mode === 'exploded' ? 8.5 : 11.5)
      v.addScaledVector(spring, dt)
      v.multiplyScalar(Math.pow(mode === 'ghost' ? .84 : .79, dt * 60))
      p.addScaledVector(v, dt)
      const hover = Math.sin(state.clock.elapsedTime * .75 + i * .61) * .018 * energy
      dummy.position.copy(p).add(new THREE.Vector3(0, hover, 0))
      dummy.rotation.set(i * .19 + state.clock.elapsedTime * .04, i * .13, i * .07 - state.clock.elapsedTime * .025)
      const scale = mode === 'ghost' ? .72 : 1
      dummy.scale.setScalar(scale)
      dummy.updateMatrix()
      mesh.current.setMatrixAt(i, dummy.matrix)
    }
    mesh.current.instanceMatrix.needsUpdate = true
    material.emissiveIntensity = THREE.MathUtils.damp(material.emissiveIntensity, mode === 'assembled' ? .35 + energy * .22 : .12 + energy * .12, 3, delta)
    material.opacity = THREE.MathUtils.damp(material.opacity, mode === 'ghost' ? .24 : .9, 3, delta)
    material.transparent = mode === 'ghost'
  })

  useEffect(() => () => {
    geometry.dispose()
    material.dispose()
  }, [geometry, material])

  return <group position={origin}><instancedMesh ref={mesh} args={[geometry, material, COUNT]} castShadow /></group>
}

function FeedbackCore({ position, theme }: { position: Vec3; theme: Alpha5Theme }) {
  const group = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!group.current) return
    group.current.rotation.y += delta * .52
    group.current.rotation.z = Math.sin(state.clock.elapsedTime * .7) * .18
  })
  return (
    <group ref={group} position={position}>
      <mesh><icosahedronGeometry args={[.28, 2]} /><meshPhysicalMaterial color={theme.warning} emissive={theme.warning} emissiveIntensity={2.8} metalness={.42} roughness={.08} iridescence={.7} toneMapped={false} /></mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[.55, .018, 10, 90]} /><meshBasicMaterial color={theme.warning} transparent opacity={.65} toneMapped={false} /></mesh>
      <pointLight color={theme.warning} intensity={8} distance={3.5} decay={2} />
    </group>
  )
}

export function ArtifactAssembler({ status, theme }: { status: string; theme: Alpha5Theme }) {
  const show = ['revision_required', 'transfer_ready', 'completed'].includes(status)
  if (!show) return null
  const hasV2 = status === 'transfer_ready' || status === 'completed'
  const complete = status === 'completed'
  return (
    <group position={[5.3, 2.05, 2.15]}>
      <FragmentSet origin={[-1.05, 0, 0]} mode={complete ? 'ghost' : 'exploded'} color={theme.secondary} energy={theme.dataEnergy} />
      <FeedbackCore position={[0, .05, 0]} theme={theme} />
      {hasV2 && <FragmentSet origin={[1.05, 0, 0]} mode="assembled" color={theme.accent} energy={theme.dataEnergy} />}
      {complete && (
        <group position={[2.05, .15, 0]}>
          <mesh><octahedronGeometry args={[.28, 1]} /><meshPhysicalMaterial color="#eef7ff" emissive={theme.accent} emissiveIntensity={2.2} metalness={.62} roughness={.08} clearcoat={1} toneMapped={false} /></mesh>
          <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[.52, .012, 10, 80]} /><meshBasicMaterial color={theme.accent} transparent opacity={.52} toneMapped={false} /></mesh>
        </group>
      )}
      <Html transform center distanceFactor={7.2} position={[0, 1.45, .2]} pointerEvents="none">
        <div className="presentation-event-label">
          <span>ARTIFACT PHYSICS / SERVER STAGE</span>
          <strong>{status === 'revision_required' ? 'V1 DISASSEMBLED FOR FEEDBACK' : status === 'transfer_ready' ? 'V1 → V2 REASSEMBLY' : 'V2 + TRANSFER ASSEMBLED'}</strong>
          <small>animation only · artifact truth remains server-side</small>
        </div>
      </Html>
    </group>
  )
}
