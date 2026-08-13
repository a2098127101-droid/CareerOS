import { Edges, Html, MeshTransmissionMaterial, RoundedBox } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import { useRef } from 'react'
import * as THREE from 'three'
import type { Alpha5Theme } from '../alpha5/ThemeSystem'
import { SHOWCASE_CLIPS, sampleTrack, smooth01 } from './ShowcaseSequenceConfig'
import { showcaseProgress, type ShowcaseRuntimeState } from './ShowcaseRuntime'

type Stage = {
  transform: number
  wings: number
  iris: number
  gantry: number
  ceiling: number
  reactor: number
}

function steadyStage(status: string): Stage {
  if (status === 'completed') return { transform: .86, wings: .9, iris: .92, gantry: .86, ceiling: .9, reactor: 1 }
  if (status === 'transfer_ready') return { transform: .64, wings: .66, iris: .72, gantry: .62, ceiling: .68, reactor: .78 }
  if (status === 'revision_required') return { transform: .44, wings: .45, iris: .52, gantry: .42, ceiling: .48, reactor: .6 }
  return { transform: .22, wings: .2, iris: .28, gantry: .18, ceiling: .22, reactor: .36 }
}

export function ControlRoomTransformation({ runtime, theme, workStatus }: { runtime: ShowcaseRuntimeState; theme: Alpha5Theme; workStatus: string }) {
  const leftWing = useRef<THREE.Group>(null)
  const rightWing = useRef<THREE.Group>(null)
  const ceiling = useRef<THREE.Group>(null)
  const iris = useRef<THREE.Group>(null)
  const gantryLeft = useRef<THREE.Group>(null)
  const gantryRight = useRef<THREE.Group>(null)
  const reactor = useRef<THREE.Group>(null)
  const petals = useRef<THREE.Group>(null)

  useFrame((state, delta) => {
    let target = steadyStage(workStatus)
    if (runtime.active && runtime.clip) {
      const clip = SHOWCASE_CLIPS[runtime.clip]
      const progress = showcaseProgress(runtime, state.clock.elapsedTime)
      const sample = sampleTrack(clip.room, progress)
      const t = smooth01(sample.t)
      target = {
        transform: THREE.MathUtils.lerp(sample.a.transform, sample.b.transform, t),
        wings: THREE.MathUtils.lerp(sample.a.wings, sample.b.wings, t),
        iris: THREE.MathUtils.lerp(sample.a.iris, sample.b.iris, t),
        gantry: THREE.MathUtils.lerp(sample.a.gantry, sample.b.gantry, t),
        ceiling: THREE.MathUtils.lerp(sample.a.ceiling, sample.b.ceiling, t),
        reactor: THREE.MathUtils.lerp(sample.a.reactor, sample.b.reactor, t),
      }
    }
    const damp = (current: number, value: number, speed = 4.2) => THREE.MathUtils.damp(current, value, speed, delta)

    if (leftWing.current) {
      leftWing.current.position.x = damp(leftWing.current.position.x, -8.45 - target.wings * 1.05)
      leftWing.current.position.z = damp(leftWing.current.position.z, -1.4 + target.wings * .7)
      leftWing.current.rotation.y = damp(leftWing.current.rotation.y, -.08 - target.wings * .32)
    }
    if (rightWing.current) {
      rightWing.current.position.x = damp(rightWing.current.position.x, 8.45 + target.wings * 1.05)
      rightWing.current.position.z = damp(rightWing.current.position.z, -1.4 + target.wings * .7)
      rightWing.current.rotation.y = damp(rightWing.current.rotation.y, .08 + target.wings * .32)
    }
    if (ceiling.current) {
      ceiling.current.position.y = damp(ceiling.current.position.y, 5.55 + target.ceiling * 1.0)
      ceiling.current.rotation.y += delta * (.035 + target.ceiling * .09)
      ceiling.current.scale.setScalar(damp(ceiling.current.scale.x, .94 + target.ceiling * .16))
    }
    if (iris.current) {
      iris.current.rotation.z += delta * (.08 + target.iris * .42)
      iris.current.scale.setScalar(damp(iris.current.scale.x, .82 + target.iris * .42))
    }
    if (gantryLeft.current) {
      gantryLeft.current.position.x = damp(gantryLeft.current.position.x, -5.5 + target.gantry * .82)
      gantryLeft.current.position.y = damp(gantryLeft.current.position.y, 2.2 + target.gantry * .6)
      gantryLeft.current.rotation.z = damp(gantryLeft.current.rotation.z, -.08 - target.gantry * .08)
    }
    if (gantryRight.current) {
      gantryRight.current.position.x = damp(gantryRight.current.position.x, 5.5 - target.gantry * .82)
      gantryRight.current.position.y = damp(gantryRight.current.position.y, 2.2 + target.gantry * .6)
      gantryRight.current.rotation.z = damp(gantryRight.current.rotation.z, .08 + target.gantry * .08)
    }
    if (reactor.current) {
      reactor.current.scale.y = damp(reactor.current.scale.y, .75 + target.reactor * .7)
      reactor.current.rotation.y += delta * (.15 + target.reactor * .48)
    }
    if (petals.current) {
      petals.current.rotation.y -= delta * (.05 + target.transform * .16)
      petals.current.scale.setScalar(damp(petals.current.scale.x, .72 + target.transform * .42))
    }
  })

  return (
    <group>
      <group ref={leftWing} position={[-8.45, 3.2, -1.4]}>
        <RoundedBox args={[.35, 5.6, 8.8]} radius={.12} smoothness={4}><meshPhysicalMaterial color="#0a151c" metalness={.9} roughness={.18} clearcoat={.75} /><Edges color={theme.accent} threshold={26} /></RoundedBox>
        <RoundedBox args={[.08, 4.7, 7.6]} radius={.05} smoothness={3} position={[.22, 0, .15]}><MeshTransmissionMaterial transmission={.9} thickness={.28} roughness={.12} chromaticAberration={.035} anisotropicBlur={.08} samples={2} resolution={128} color={theme.accent} /></RoundedBox>
      </group>
      <group ref={rightWing} position={[8.45, 3.2, -1.4]}>
        <RoundedBox args={[.35, 5.6, 8.8]} radius={.12} smoothness={4}><meshPhysicalMaterial color="#0a151c" metalness={.9} roughness={.18} clearcoat={.75} /><Edges color={theme.secondary} threshold={26} /></RoundedBox>
        <RoundedBox args={[.08, 4.7, 7.6]} radius={.05} smoothness={3} position={[-.22, 0, .15]}><MeshTransmissionMaterial transmission={.9} thickness={.28} roughness={.12} chromaticAberration={.035} anisotropicBlur={.08} samples={2} resolution={128} color={theme.secondary} /></RoundedBox>
      </group>

      <group ref={ceiling} position={[0, 5.55, .55]} rotation={[Math.PI / 2, 0, 0]}>
        {[3.2, 4.2, 5.1].map((radius, index) => <mesh key={radius} rotation={[0, 0, index * .38]}><torusGeometry args={[radius, .045 - index * .008, 10, 180]} /><meshPhysicalMaterial color={index % 2 ? theme.secondary : theme.accent} emissive={index % 2 ? theme.secondary : theme.accent} emissiveIntensity={.35 + index * .12} metalness={.68} roughness={.12} toneMapped={false} /></mesh>)}
      </group>

      <group ref={iris} position={[0, .07, .65]} rotation={[-Math.PI / 2, 0, 0]}>
        {Array.from({ length: 12 }, (_, index) => {
          const angle = index / 12 * Math.PI * 2
          return <mesh key={index} position={[Math.cos(angle) * 2.8, Math.sin(angle) * 2.8, 0]} rotation={[0, 0, angle + Math.PI / 2]}><boxGeometry args={[1.7, .055, .34]} /><meshPhysicalMaterial color="#1b2b34" emissive={index % 3 === 0 ? theme.accent : '#132029'} emissiveIntensity={index % 3 === 0 ? 1.4 : .08} metalness={.88} roughness={.18} toneMapped={index % 3 !== 0} /></mesh>
        })}
      </group>

      <group ref={gantryLeft} position={[-5.5, 2.2, 1.8]}>
        <RoundedBox args={[1.05, 4.6, .34]} radius={.1} smoothness={4}><meshPhysicalMaterial color="#101e26" metalness={.88} roughness={.17} clearcoat={.6} /><Edges color={theme.accent} threshold={24} /></RoundedBox>
        <mesh position={[.62, 0, 0]}><boxGeometry args={[.035, 3.8, .04]} /><meshBasicMaterial color={theme.accent} toneMapped={false} /></mesh>
      </group>
      <group ref={gantryRight} position={[5.5, 2.2, 1.8]}>
        <RoundedBox args={[1.05, 4.6, .34]} radius={.1} smoothness={4}><meshPhysicalMaterial color="#101e26" metalness={.88} roughness={.17} clearcoat={.6} /><Edges color={theme.secondary} threshold={24} /></RoundedBox>
        <mesh position={[-.62, 0, 0]}><boxGeometry args={[.035, 3.8, .04]} /><meshBasicMaterial color={theme.secondary} toneMapped={false} /></mesh>
      </group>

      <group ref={reactor} position={[0, 2.45, .65]}>
        <mesh><cylinderGeometry args={[.72, 1.05, 2.2, 48, 1, true]} /><meshPhysicalMaterial color="#172a31" metalness={.92} roughness={.1} clearcoat={1} transparent opacity={.36} side={THREE.DoubleSide} /></mesh>
        <mesh><cylinderGeometry args={[.46, .46, 2.5, 32, 1, true]} /><meshBasicMaterial color={theme.accent} transparent opacity={.16} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} side={THREE.DoubleSide} /></mesh>
      </group>

      <group ref={petals} position={[0, 2.45, .65]}>
        {Array.from({ length: 8 }, (_, index) => {
          const angle = index / 8 * Math.PI * 2
          return <mesh key={index} position={[Math.cos(angle) * 1.55, 0, Math.sin(angle) * 1.55]} rotation={[0, -angle, Math.PI / 2.7]}><boxGeometry args={[1.4, .08, .32]} /><meshPhysicalMaterial color="#23343d" emissive={index % 2 ? theme.secondary : theme.accent} emissiveIntensity={.32} metalness={.9} roughness={.13} clearcoat={.65} toneMapped={false} /></mesh>
        })}
      </group>

      {runtime.active && runtime.clip === 'room_transformation' && <Html transform center distanceFactor={8} position={[0, 6.25, .2]} pointerEvents="none"><div className="presentation-event-label"><span>CONTROL ROOM TRANSFORMATION</span><strong>MULTI-STAGE MECHANICAL RECONFIGURATION</strong><small>cinematic clip · server state unchanged</small></div></Html>}
    </group>
  )
}
