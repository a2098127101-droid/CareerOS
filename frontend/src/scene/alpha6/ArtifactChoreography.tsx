import { Html, Sparkles } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Alpha5Theme } from '../alpha5/ThemeSystem'
import { SHOWCASE_CLIPS, sampleTrack, smooth01 } from './ShowcaseSequenceConfig'
import { showcaseProgress, type ShowcaseRuntimeState } from './ShowcaseRuntime'

const PARTS = 36

function isArtifactClip(runtime: ShowcaseRuntimeState) {
  return runtime.active && Boolean(runtime.clip && [
    'artifact_destruction', 'artifact_assembly', 'server_revision', 'server_transfer', 'server_completed', 'grand_finale',
  ].includes(runtime.clip))
}

export function ArtifactChoreography({ runtime, theme }: { runtime: ShowcaseRuntimeState; theme: Alpha5Theme }) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const feedback = useRef<THREE.Group>(null)
  const body = useMemo(() => {
    const items = Array.from({ length: PARTS }, (_, index) => {
      const row = Math.floor(index / 6)
      const col = index % 6
      const assembled = new THREE.Vector3(
        3.35 + (col - 2.5) * .22,
        1.55 + (row - 2.5) * .17,
        1.75 + ((index % 3) - 1) * .07,
      )
      const angle = index * 2.399963
      const radius = 1.25 + (index % 7) * .14
      const exploded = new THREE.Vector3(
        3.35 + Math.cos(angle) * radius,
        1.6 + Math.sin(angle * .67) * (1.0 + (index % 5) * .08),
        1.75 + Math.sin(angle) * radius,
      )
      const scatter = new THREE.Vector3(
        Math.sin(index * 11.7) * .62,
        Math.cos(index * 7.1) * .54,
        Math.sin(index * 5.3) * .58,
      )
      const scale = new THREE.Vector3(.16 + (index % 3) * .025, .07 + (row % 2) * .02, .13 + (col % 2) * .02)
      return { assembled, exploded, scatter, scale, phase: angle }
    })
    return { items, matrix: new THREE.Matrix4(), quaternion: new THREE.Quaternion(), position: new THREE.Vector3(), scale: new THREE.Vector3() }
  }, [])

  useFrame((state) => {
    if (!mesh.current || !runtime.active || !runtime.clip) return
    const clip = SHOWCASE_CLIPS[runtime.clip]
    const progress = showcaseProgress(runtime, state.clock.elapsedTime)
    const sample = sampleTrack(clip.artifact, progress)
    const t = smooth01(sample.t)
    const explode = THREE.MathUtils.lerp(sample.a.explode, sample.b.explode, t)
    const assemble = THREE.MathUtils.lerp(sample.a.assemble, sample.b.assemble, t)
    const spin = THREE.MathUtils.lerp(sample.a.spin, sample.b.spin, t)
    const scatter = THREE.MathUtils.lerp(sample.a.scatter, sample.b.scatter, t)
    const feedbackAmount = THREE.MathUtils.lerp(sample.a.feedback, sample.b.feedback, t)

    body.items.forEach((item, index) => {
      body.position.copy(item.assembled).lerp(item.exploded, explode)
      body.position.addScaledVector(item.scatter, scatter * (.3 + (index % 4) * .12))
      body.position.x += Math.sin(state.clock.elapsedTime * 1.4 + item.phase) * .035 * explode
      body.position.y += Math.cos(state.clock.elapsedTime * 1.1 + item.phase) * .025 * explode
      const euler = new THREE.Euler(
        Math.sin(item.phase) * spin * 1.2,
        state.clock.elapsedTime * spin * (.18 + (index % 5) * .025) + item.phase * explode,
        Math.cos(item.phase) * spin,
      )
      body.quaternion.setFromEuler(euler)
      const settle = .72 + assemble * .28
      body.scale.copy(item.scale).multiplyScalar(settle)
      body.matrix.compose(body.position, body.quaternion, body.scale)
      mesh.current!.setMatrixAt(index, body.matrix)
    })
    mesh.current.instanceMatrix.needsUpdate = true

    if (feedback.current) {
      feedback.current.visible = feedbackAmount > .03
      feedback.current.scale.setScalar(.55 + feedbackAmount * .72 + Math.sin(state.clock.elapsedTime * 4.2) * .045 * feedbackAmount)
      feedback.current.rotation.y = state.clock.elapsedTime * (.25 + feedbackAmount * .8)
    }
  })

  if (!isArtifactClip(runtime)) return null

  return (
    <group>
      <instancedMesh ref={mesh} args={[undefined, undefined, PARTS]} castShadow>
        <boxGeometry args={[1, 1, 1]} />
        <meshPhysicalMaterial color={theme.accent} metalness={.58} roughness={.12} clearcoat={1} clearcoatRoughness={.05} emissive={theme.accent} emissiveIntensity={.22} />
      </instancedMesh>
      <group ref={feedback} position={[3.35, 1.65, 1.75]}>
        <mesh><icosahedronGeometry args={[.22, 2]} /><meshPhysicalMaterial color={theme.secondary} emissive={theme.secondary} emissiveIntensity={3.5} metalness={.4} roughness={.04} clearcoat={1} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[.42, .014, 10, 90]} /><meshBasicMaterial color={theme.secondary} transparent opacity={.68} toneMapped={false} /></mesh>
        <Sparkles count={28} scale={[1.5, 1.5, 1.5]} size={2.8} speed={.65} opacity={.8} color={theme.secondary} />
      </group>
      <Html transform center distanceFactor={7} position={[3.35, 3.15, 1.75]} pointerEvents="none">
        <div className="presentation-event-label"><span>ARTIFACT CHOREOGRAPHY</span><strong>{runtime.clip?.replaceAll('_', ' ').toUpperCase()}</strong><small>visual clip · server artifact state unchanged</small></div>
      </Html>
    </group>
  )
}
