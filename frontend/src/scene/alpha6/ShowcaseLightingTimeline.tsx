import { useFrame, useThree } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { Alpha5Theme } from '../alpha5/ThemeSystem'
import { SHOWCASE_CLIPS, sampleTrack, smooth01 } from './ShowcaseSequenceConfig'
import { showcaseProgress, type ShowcaseRuntimeState } from './ShowcaseRuntime'

export function ShowcaseLightingTimeline({ theme, runtime }: { theme: Alpha5Theme; runtime: ShowcaseRuntimeState }) {
  const { gl, scene } = useThree()
  const key = useRef<THREE.PointLight>(null)
  const accent = useRef<THREE.SpotLight>(null)
  const secondary = useRef<THREE.SpotLight>(null)
  const rimLeft = useRef<THREE.PointLight>(null)
  const rimRight = useRef<THREE.PointLight>(null)
  const floorPulse = useRef<THREE.Mesh>(null)
  const accentColor = useMemo(() => new THREE.Color(theme.accent), [theme.accent])
  const secondaryColor = useMemo(() => new THREE.Color(theme.secondary), [theme.secondary])

  useFrame((state, delta) => {
    let keyIntensity = .82
    let accentIntensity = .75
    let secondaryIntensity = .68
    let rimIntensity = .55
    let exposure = 1
    let fogBoost = .3
    let pulse = 0

    if (runtime.active && runtime.clip) {
      const clip = SHOWCASE_CLIPS[runtime.clip]
      const progress = showcaseProgress(runtime, state.clock.elapsedTime)
      const sample = sampleTrack(clip.lighting, progress)
      const t = smooth01(sample.t)
      keyIntensity = THREE.MathUtils.lerp(sample.a.keyIntensity, sample.b.keyIntensity, t)
      accentIntensity = THREE.MathUtils.lerp(sample.a.accentIntensity, sample.b.accentIntensity, t)
      secondaryIntensity = THREE.MathUtils.lerp(sample.a.secondaryIntensity, sample.b.secondaryIntensity, t)
      rimIntensity = THREE.MathUtils.lerp(sample.a.rimIntensity, sample.b.rimIntensity, t)
      exposure = THREE.MathUtils.lerp(sample.a.exposure, sample.b.exposure, t)
      fogBoost = THREE.MathUtils.lerp(sample.a.fogBoost, sample.b.fogBoost, t)
      pulse = THREE.MathUtils.lerp(sample.a.pulse, sample.b.pulse, t)
    }

    const beat = 1 + Math.sin(state.clock.elapsedTime * (2.4 + pulse * 4.2)) * .12 * pulse
    const colorT = 1 - Math.exp(-delta * 4)
    if (key.current) {
      key.current.color.lerp(accentColor, colorT)
      key.current.intensity = THREE.MathUtils.damp(key.current.intensity, 10 * keyIntensity * beat, 4, delta)
      key.current.position.x = Math.sin(state.clock.elapsedTime * .23) * 2.2
      key.current.position.z = 1.1 + Math.cos(state.clock.elapsedTime * .18) * 1.3
    }
    if (accent.current) {
      accent.current.color.lerp(accentColor, colorT)
      accent.current.intensity = THREE.MathUtils.damp(accent.current.intensity, 22 * accentIntensity * beat, 4, delta)
      accent.current.position.x = -7.2 + Math.sin(state.clock.elapsedTime * .31) * 1.2
    }
    if (secondary.current) {
      secondary.current.color.lerp(secondaryColor, colorT)
      secondary.current.intensity = THREE.MathUtils.damp(secondary.current.intensity, 20 * secondaryIntensity * beat, 4, delta)
      secondary.current.position.x = 7.2 + Math.cos(state.clock.elapsedTime * .27) * 1.2
    }
    if (rimLeft.current) {
      rimLeft.current.color.lerp(accentColor, colorT)
      rimLeft.current.intensity = THREE.MathUtils.damp(rimLeft.current.intensity, 8 * rimIntensity * beat, 4, delta)
    }
    if (rimRight.current) {
      rimRight.current.color.lerp(secondaryColor, colorT)
      rimRight.current.intensity = THREE.MathUtils.damp(rimRight.current.intensity, 8 * rimIntensity * beat, 4, delta)
    }
    if (floorPulse.current) {
      floorPulse.current.rotation.z += delta * (.12 + pulse * .55)
      const material = floorPulse.current.material as THREE.MeshBasicMaterial
      material.opacity = THREE.MathUtils.damp(material.opacity, .08 + pulse * .28, 4, delta)
      material.color.lerp(accentColor, colorT)
      floorPulse.current.scale.setScalar(1 + pulse * .08 + Math.sin(state.clock.elapsedTime * 3.1) * .018 * pulse)
    }

    gl.toneMappingExposure = THREE.MathUtils.damp(gl.toneMappingExposure, theme.exposure * exposure, 4.5, delta)
    if (scene.fog instanceof THREE.FogExp2) {
      const target = theme.fogDensity * (1 + fogBoost * .34)
      scene.fog.density = THREE.MathUtils.damp(scene.fog.density, target, 3.8, delta)
    }
  })

  return (
    <>
      <pointLight ref={key} position={[0, 6.7, 1.2]} intensity={8} color={theme.accent} distance={15} decay={2} />
      <spotLight ref={accent} position={[-7.2, 7.8, 4.5]} intensity={16} color={theme.accent} distance={20} angle={.38} penumbra={.95} />
      <spotLight ref={secondary} position={[7.2, 7.5, 4]} intensity={15} color={theme.secondary} distance={20} angle={.38} penumbra={.95} />
      <pointLight ref={rimLeft} position={[-8.5, 3.2, -5.3]} intensity={5} color={theme.accent} distance={11} decay={2} />
      <pointLight ref={rimRight} position={[8.5, 3.2, -5.3]} intensity={5} color={theme.secondary} distance={11} decay={2} />
      <mesh ref={floorPulse} position={[0, .055, .55]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[3.8, 4.0, 160]} />
        <meshBasicMaterial color={theme.accent} transparent opacity={.08} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
    </>
  )
}
