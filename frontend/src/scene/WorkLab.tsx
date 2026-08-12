import {
  CameraControls,
  ContactShadows,
  Edges,
  Float,
  Html,
  Line,
  MeshReflectorMaterial,
  RoundedBox,
  Sparkles,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, ChromaticAberration, EffectComposer, Vignette } from '@react-three/postprocessing'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'

type Focus = 'hub' | 'foundation' | 'work-sample'

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

type Vec3 = [number, number, number]

const palette = {
  background: '#070a0f',
  floor: '#0d1218',
  graphite: '#111820',
  graphite2: '#18212b',
  steel: '#26323d',
  warmMetal: '#715f4f',
  wood: '#6d5744',
  bone: '#ded8ce',
  cyan: '#76e1da',
  cyanSoft: '#4ca8aa',
  amber: '#e8b56f',
  amberSoft: '#9c6d3e',
  green: '#79e2b5',
  rose: '#d98b80',
  blue: '#7ba7d7',
}

const capabilityColors: Record<string, string> = {
  unobserved: '#3b4651',
  signal: '#8d9ba9',
  evidence: '#e0b768',
  verified_evidence: '#7ce0b8',
}

function SceneLabel({ children, className = '' }: { children: string; className?: string }) {
  return (
    <Html center transform distanceFactor={8.2}>
      <div className={`scene-label ${className}`}>{children}</div>
    </Html>
  )
}

function createWoodTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 768
  canvas.height = 256
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height)
  gradient.addColorStop(0, '#806a54')
  gradient.addColorStop(0.46, '#66513f')
  gradient.addColorStop(1, '#554333')
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  for (let y = 0; y < canvas.height; y += 4) {
    const wobble = Math.sin(y * 0.16) * 8 + Math.sin(y * 0.043) * 17
    ctx.strokeStyle = `rgba(32, 20, 13, ${0.05 + (y % 17) / 480})`
    ctx.lineWidth = y % 12 === 0 ? 1.35 : 0.65
    ctx.beginPath()
    for (let x = -20; x < canvas.width + 20; x += 12) {
      const yy = y + Math.sin((x + wobble) * 0.028) * 1.7
      if (x === -20) ctx.moveTo(x, yy)
      else ctx.lineTo(x, yy)
    }
    ctx.stroke()
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(2.2, 1)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 8
  return texture
}

function createFloorTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  ctx.fillStyle = '#0d1218'
  ctx.fillRect(0, 0, 512, 512)
  const image = ctx.getImageData(0, 0, 512, 512)
  for (let i = 0; i < image.data.length; i += 4) {
    const noise = Math.floor(Math.random() * 8)
    image.data[i] += noise
    image.data[i + 1] += noise
    image.data[i + 2] += noise
  }
  ctx.putImageData(image, 0, 0)
  ctx.strokeStyle = 'rgba(124, 148, 165, .075)'
  ctx.lineWidth = 1
  for (let i = 0; i <= 512; i += 64) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 512); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(512, i); ctx.stroke()
  }
  ctx.strokeStyle = 'rgba(118, 225, 218, .05)'
  ctx.lineWidth = 2
  for (let i = 0; i <= 512; i += 256) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 512); ctx.stroke()
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(512, i); ctx.stroke()
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(5, 4)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 8
  return texture
}

function useProceduralTextures() {
  const textures = useMemo(() => ({ wood: createWoodTexture(), floor: createFloorTexture() }), [])
  useEffect(() => () => {
    textures.wood.dispose()
    textures.floor.dispose()
  }, [textures])
  return textures
}

function LightBar({ position, scale, color = palette.cyan, intensity = 2.1 }: { position: Vec3; scale: Vec3; color?: string; intensity?: number }) {
  return (
    <mesh position={position} scale={scale}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={intensity} toneMapped={false} />
    </mesh>
  )
}

function ArchitecturalShell({ floorTexture }: { floorTexture: THREE.Texture }) {
  const ribs = Array.from({ length: 9 }, (_, index) => -8 + index * 2)
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[25, 20]} />
        <MeshReflectorMaterial
          map={floorTexture}
          color={palette.floor}
          roughness={0.78}
          metalness={0.24}
          blur={[280, 90]}
          mixBlur={0.9}
          mixStrength={16}
          mirror={0.24}
          resolution={512}
          depthScale={0.22}
          minDepthThreshold={0.38}
          maxDepthThreshold={1.5}
        />
      </mesh>

      <RoundedBox args={[17.4, 6.8, 0.34]} radius={0.18} smoothness={5} position={[0, 3.35, -7.05]} receiveShadow>
        <meshPhysicalMaterial color="#0b1117" roughness={0.48} metalness={0.42} clearcoat={0.22} />
      </RoundedBox>
      <RoundedBox args={[13.9, 5.35, 0.08]} radius={0.1} smoothness={4} position={[0, 3.18, -6.84]}>
        <meshPhysicalMaterial color="#101a23" roughness={0.28} metalness={0.36} clearcoat={0.58} clearcoatRoughness={0.2} />
      </RoundedBox>
      <mesh position={[0, 3.15, -6.72]}>
        <planeGeometry args={[12.8, 4.45]} />
        <meshBasicMaterial color="#10202a" transparent opacity={0.42} toneMapped={false} />
      </mesh>

      <RoundedBox args={[0.22, 6.3, 15.2]} radius={0.1} smoothness={4} position={[-8.65, 3.15, -0.15]} receiveShadow>
        <meshStandardMaterial color="#0e151c" roughness={0.65} metalness={0.34} />
      </RoundedBox>
      <RoundedBox args={[0.22, 6.3, 15.2]} radius={0.1} smoothness={4} position={[8.65, 3.15, -0.15]} receiveShadow>
        <meshStandardMaterial color="#0e151c" roughness={0.65} metalness={0.34} />
      </RoundedBox>

      {ribs.map((z) => (
        <group key={z} position={[0, 6.25, z * 0.78]}>
          <RoundedBox args={[17.1, 0.13, 0.16]} radius={0.06} smoothness={3}>
            <meshStandardMaterial color="#23303b" metalness={0.72} roughness={0.28} />
          </RoundedBox>
          <LightBar position={[0, -0.08, 0.11]} scale={[12.8, 0.018, 0.03]} color={z % 4 === 0 ? palette.amber : palette.cyan} intensity={1.5} />
        </group>
      ))}

      <mesh position={[0, 3.1, -6.58]}>
        <torusGeometry args={[5.35, 0.055, 18, 160]} />
        <meshStandardMaterial color={palette.cyan} emissive={palette.cyan} emissiveIntensity={2.8} toneMapped={false} transparent opacity={0.42} />
      </mesh>
      <mesh position={[0, 3.1, -6.56]} scale={[1.13, 1.13, 1]}>
        <torusGeometry args={[5.35, 0.018, 12, 160]} />
        <meshBasicMaterial color={palette.amber} transparent opacity={0.24} toneMapped={false} />
      </mesh>

      <group position={[-7.9, 2.8, -1.4]}>
        {Array.from({ length: 7 }, (_, i) => (
          <LightBar key={i} position={[0, -1.9 + i * 0.64, 0]} scale={[0.025, 0.42, 4.7]} color={i % 3 === 0 ? palette.amber : '#40566a'} intensity={i % 3 === 0 ? 1.4 : 0.35} />
        ))}
      </group>
      <group position={[7.9, 2.8, -1.4]}>
        {Array.from({ length: 7 }, (_, i) => (
          <LightBar key={i} position={[0, -1.9 + i * 0.64, 0]} scale={[0.025, 0.42, 4.7]} color={i % 3 === 0 ? palette.cyan : '#40566a'} intensity={i % 3 === 0 ? 1.4 : 0.35} />
        ))}
      </group>

      <ContactShadows position={[0, 0.025, 0]} opacity={0.52} scale={18} blur={2.3} far={7.2} resolution={512} />
    </group>
  )
}

function StatusGlass({ label, locked, accent }: { label: string; locked: boolean; accent: string }) {
  return (
    <Float speed={1.05} rotationIntensity={0.025} floatIntensity={0.08}>
      <group position={[0, 2.48, -0.18]}>
        <RoundedBox args={[1.86, 0.42, 0.045]} radius={0.08} smoothness={5}>
          <meshPhysicalMaterial
            color="#14202a"
            metalness={0.18}
            roughness={0.08}
            transparent
            opacity={0.76}
            clearcoat={1}
            clearcoatRoughness={0.08}
          />
          <Edges color={locked ? '#48535e' : accent} threshold={15} />
        </RoundedBox>
        <group position={[0, 0, 0.05]}><SceneLabel className={locked ? 'muted workstation-label' : 'workstation-label'}>{label}</SceneLabel></group>
      </group>
    </Float>
  )
}

function Workstation({
  node,
  position,
  accent,
  woodTexture,
  onClick,
}: {
  node?: SpatialNode
  position: Vec3
  accent: string
  woodTexture: THREE.Texture
  onClick: () => void
}) {
  const locked = node?.state === 'locked'
  const activeAccent = locked ? '#53606b' : accent
  const stateLabel = locked ? 'LOCKED BY SERVER' : 'READY · SERVER STATE'
  return (
    <group position={position} onClick={(event) => { event.stopPropagation(); onClick() }}>
      <spotLight position={[0, 4.5, 1.2]} target-position={[0, 0.8, 0]} color={activeAccent} intensity={locked ? 8 : 22} distance={8.5} angle={0.52} penumbra={0.88} castShadow />

      <RoundedBox args={[3.48, 0.28, 2.42]} radius={0.16} smoothness={5} position={[0, 0.14, 0]} castShadow receiveShadow>
        <meshPhysicalMaterial color="#11171d" roughness={0.24} metalness={0.72} clearcoat={0.45} clearcoatRoughness={0.2} />
        <Edges color="#31404c" threshold={20} />
      </RoundedBox>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.292, 0]}>
        <ringGeometry args={[1.02, 1.34, 96]} />
        <meshBasicMaterial color={activeAccent} transparent opacity={locked ? 0.08 : 0.23} toneMapped={false} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.296, 0]}>
        <ringGeometry args={[1.52, 1.55, 96]} />
        <meshBasicMaterial color={activeAccent} transparent opacity={locked ? 0.04 : 0.38} toneMapped={false} />
      </mesh>

      <RoundedBox args={[2.88, 0.16, 1.48]} radius={0.085} smoothness={6} position={[0, 0.88, -0.03]} castShadow receiveShadow>
        <meshPhysicalMaterial map={woodTexture} color={locked ? '#4c4e4f' : '#78624f'} roughness={0.38} metalness={0.08} clearcoat={0.42} clearcoatRoughness={0.28} />
      </RoundedBox>
      <RoundedBox args={[0.17, 1.25, 1.12]} radius={0.055} smoothness={4} position={[-1.22, 0.56, -0.02]} castShadow>
        <meshStandardMaterial color="#202932" metalness={0.72} roughness={0.3} />
      </RoundedBox>
      <RoundedBox args={[0.17, 1.25, 1.12]} radius={0.055} smoothness={4} position={[1.22, 0.56, -0.02]} castShadow>
        <meshStandardMaterial color="#202932" metalness={0.72} roughness={0.3} />
      </RoundedBox>

      <RoundedBox args={[1.92, 1.22, 0.12]} radius={0.075} smoothness={6} position={[0, 1.62, -0.39]} castShadow>
        <meshPhysicalMaterial color="#0a0f14" metalness={0.78} roughness={0.2} clearcoat={0.72} clearcoatRoughness={0.12} />
        <Edges color="#3b4a56" threshold={24} />
      </RoundedBox>
      <RoundedBox args={[1.71, 1.01, 0.035]} radius={0.055} smoothness={5} position={[0, 1.62, -0.318]}>
        <meshPhysicalMaterial
          color="#071216"
          emissive={activeAccent}
          emissiveIntensity={locked ? 0.1 : 0.58}
          roughness={0.16}
          metalness={0.32}
          clearcoat={0.82}
          clearcoatRoughness={0.08}
        />
      </RoundedBox>
      <group position={[0, 1.64, -0.286]}>
        <Html transform distanceFactor={6.6} pointerEvents="none">
          <div className={`monitor-ui ${locked ? 'locked' : ''}`}>
            <div className="monitor-ui-top"><span>STEPIN / WORK LAB</span><b>{stateLabel}</b></div>
            <div className="monitor-ui-scan"><i /><i /><i /><i /></div>
            <strong>{node?.label || 'Workstation'}</strong>
            <small>SceneState authority · read only</small>
          </div>
        </Html>
      </group>
      <RoundedBox args={[0.14, 0.5, 0.13]} radius={0.035} smoothness={4} position={[0, 1.03, -0.39]} castShadow>
        <meshStandardMaterial color="#2a3540" metalness={0.78} roughness={0.22} />
      </RoundedBox>
      <RoundedBox args={[0.72, 0.055, 0.42]} radius={0.035} smoothness={4} position={[0, 0.94, -0.36]} castShadow>
        <meshStandardMaterial color="#29343d" metalness={0.72} roughness={0.28} />
      </RoundedBox>

      <RoundedBox args={[1.1, 0.055, 0.38]} radius={0.035} smoothness={4} position={[-0.36, 1.0, 0.34]} rotation={[-0.08, 0, 0]} castShadow>
        <meshPhysicalMaterial color="#171d22" roughness={0.3} metalness={0.58} clearcoat={0.38} />
        <Edges color="#465560" threshold={30} />
      </RoundedBox>
      {Array.from({ length: 7 }, (_, index) => (
        <LightBar key={index} position={[-0.77 + index * 0.135, 1.036, 0.22]} scale={[0.045, 0.006, 0.13]} color={index < 4 ? activeAccent : '#3f4a52'} intensity={index < 4 ? 1.1 : 0.15} />
      ))}
      <RoundedBox args={[0.42, 0.045, 0.31]} radius={0.045} smoothness={5} position={[0.76, 0.99, 0.34]}>
        <meshPhysicalMaterial color="#161d23" metalness={0.42} roughness={0.26} clearcoat={0.62} />
      </RoundedBox>

      <group position={[-1.35, 1.17, 0.43]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.12, 0.12, 0.22, 32]} />
          <meshPhysicalMaterial color="#202b33" metalness={0.75} roughness={0.18} clearcoat={0.55} />
        </mesh>
        <mesh position={[0, 0.13, 0]}>
          <sphereGeometry args={[0.075, 24, 24]} />
          <meshStandardMaterial color={activeAccent} emissive={activeAccent} emissiveIntensity={1.8} toneMapped={false} />
        </mesh>
      </group>

      <StatusGlass label={node?.label || 'Workstation'} locked={locked} accent={activeAccent} />
    </group>
  )
}

function EvidenceCapsule({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
  const accent = verified ? palette.green : palette.amber
  return (
    <Float speed={0.75 + Math.abs(position[0]) * 0.06} rotationIntensity={0.025} floatIntensity={0.08}>
      <group position={position} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
        <RoundedBox args={[0.62, 0.36, 0.16]} radius={0.055} smoothness={5}>
          <meshPhysicalMaterial color="#19232b" metalness={0.36} roughness={0.2} clearcoat={0.85} clearcoatRoughness={0.1} />
          <Edges color={accent} threshold={22} />
        </RoundedBox>
        <RoundedBox args={[0.5, 0.245, 0.022]} radius={0.025} smoothness={4} position={[0, 0, 0.1]}>
          <meshStandardMaterial color={verified ? '#18332a' : '#33261c'} emissive={accent} emissiveIntensity={verified ? 0.72 : 0.2} roughness={0.42} />
        </RoundedBox>
        <mesh position={[0.22, 0.115, 0.126]}>
          <sphereGeometry args={[0.026, 16, 16]} />
          <meshBasicMaterial color={accent} toneMapped={false} />
        </mesh>
      </group>
    </Float>
  )
}

function EvidenceVault({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-5.85, 0, -2.0]}>
      <RoundedBox args={[3.1, 4.45, 0.48]} radius={0.16} smoothness={6} position={[0, 2.24, 0]} castShadow receiveShadow>
        <meshPhysicalMaterial color="#0d141b" metalness={0.52} roughness={0.24} clearcoat={0.5} clearcoatRoughness={0.24} />
        <Edges color="#2e3b46" threshold={22} />
      </RoundedBox>
      <RoundedBox args={[2.72, 3.84, 0.08]} radius={0.08} smoothness={5} position={[0, 2.25, 0.29]}>
        <meshPhysicalMaterial color="#111f27" transparent opacity={0.78} metalness={0.18} roughness={0.08} clearcoat={1} />
      </RoundedBox>
      {Array.from({ length: 5 }, (_, index) => (
        <group key={index} position={[0, 0.73 + index * 0.72, 0.42]}>
          <RoundedBox args={[2.52, 0.07, 0.34]} radius={0.025} smoothness={3}>
            <meshStandardMaterial color="#34404a" metalness={0.78} roughness={0.24} />
          </RoundedBox>
          <LightBar position={[0, 0.035, 0.17]} scale={[2.16, 0.014, 0.018]} color={index === 4 ? palette.green : palette.amber} intensity={0.9} />
        </group>
      ))}
      {nodes.slice(0, 15).map((node, index) => {
        const column = index % 3
        const row = Math.floor(index / 3)
        return <EvidenceCapsule key={node.id} node={node} position={[-0.83 + column * 0.83, 0.92 + row * 0.72, 0.61]} onInspect={onInspect} />
      })}
      <group position={[0, 4.82, 0.3]}><SceneLabel className="zone-label">EVIDENCE VAULT · SERVER RECORDS</SceneLabel></group>
      <LightBar position={[0, 4.46, 0.3]} scale={[1.9, 0.025, 0.03]} color={palette.amber} intensity={1.8} />
    </group>
  )
}

function ProjectForge({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const ringRef = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (ringRef.current) ringRef.current.rotation.y += delta * 0.09
  })
  return (
    <group position={[5.65, 0, -2.15]}>
      <mesh position={[0, 0.48, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.78, 1.96, 0.55, 64]} />
        <meshPhysicalMaterial color="#10171e" metalness={0.68} roughness={0.22} clearcoat={0.52} clearcoatRoughness={0.18} />
      </mesh>
      <mesh position={[0, 0.79, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[1.64, 1.64, 0.11, 64]} />
        <meshPhysicalMaterial color="#5b4939" metalness={0.14} roughness={0.4} clearcoat={0.46} />
      </mesh>
      <mesh position={[0, 0.86, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.7, 1.46, 96]} />
        <meshStandardMaterial color="#182630" emissive={palette.blue} emissiveIntensity={0.38} metalness={0.44} roughness={0.3} />
      </mesh>
      <group ref={ringRef} position={[0, 1.04, 0]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[1.22, 0.018, 12, 96]} />
          <meshBasicMaterial color={palette.cyan} transparent opacity={0.48} toneMapped={false} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]} scale={[0.76, 0.76, 0.76]}>
          <torusGeometry args={[1.22, 0.012, 10, 96]} />
          <meshBasicMaterial color={palette.amber} transparent opacity={0.42} toneMapped={false} />
        </mesh>
      </group>
      {nodes.slice(0, 10).map((node, index) => {
        const angle = (index / Math.max(1, Math.min(nodes.length, 10))) * Math.PI * 2
        const radius = 0.7 + (index % 2) * 0.28
        const y = 1.12 + (index % 3) * 0.12
        return (
          <Float key={node.id} speed={0.8 + index * 0.03} rotationIntensity={0.018} floatIntensity={0.08}>
            <group position={[Math.cos(angle) * radius, y, Math.sin(angle) * radius]} rotation={[0, -angle + Math.PI / 2, 0]} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
              <RoundedBox args={[0.58, 0.055, 0.84]} radius={0.035} smoothness={4}>
                <meshPhysicalMaterial
                  color={node.kind === 'artifact' ? '#8d7558' : '#526d85'}
                  metalness={0.28}
                  roughness={0.3}
                  clearcoat={0.65}
                  clearcoatRoughness={0.18}
                />
                <Edges color={node.kind === 'artifact' ? palette.amber : palette.blue} threshold={24} />
              </RoundedBox>
              <LightBar position={[0, 0.038, -0.28]} scale={[0.34, 0.009, 0.018]} color={node.kind === 'artifact' ? palette.amber : palette.blue} intensity={1.1} />
            </group>
          </Float>
        )
      })}
      <group position={[0, 2.1, 0]}><SceneLabel className="zone-label">PROJECT FORGE · VERSIONS</SceneLabel></group>
    </group>
  )
}

function CapabilityNode({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  const color = capabilityColors[level] || capabilityColors.unobserved
  const scale = level === 'verified_evidence' ? 0.32 : level === 'evidence' ? 0.285 : level === 'signal' ? 0.245 : 0.19
  const emissive = level === 'verified_evidence' ? 2.4 : level === 'evidence' ? 1.25 : level === 'signal' ? 0.42 : 0.08
  return (
    <Float speed={0.72 + position[0] * 0.03} rotationIntensity={0.04} floatIntensity={0.12}>
      <group position={position} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
        <mesh>
          <sphereGeometry args={[scale, 48, 48]} />
          <meshPhysicalMaterial
            color={color}
            emissive={color}
            emissiveIntensity={emissive}
            roughness={0.16}
            metalness={0.42}
            clearcoat={1}
            clearcoatRoughness={0.08}
            iridescence={level === 'verified_evidence' ? 0.9 : 0.18}
            iridescenceIOR={1.3}
          />
        </mesh>
        <mesh rotation={[0, 0, Math.PI / 4]}>
          <torusGeometry args={[scale * 1.58, 0.015, 10, 72]} />
          <meshBasicMaterial color={color} transparent opacity={level === 'unobserved' ? 0.12 : 0.48} toneMapped={false} />
        </mesh>
        <mesh rotation={[Math.PI / 2.6, 0, -Math.PI / 5]}>
          <torusGeometry args={[scale * 1.92, 0.008, 10, 72]} />
          <meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? 0.4 : 0.13} toneMapped={false} />
        </mesh>
        <mesh position={[0, 0, -0.03]}>
          <ringGeometry args={[scale * 2.25, scale * 2.42, 72]} />
          <meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? 0.18 : 0.05} side={THREE.DoubleSide} toneMapped={false} />
        </mesh>
        <group position={[0, -scale * 2.25, 0]}><SceneLabel className="capability-label">{node.label}</SceneLabel></group>
      </group>
    </Float>
  )
}

function capabilityLayout(index: number): Vec3 {
  const ring = index < 5 ? 0 : 1
  const local = index % 5
  const angle = (local / 5) * Math.PI * 2 - Math.PI / 2 + ring * 0.22
  const rx = ring === 0 ? 2.1 : 3.25
  const ry = ring === 0 ? 1.05 : 1.55
  return [Math.cos(angle) * rx, Math.sin(angle) * ry, 0]
}

function CapabilityConstellation({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const frameRef = useRef<THREE.Group>(null)
  useFrame((state) => {
    if (frameRef.current) frameRef.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.14) * 0.012
  })
  const points = nodes.slice(0, 10).map((_, index) => capabilityLayout(index))
  return (
    <group ref={frameRef} position={[0, 3.25, -6.37]}>
      <mesh position={[0, 0, -0.08]}>
        <circleGeometry args={[4.28, 96]} />
        <meshBasicMaterial color="#09141a" transparent opacity={0.62} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, -0.04]}>
        <ringGeometry args={[3.9, 4.0, 128]} />
        <meshBasicMaterial color={palette.cyan} transparent opacity={0.17} toneMapped={false} />
      </mesh>
      <mesh position={[0, 0, -0.03]} scale={[0.76, 0.76, 1]}>
        <ringGeometry args={[3.9, 4.0, 128]} />
        <meshBasicMaterial color={palette.amber} transparent opacity={0.12} toneMapped={false} />
      </mesh>
      {nodes.slice(0, 10).map((node, index) => (
        <CapabilityNode key={node.id} node={node} position={points[index]} onInspect={onInspect} />
      ))}
      <mesh position={[0, 0, 0.02]}>
        <sphereGeometry args={[0.16, 32, 32]} />
        <meshStandardMaterial color="#dbe6e3" emissive={palette.cyan} emissiveIntensity={1.4} toneMapped={false} />
      </mesh>
      {points.map((point, index) => (
        <Line key={index} points={[[0, 0, 0], point]} color={index % 2 === 0 ? '#527277' : '#6e6255'} lineWidth={0.55} transparent opacity={0.17} />
      ))}
      <group position={[0, 2.45, 0.1]}><SceneLabel className="zone-label">CAPABILITY CONSTELLATION · SERVER VERIFIED</SceneLabel></group>
    </group>
  )
}

function TrajectoryRibbon({ nodes }: { nodes: SpatialNode[] }) {
  const latest = nodes.slice(-24)
  const points = latest.map((_, index) => [index * 0.34, Math.sin(index * 0.72) * 0.07, Math.cos(index * 0.42) * 0.14] as Vec3)
  return (
    <group position={[-3.95, 0.34, 3.1]}>
      <RoundedBox args={[8.05, 0.22, 0.74]} radius={0.12} smoothness={5} position={[3.95, -0.16, 0]} receiveShadow>
        <meshPhysicalMaterial color="#0e151c" metalness={0.48} roughness={0.28} clearcoat={0.42} />
        <Edges color="#263540" threshold={30} />
      </RoundedBox>
      {points.length > 1 && <Line points={points} color={palette.cyan} lineWidth={1.1} transparent opacity={0.32} />}
      {latest.map((node, index) => {
        const color = node.state === 'failure' ? palette.rose : node.state === 'success' ? palette.green : '#758696'
        return (
          <Float key={node.id} speed={0.68} rotationIntensity={0} floatIntensity={0.045}>
            <mesh position={points[index]}>
              <sphereGeometry args={[node.state === 'failure' ? 0.09 : node.state === 'success' ? 0.075 : 0.055, 24, 24]} />
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={node.state === 'success' ? 1.2 : 0.5} toneMapped={false} />
            </mesh>
          </Float>
        )
      })}
      <group position={[4.0, 0.3, 0]}><SceneLabel className="trajectory-label">TRAJECTORY · IMMUTABLE EVENT LEDGER</SceneLabel></group>
    </group>
  )
}

function semanticNodePositions(nodes: SpatialNode[]) {
  const map = new Map<string, Vec3>()
  const evidence = nodes.filter((node) => node.kind === 'evidence').slice(0, 15)
  evidence.forEach((node, index) => {
    const column = index % 3
    const row = Math.floor(index / 3)
    map.set(node.id, [-5.85 - 0.83 + column * 0.83, 0.92 + row * 0.72, -2.0 + 0.61])
  })

  const forge = nodes.filter((node) => node.kind === 'project' || node.kind === 'artifact').slice(0, 10)
  forge.forEach((node, index) => {
    const angle = (index / Math.max(1, forge.length)) * Math.PI * 2
    const radius = 0.7 + (index % 2) * 0.28
    const y = 1.12 + (index % 3) * 0.12
    map.set(node.id, [5.65 + Math.cos(angle) * radius, y, -2.15 + Math.sin(angle) * radius])
  })

  const capabilities = nodes.filter((node) => node.kind === 'capability').slice(0, 10)
  capabilities.forEach((node, index) => {
    const local = capabilityLayout(index)
    map.set(node.id, [local[0], 3.25 + local[1], -6.37 + local[2]])
  })
  return map
}

function SemanticBeam({ from, to, relation, phase }: { from: Vec3; to: Vec3; relation: string; phase: number }) {
  const pulse = useRef<THREE.Mesh>(null)
  const color = relation === 'supports' ? palette.amber : palette.cyan
  const curve = useMemo(() => {
    const start = new THREE.Vector3(...from)
    const end = new THREE.Vector3(...to)
    const midpoint = start.clone().lerp(end, 0.5)
    midpoint.y = Math.max(start.y, end.y) + 0.68 + Math.abs(end.x - start.x) * 0.035
    midpoint.z += relation === 'supports' ? 0.18 : -0.12
    return new THREE.QuadraticBezierCurve3(start, midpoint, end)
  }, [from, to, relation])
  const points = useMemo(() => curve.getPoints(28), [curve])
  useFrame((state) => {
    if (!pulse.current) return
    const progress = (state.clock.elapsedTime * 0.115 + phase) % 1
    pulse.current.position.copy(curve.getPoint(progress))
  })
  return (
    <group>
      <Line points={points} color={color} lineWidth={2.4} transparent opacity={0.055} />
      <Line points={points} color={color} lineWidth={0.62} transparent opacity={0.24} />
      <mesh ref={pulse}>
        <sphereGeometry args={[0.032, 18, 18]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
    </group>
  )
}

function SemanticLinkLayer({ nodes, connections }: { nodes: SpatialNode[]; connections: SpatialConnection[] }) {
  const positions = useMemo(() => semanticNodePositions(nodes), [nodes])
  const visible = useMemo(() => connections
    .filter((link) => positions.has(link.from) && positions.has(link.to))
    .slice(0, 22), [connections, positions])
  return (
    <group>
      {visible.map((link, index) => (
        <SemanticBeam
          key={link.id}
          from={positions.get(link.from)!}
          to={positions.get(link.to)!}
          relation={link.relation}
          phase={(index * 0.137) % 1}
        />
      ))}
    </group>
  )
}

function DataMonolith() {
  const outer = useRef<THREE.Group>(null)
  const inner = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (outer.current) outer.current.rotation.y += delta * 0.07
    if (inner.current) inner.current.rotation.y -= delta * 0.12
  })
  return (
    <group position={[0, 2.25, 0.75]}>
      <group ref={outer}>
        <mesh rotation={[Math.PI / 2.6, 0, 0]}>
          <torusGeometry args={[0.64, 0.018, 12, 96]} />
          <meshBasicMaterial color={palette.cyan} transparent opacity={0.42} toneMapped={false} />
        </mesh>
        <mesh rotation={[-Math.PI / 2.9, 0.35, 0]}>
          <torusGeometry args={[0.9, 0.012, 12, 96]} />
          <meshBasicMaterial color={palette.amber} transparent opacity={0.32} toneMapped={false} />
        </mesh>
      </group>
      <group ref={inner}>
        <mesh>
          <icosahedronGeometry args={[0.28, 2]} />
          <meshPhysicalMaterial color="#b9d8d4" emissive={palette.cyan} emissiveIntensity={1.2} metalness={0.44} roughness={0.18} clearcoat={1} iridescence={0.7} />
        </mesh>
      </group>
      <pointLight color={palette.cyan} intensity={7} distance={4.5} decay={2.2} />
    </group>
  )
}

function AmbientAtmosphere() {
  return (
    <group>
      <Sparkles count={95} scale={[17, 6, 13]} size={1.6} speed={0.12} opacity={0.26} color="#9bc9c5" noise={[1, 0.35, 1]} />
      <Sparkles count={34} scale={[13, 4, 11]} size={2.4} speed={0.08} opacity={0.18} color="#d2ab74" noise={[1, 0.5, 1]} />
      <fogExp2 attach="fog" args={[palette.background, 0.032]} />
    </group>
  )
}

function Scene({ nodes, connections, focus, onFocus, onInspect }: Props) {
  const controls = useRef<CameraControls>(null)
  const textures = useProceduralTextures()
  useEffect(() => {
    if (!controls.current) return
    if (focus === 'foundation') controls.current.setLookAt(-3.65, 2.8, 4.95, -2.75, 1.35, -0.45, true)
    else if (focus === 'work-sample') controls.current.setLookAt(3.65, 2.8, 4.95, 2.75, 1.35, -0.45, true)
    else controls.current.setLookAt(0, 4.9, 11.9, 0, 1.85, -1.95, true)
  }, [focus])

  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const projects = nodes.filter((node) => node.kind === 'project' || node.kind === 'artifact')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const trajectory = nodes.filter((node) => node.kind === 'trajectory_event')

  return (
    <>
      <color attach="background" args={[palette.background]} />
      <AmbientAtmosphere />
      <ambientLight intensity={0.46} color="#9ab0c2" />
      <hemisphereLight args={['#8da6ba', '#21170f', 0.72]} />
      <directionalLight position={[4.8, 8.8, 5.6]} intensity={2.25} color="#dbe7ee" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.00025} />
      <spotLight position={[-6, 7, 3.5]} intensity={14} color="#8ddfd7" distance={15} angle={0.44} penumbra={0.88} />
      <spotLight position={[6, 6.6, 2.4]} intensity={12} color="#e0ab70" distance={14} angle={0.42} penumbra={0.86} />
      <pointLight position={[0, 4.4, -5.9]} intensity={7} color="#5ba8af" distance={10} decay={2.1} />

      <ArchitecturalShell floorTexture={textures.floor} />
      <DataMonolith />
      <Workstation node={foundation} position={[-2.75, 0, -0.65]} accent={palette.cyan} woodTexture={textures.wood} onClick={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[2.75, 0, -0.65]} accent={palette.amber} woodTexture={textures.wood} onClick={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />
      <EvidenceVault nodes={evidence} onInspect={onInspect} />
      <ProjectForge nodes={projects} onInspect={onInspect} />
      <CapabilityConstellation nodes={capabilities} onInspect={onInspect} />
      <TrajectoryRibbon nodes={trajectory} />
      <SemanticLinkLayer nodes={nodes} connections={connections} />
      <CameraControls ref={controls} enabled={false} smoothTime={0.72} />
    </>
  )
}

function CinematicPostFX() {
  return (
    <EffectComposer multisampling={4}>
      <Bloom intensity={0.92} luminanceThreshold={1} luminanceSmoothing={0.26} mipmapBlur />
      <ChromaticAberration offset={[0.00035, 0.00055]} />
      <Vignette eskil={false} offset={0.14} darkness={0.72} />
    </EffectComposer>
  )
}

export function WorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 6.7, 15.8], fov: 43, near: 0.1, far: 80 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.18
        gl.outputColorSpace = THREE.SRGBColorSpace
        gl.shadowMap.type = THREE.PCFSoftShadowMap
        scene.background = new THREE.Color(palette.background)
      }}
      frameloop="always"
    >
      <Scene {...props} />
      <CinematicPostFX />
    </Canvas>
  )
}
