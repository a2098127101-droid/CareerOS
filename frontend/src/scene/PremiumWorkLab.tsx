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
  useCursor,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, ChromaticAberration, EffectComposer, Vignette } from '@react-three/postprocessing'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

const P = {
  bg: '#05080c',
  graphite: '#0d141b',
  graphite2: '#151f28',
  steel: '#30404c',
  cyan: '#78e8df',
  cyan2: '#3f9ea5',
  amber: '#efbd78',
  amber2: '#8e633d',
  green: '#7ce6b7',
  blue: '#79aee2',
  rose: '#dc8b82',
  ivory: '#eee7dc',
}

const capabilityColor: Record<string, string> = {
  unobserved: '#43505c',
  signal: '#9aa8b5',
  evidence: '#e4ba6e',
  verified_evidence: '#7ce2b8',
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html center transform distanceFactor={8}><div className={`scene-label ${className}`}>{children}</div></Html>
}

function makeWoodTexture() {
  const c = document.createElement('canvas')
  c.width = 1024
  c.height = 256
  const x = c.getContext('2d')
  if (!x) return new THREE.Texture()
  const g = x.createLinearGradient(0, 0, 0, c.height)
  g.addColorStop(0, '#8a735b')
  g.addColorStop(.45, '#6d5844')
  g.addColorStop(1, '#51402f')
  x.fillStyle = g
  x.fillRect(0, 0, c.width, c.height)
  for (let y = 2; y < c.height; y += 3) {
    x.strokeStyle = `rgba(30,18,10,${.025 + (y % 19) / 550})`
    x.lineWidth = y % 13 === 0 ? 1.2 : .45
    x.beginPath()
    for (let px = -20; px < c.width + 20; px += 10) {
      const py = y + Math.sin(px * .021 + y * .038) * 1.7 + Math.sin(px * .006 + y * .12) * .8
      if (px === -20) x.moveTo(px, py)
      else x.lineTo(px, py)
    }
    x.stroke()
  }
  const t = new THREE.CanvasTexture(c)
  t.wrapS = THREE.RepeatWrapping
  t.wrapT = THREE.RepeatWrapping
  t.repeat.set(2.4, 1)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 12
  return t
}

function makeFloorTexture() {
  const c = document.createElement('canvas')
  c.width = 768
  c.height = 768
  const x = c.getContext('2d')
  if (!x) return new THREE.Texture()
  x.fillStyle = '#0a1016'
  x.fillRect(0, 0, c.width, c.height)
  const img = x.getImageData(0, 0, c.width, c.height)
  for (let i = 0; i < img.data.length; i += 4) {
    const n = Math.random() * 7
    img.data[i] += n
    img.data[i + 1] += n
    img.data[i + 2] += n
  }
  x.putImageData(img, 0, 0)
  for (let p = 0; p <= c.width; p += 64) {
    x.strokeStyle = p % 256 === 0 ? 'rgba(120,220,215,.07)' : 'rgba(160,180,195,.035)'
    x.lineWidth = p % 256 === 0 ? 1.4 : .7
    x.beginPath(); x.moveTo(p, 0); x.lineTo(p, c.height); x.stroke()
    x.beginPath(); x.moveTo(0, p); x.lineTo(c.width, p); x.stroke()
  }
  const t = new THREE.CanvasTexture(c)
  t.wrapS = THREE.RepeatWrapping
  t.wrapT = THREE.RepeatWrapping
  t.repeat.set(4.7, 3.9)
  t.colorSpace = THREE.SRGBColorSpace
  t.anisotropy = 12
  return t
}

function makeBrushedMetalTexture() {
  const c = document.createElement('canvas')
  c.width = 512
  c.height = 512
  const x = c.getContext('2d')
  if (!x) return new THREE.Texture()
  x.fillStyle = '#8f8f8f'
  x.fillRect(0, 0, 512, 512)
  for (let y = 0; y < 512; y++) {
    const v = 115 + Math.floor(Math.random() * 75)
    x.strokeStyle = `rgb(${v},${v},${v})`
    x.globalAlpha = .2
    x.beginPath(); x.moveTo(0, y); x.lineTo(512, y); x.stroke()
  }
  x.globalAlpha = 1
  const t = new THREE.CanvasTexture(c)
  t.wrapS = THREE.RepeatWrapping
  t.wrapT = THREE.RepeatWrapping
  t.repeat.set(2, 5)
  t.anisotropy = 8
  return t
}

function useTextures() {
  const textures = useMemo(() => ({ wood: makeWoodTexture(), floor: makeFloorTexture(), metal: makeBrushedMetalTexture() }), [])
  useEffect(() => () => Object.values(textures).forEach((t) => t.dispose()), [textures])
  return textures
}

function GlowBar({ position, scale, color = P.cyan, power = 2 }: { position: Vec3; scale: Vec3; color?: string; power?: number }) {
  return <mesh position={position} scale={scale}><boxGeometry /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={power} toneMapped={false} /></mesh>
}

function Cable({ from, to, color = '#53616b' }: { from: Vec3; to: Vec3; color?: string }) {
  const start = useMemo(() => new THREE.Vector3(...from), [from])
  const end = useMemo(() => new THREE.Vector3(...to), [to])
  const midpoint = useMemo(() => start.clone().add(end).multiplyScalar(.5), [start, end])
  const length = start.distanceTo(end)
  const direction = useMemo(() => end.clone().sub(start).normalize(), [start, end])
  const q = useMemo(() => new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction), [direction])
  return <mesh position={midpoint} quaternion={q}><cylinderGeometry args={[.012, .012, length, 10]} /><meshStandardMaterial color={color} metalness={.78} roughness={.3} /></mesh>
}

function SuspendedHalo() {
  const outer = useRef<THREE.Group>(null)
  const inner = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (outer.current) outer.current.rotation.z += delta * .025
    if (inner.current) inner.current.rotation.z = -state.clock.elapsedTime * .035
  })
  const anchors: Vec3[] = [[-4.2, 6.2, -1.4], [4.2, 6.2, -1.4], [-3.2, 6.2, 2.4], [3.2, 6.2, 2.4]]
  const ringTargets: Vec3[] = [[-2.7, 4.55, .1], [2.7, 4.55, .1], [-2.1, 4.55, 1.5], [2.1, 4.55, 1.5]]
  return (
    <group>
      {anchors.map((a, i) => <Cable key={i} from={a} to={ringTargets[i]} />)}
      <group position={[0, 4.55, .65]} rotation={[Math.PI / 2, 0, 0]}>
        <group ref={outer}>
          <mesh><torusGeometry args={[3.65, .085, 18, 160]} /><meshPhysicalMaterial color="#1f2c36" metalness={.82} roughness={.2} clearcoat={.55} /></mesh>
          <mesh scale={[1, 1, 1.02]}><torusGeometry args={[3.65, .018, 10, 160]} /><meshBasicMaterial color={P.cyan} transparent opacity={.55} toneMapped={false} /></mesh>
        </group>
        <group ref={inner}>
          <mesh><torusGeometry args={[2.72, .048, 16, 144]} /><meshStandardMaterial color="#6d5845" metalness={.45} roughness={.28} /></mesh>
          <mesh><torusGeometry args={[2.72, .01, 10, 144]} /><meshBasicMaterial color={P.amber} transparent opacity={.5} toneMapped={false} /></mesh>
        </group>
      </group>
      <pointLight position={[0, 4.35, .65]} color={P.cyan} intensity={6} distance={8} decay={2.2} />
    </group>
  )
}

function GlassPartition({ position, rotation = [0, 0, 0], width = 3.3 }: { position: Vec3; rotation?: Vec3; width?: number }) {
  return (
    <group position={position} rotation={rotation}>
      <RoundedBox args={[width + .16, 3.05, .1]} radius={.06} smoothness={4}>
        <meshPhysicalMaterial color="#14232c" metalness={.68} roughness={.25} />
      </RoundedBox>
      <RoundedBox args={[width, 2.86, .035]} radius={.045} smoothness={4} position={[0, 0, .07]}>
        <meshPhysicalMaterial color="#94bdc4" transparent opacity={.16} roughness={.12} metalness={.05} transmission={.46} thickness={.32} ior={1.35} clearcoat={1} clearcoatRoughness={.12} />
        <Edges color="#577583" threshold={25} />
      </RoundedBox>
      <GlowBar position={[-width * .37, 0, .105]} scale={[.012, 2.35, .012]} color={P.cyan} power={1.1} />
      <GlowBar position={[width * .37, 0, .105]} scale={[.012, 2.35, .012]} color={P.amber} power={.75} />
    </group>
  )
}

function ServerRack({ position, accent }: { position: Vec3; accent: string }) {
  return (
    <group position={position}>
      <RoundedBox args={[1.12, 3.45, .9]} radius={.09} smoothness={5} castShadow>
        <meshPhysicalMaterial color="#0b1117" metalness={.76} roughness={.28} clearcoat={.35} />
        <Edges color="#34444f" threshold={25} />
      </RoundedBox>
      {Array.from({ length: 10 }, (_, i) => (
        <group key={i} position={[0, 1.37 - i * .285, .48]}>
          <RoundedBox args={[.9, .205, .05]} radius={.025} smoothness={3}>
            <meshStandardMaterial color="#151f27" metalness={.7} roughness={.32} />
          </RoundedBox>
          <GlowBar position={[-.31, 0, .045]} scale={[.07, .012, .008]} color={i % 4 === 0 ? P.amber : accent} power={i % 4 === 0 ? .8 : 1.2} />
          <GlowBar position={[.31, 0, .045]} scale={[.025, .012, .008]} color={accent} power={.7} />
        </group>
      ))}
      <pointLight position={[0, .8, .8]} color={accent} intensity={2.2} distance={2.6} decay={2} />
    </group>
  )
}

function Architecture({ floor, metal }: { floor: THREE.Texture; metal: THREE.Texture }) {
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[25, 20]} />
        <MeshReflectorMaterial map={floor} color="#0b1117" roughness={.72} metalness={.26} blur={[320, 110]} mixBlur={.95} mixStrength={18} mirror={.28} resolution={512} depthScale={.28} minDepthThreshold={.38} maxDepthThreshold={1.5} />
      </mesh>
      <RoundedBox args={[17.8, 6.9, .38]} radius={.18} smoothness={5} position={[0, 3.38, -7.12]} receiveShadow>
        <meshPhysicalMaterial color="#080d12" metalness={.5} roughness={.42} roughnessMap={metal} clearcoat={.3} />
      </RoundedBox>
      <RoundedBox args={[14.5, 5.5, .08]} radius={.11} smoothness={5} position={[0, 3.23, -6.86]}>
        <meshPhysicalMaterial color="#101c24" metalness={.4} roughness={.22} clearcoat={.72} clearcoatRoughness={.14} />
      </RoundedBox>
      <mesh position={[0, 3.18, -6.76]}><planeGeometry args={[13.4, 4.55]} /><meshBasicMaterial color="#0e2129" transparent opacity={.43} toneMapped={false} /></mesh>
      <RoundedBox args={[.24, 6.45, 15.5]} radius={.1} smoothness={4} position={[-8.85, 3.18, -.05]}><meshStandardMaterial color="#0d151c" metalness={.5} roughness={.55} /></RoundedBox>
      <RoundedBox args={[.24, 6.45, 15.5]} radius={.1} smoothness={4} position={[8.85, 3.18, -.05]}><meshStandardMaterial color="#0d151c" metalness={.5} roughness={.55} /></RoundedBox>
      {Array.from({ length: 9 }, (_, i) => (
        <group key={i} position={[0, 6.28, -5.9 + i * 1.47]}>
          <RoundedBox args={[17.3, .14, .18]} radius={.05} smoothness={3}><meshStandardMaterial color="#25333e" metalness={.78} roughness={.26} roughnessMap={metal} /></RoundedBox>
          <GlowBar position={[0, -.085, .11]} scale={[12.9, .016, .022]} color={i % 3 === 0 ? P.amber : P.cyan} power={1.45} />
        </group>
      ))}
      <GlassPartition position={[-7.15, 2.1, 1.55]} rotation={[0, .14, 0]} width={2.55} />
      <GlassPartition position={[7.15, 2.1, 1.55]} rotation={[0, -.14, 0]} width={2.55} />
      <GlassPartition position={[-5.55, 2.1, 4.65]} rotation={[0, .05, 0]} width={2.3} />
      <GlassPartition position={[5.55, 2.1, 4.65]} rotation={[0, -.05, 0]} width={2.3} />
      <ServerRack position={[-7.78, 1.72, -4.95]} accent={P.cyan} />
      <ServerRack position={[7.78, 1.72, -4.95]} accent={P.amber} />
      {[-5.8, -2.9, 0, 2.9, 5.8].map((x, i) => <GlowBar key={x} position={[x, .012, 2.1]} scale={[1.9, .012, .025]} color={i % 2 ? P.amber : P.cyan} power={1.15} />)}
      <SuspendedHalo />
      <ContactShadows position={[0, .025, 0]} opacity={.56} scale={18} blur={2.2} far={7.5} resolution={512} />
    </group>
  )
}

function MonitorUI({ node, locked }: { node?: SpatialNode; locked: boolean }) {
  return (
    <Html transform distanceFactor={6.5} pointerEvents="none">
      <div className={`monitor-ui ${locked ? 'locked' : ''}`}>
        <div className="monitor-ui-top"><span>STEPIN / SPATIAL RUNTIME</span><b>{locked ? 'SERVER LOCKED' : 'LIVE SCENESTATE'}</b></div>
        <div className="monitor-ui-scan"><i /><i /><i /><i /></div>
        <strong>{node?.label || 'Workstation'}</strong>
        <small>read only · capability authority stays server-side</small>
      </div>
    </Html>
  )
}

function Workstation({ node, position, accent, wood, metal, onActivate }: { node?: SpatialNode; position: Vec3; accent: string; wood: THREE.Texture; metal: THREE.Texture; onActivate: () => void }) {
  const root = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const locked = node?.state === 'locked'
  const active = locked ? '#56626c' : accent
  useFrame((state, delta) => {
    if (root.current) {
      const s = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.035 : 1, 6.5, delta)
      root.current.scale.setScalar(s)
      root.current.position.y = THREE.MathUtils.damp(root.current.position.y, hovered ? .035 : 0, 6, delta)
    }
    if (halo.current) halo.current.rotation.z = state.clock.elapsedTime * (hovered ? .16 : .055)
  })
  return (
    <group ref={root} position={position} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onActivate() }}>
      <spotLight position={[0, 4.6, 1.4]} color={active} intensity={hovered ? 34 : locked ? 7 : 22} distance={9} angle={.49} penumbra={.9} castShadow />
      <RoundedBox args={[3.58, .3, 2.48]} radius={.17} smoothness={6} position={[0, .15, 0]} castShadow receiveShadow>
        <meshPhysicalMaterial color="#0e151b" metalness={.78} roughness={.23} roughnessMap={metal} clearcoat={.5} clearcoatRoughness={.16} />
        <Edges color={hovered ? active : '#31414d'} threshold={20} />
      </RoundedBox>
      <group ref={halo} position={[0, .315, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <mesh><ringGeometry args={[1.05, 1.35, 96]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .36 : locked ? .07 : .2} toneMapped={false} /></mesh>
        <mesh><ringGeometry args={[1.54, 1.57, 96]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .66 : locked ? .05 : .35} toneMapped={false} /></mesh>
      </group>
      <RoundedBox args={[2.96, .17, 1.52]} radius={.09} smoothness={6} position={[0, .9, -.02]} castShadow>
        <meshPhysicalMaterial map={wood} color={locked ? '#4b4d4e' : '#7c654f'} roughness={.34} metalness={.06} clearcoat={.48} clearcoatRoughness={.22} />
      </RoundedBox>
      {[-1.27, 1.27].map((x) => <RoundedBox key={x} args={[.18, 1.27, 1.12]} radius={.055} smoothness={4} position={[x, .57, -.02]} castShadow><meshStandardMaterial color="#202b34" metalness={.76} roughness={.27} roughnessMap={metal} /></RoundedBox>)}
      <RoundedBox args={[2.02, 1.28, .13]} radius={.08} smoothness={6} position={[0, 1.67, -.4]} castShadow>
        <meshPhysicalMaterial color="#070c11" metalness={.82} roughness={.16} clearcoat={.82} clearcoatRoughness={.08} />
        <Edges color={hovered ? active : '#3b4b57'} threshold={24} />
      </RoundedBox>
      <RoundedBox args={[1.79, 1.06, .036]} radius={.055} smoothness={5} position={[0, 1.67, -.326]}>
        <meshPhysicalMaterial color="#061115" emissive={active} emissiveIntensity={locked ? .08 : hovered ? .92 : .54} roughness={.12} metalness={.36} clearcoat={.9} clearcoatRoughness={.07} />
      </RoundedBox>
      <group position={[0, 1.69, -.292]}><MonitorUI node={node} locked={locked} /></group>
      <RoundedBox args={[.14, .52, .14]} radius={.035} smoothness={4} position={[0, 1.03, -.4]}><meshStandardMaterial color="#2b3741" metalness={.82} roughness={.22} /></RoundedBox>
      <RoundedBox args={[.76, .055, .44]} radius={.035} smoothness={4} position={[0, .96, -.37]}><meshStandardMaterial color="#2a3540" metalness={.78} roughness={.24} /></RoundedBox>
      <RoundedBox args={[1.18, .058, .41]} radius={.04} smoothness={4} position={[-.38, 1.02, .35]} rotation={[-.08, 0, 0]}><meshPhysicalMaterial color="#151d23" metalness={.62} roughness={.27} clearcoat={.42} /></RoundedBox>
      {Array.from({ length: 8 }, (_, i) => <GlowBar key={i} position={[-.82 + i * .14, 1.055, .235]} scale={[.048, .006, .13]} color={i < 5 ? active : '#3a4650'} power={i < 5 ? 1.15 : .14} />)}
      <RoundedBox args={[.44, .045, .32]} radius={.045} smoothness={5} position={[.78, 1.01, .34]}><meshPhysicalMaterial color="#151d23" metalness={.45} roughness={.24} clearcoat={.7} /></RoundedBox>
      <Float speed={1} rotationIntensity={.02} floatIntensity={.06}>
        <group position={[0, 2.57, -.18]}>
          <RoundedBox args={[1.96, .44, .05]} radius={.08} smoothness={5}><meshPhysicalMaterial color="#12212a" transparent opacity={.72} roughness={.06} metalness={.18} transmission={.25} clearcoat={1} /><Edges color={active} threshold={18} /></RoundedBox>
          <group position={[0, 0, .06]}><Label className={locked ? 'muted workstation-label' : 'workstation-label'}>{node?.label || 'Workstation'}</Label></group>
        </group>
      </Float>
    </group>
  )
}

function EvidenceVault({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-5.95, 0, -2.05]}>
      <RoundedBox args={[3.18, 4.5, .52]} radius={.17} smoothness={6} position={[0, 2.26, 0]} castShadow><meshPhysicalMaterial color="#0b1218" metalness={.58} roughness={.22} clearcoat={.55} /><Edges color="#2e3f49" threshold={22} /></RoundedBox>
      <RoundedBox args={[2.79, 3.88, .07]} radius={.08} smoothness={5} position={[0, 2.27, .31]}><meshPhysicalMaterial color="#18303a" transparent opacity={.22} transmission={.38} roughness={.1} thickness={.22} clearcoat={1} /></RoundedBox>
      {Array.from({ length: 5 }, (_, i) => <group key={i} position={[0, .74 + i * .72, .44]}><RoundedBox args={[2.56, .07, .35]} radius={.025} smoothness={3}><meshStandardMaterial color="#34424d" metalness={.8} roughness={.23} /></RoundedBox><GlowBar position={[0, .04, .18]} scale={[2.18, .012, .016]} color={i === 4 ? P.green : P.amber} power={.9} /></group>)}
      {nodes.slice(0, 15).map((node, index) => <EvidenceCard key={node.id} node={node} position={[-.84 + (index % 3) * .84, .93 + Math.floor(index / 3) * .72, .63]} onInspect={onInspect} />)}
      <group position={[0, 4.86, .31]}><Label className="zone-label">EVIDENCE VAULT · SERVER RECORDS</Label></group>
    </group>
  )
}

function EvidenceCard({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
  const accent = verified ? P.green : P.amber
  useFrame((_, delta) => {
    if (!ref.current) return
    const s = THREE.MathUtils.damp(ref.current.scale.x, hovered ? 1.13 : 1, 8, delta)
    ref.current.scale.setScalar(s)
    ref.current.rotation.y = THREE.MathUtils.damp(ref.current.rotation.y, hovered ? -.08 : 0, 6, delta)
  })
  return (
    <Float speed={.8} rotationIntensity={.018} floatIntensity={.07}>
      <group ref={ref} position={position} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onInspect(node) }}>
        <RoundedBox args={[.64, .37, .17]} radius={.055} smoothness={5}><meshPhysicalMaterial color="#17232b" metalness={.42} roughness={.18} clearcoat={.92} /><Edges color={accent} threshold={20} /></RoundedBox>
        <RoundedBox args={[.51, .25, .024]} radius={.026} smoothness={4} position={[0, 0, .105]}><meshStandardMaterial color={verified ? '#16352a' : '#39281b'} emissive={accent} emissiveIntensity={hovered ? 1.05 : verified ? .65 : .22} /></RoundedBox>
        <mesh position={[.23, .12, .135]}><sphereGeometry args={[.027, 18, 18]} /><meshBasicMaterial color={accent} toneMapped={false} /></mesh>
      </group>
    </Float>
  )
}

function ProjectForge({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const rings = useRef<THREE.Group>(null)
  useFrame((_, delta) => { if (rings.current) rings.current.rotation.y += delta * .1 })
  const visible = nodes.slice(0, 10)
  return (
    <group position={[5.75, 0, -2.15]}>
      <mesh position={[0, .48, 0]} castShadow><cylinderGeometry args={[1.82, 2, .58, 72]} /><meshPhysicalMaterial color="#0e151b" metalness={.72} roughness={.2} clearcoat={.58} /></mesh>
      <mesh position={[0, .81, 0]}><cylinderGeometry args={[1.67, 1.67, .11, 72]} /><meshPhysicalMaterial color="#65503d" metalness={.15} roughness={.35} clearcoat={.5} /></mesh>
      <group ref={rings} position={[0, 1.02, 0]}><mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.24, .018, 12, 96]} /><meshBasicMaterial color={P.cyan} transparent opacity={.55} toneMapped={false} /></mesh><mesh rotation={[Math.PI / 2, 0, 0]} scale={[.74, .74, .74]}><torusGeometry args={[1.24, .012, 10, 96]} /><meshBasicMaterial color={P.amber} transparent opacity={.5} toneMapped={false} /></mesh></group>
      {visible.map((node, index) => <ArtifactPlate key={node.id} node={node} index={index} count={visible.length} onInspect={onInspect} />)}
      <group position={[0, 2.15, 0]}><Label className="zone-label">PROJECT FORGE · VERSIONS</Label></group>
    </group>
  )
}

function ArtifactPlate({ node, index, count, onInspect }: { node: SpatialNode; index: number; count: number; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const angle = (index / Math.max(1, count)) * Math.PI * 2
  const radius = .72 + (index % 2) * .29
  const accent = node.kind === 'artifact' ? P.amber : P.blue
  useFrame((state, delta) => {
    if (!ref.current) return
    const s = THREE.MathUtils.damp(ref.current.scale.x, hovered ? 1.14 : 1, 7, delta)
    ref.current.scale.setScalar(s)
    ref.current.position.y = 1.16 + (index % 3) * .12 + Math.sin(state.clock.elapsedTime * .9 + index) * .018
  })
  return (
    <group ref={ref} position={[Math.cos(angle) * radius, 1.16 + (index % 3) * .12, Math.sin(angle) * radius]} rotation={[0, -angle + Math.PI / 2, 0]} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onInspect(node) }}>
      <RoundedBox args={[.6, .06, .87]} radius={.038} smoothness={4}><meshPhysicalMaterial color={node.kind === 'artifact' ? '#90775a' : '#526f89'} metalness={.32} roughness={.26} clearcoat={.72} /><Edges color={accent} threshold={22} /></RoundedBox>
      <GlowBar position={[0, .042, -.29]} scale={[.36, .009, .018]} color={accent} power={hovered ? 2 : 1.05} />
    </group>
  )
}

function capabilityLocal(index: number): Vec3 {
  const ring = index < 5 ? 0 : 1
  const local = index % 5
  const a = (local / 5) * Math.PI * 2 - Math.PI / 2 + ring * .22
  return [Math.cos(a) * (ring ? 3.25 : 2.1), Math.sin(a) * (ring ? 1.55 : 1.05), 0]
}

function CapabilityField({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const frame = useRef<THREE.Group>(null)
  useFrame((state) => { if (frame.current) frame.current.rotation.z = Math.sin(state.clock.elapsedTime * .14) * .012 })
  const visible = nodes.slice(0, 10)
  return (
    <group ref={frame} position={[0, 3.28, -6.38]}>
      <mesh position={[0, 0, -.08]}><circleGeometry args={[4.3, 96]} /><meshBasicMaterial color="#071219" transparent opacity={.68} /></mesh>
      <mesh position={[0, 0, -.04]}><ringGeometry args={[3.95, 4.04, 128]} /><meshBasicMaterial color={P.cyan} transparent opacity={.18} toneMapped={false} /></mesh>
      {visible.map((node, i) => <CapabilityOrb key={node.id} node={node} position={capabilityLocal(i)} onInspect={onInspect} />)}
      <mesh><sphereGeometry args={[.17, 36, 36]} /><meshStandardMaterial color="#d8ebe8" emissive={P.cyan} emissiveIntensity={1.5} toneMapped={false} /></mesh>
      {visible.map((_, i) => <Line key={i} points={[[0, 0, 0], capabilityLocal(i)]} color={i % 2 ? '#6f6254' : '#52747a'} lineWidth={.55} transparent opacity={.17} />)}
      <group position={[0, 2.5, .12]}><Label className="zone-label">CAPABILITY CONSTELLATION · SERVER VERIFIED</Label></group>
    </group>
  )
}

function CapabilityOrb({ node, position, onInspect }: { node: SpatialNode; position: Vec3; onInspect: (node: SpatialNode) => void }) {
  const root = useRef<THREE.Group>(null)
  const ring = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  const color = capabilityColor[level] || capabilityColor.unobserved
  const radius = level === 'verified_evidence' ? .33 : level === 'evidence' ? .29 : level === 'signal' ? .245 : .19
  useFrame((state, delta) => {
    if (root.current) {
      const pulse = level === 'verified_evidence' ? 1 + Math.sin(state.clock.elapsedTime * 2.1 + position[0]) * .025 : 1
      const target = hovered ? 1.22 : pulse
      const s = THREE.MathUtils.damp(root.current.scale.x, target, hovered ? 8 : 4, delta)
      root.current.scale.setScalar(s)
    }
    if (ring.current) ring.current.rotation.z += delta * (hovered ? 1.2 : .23)
  })
  return (
    <Float speed={.7} rotationIntensity={.035} floatIntensity={.1}>
      <group ref={root} position={position} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onInspect(node) }}>
        <mesh><sphereGeometry args={[radius, 56, 56]} /><meshPhysicalMaterial color={color} emissive={color} emissiveIntensity={level === 'verified_evidence' ? hovered ? 3.5 : 2.3 : level === 'evidence' ? 1.2 : .25} roughness={.12} metalness={.42} clearcoat={1} clearcoatRoughness={.06} iridescence={level === 'verified_evidence' ? 1 : .18} iridescenceIOR={1.3} /></mesh>
        <mesh ref={ring} rotation={[0, 0, Math.PI / 4]}><torusGeometry args={[radius * 1.62, .015, 10, 80]} /><meshBasicMaterial color={color} transparent opacity={hovered ? .78 : level === 'unobserved' ? .12 : .48} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2.7, 0, -Math.PI / 5]}><torusGeometry args={[radius * 1.95, .008, 10, 80]} /><meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? .42 : .13} toneMapped={false} /></mesh>
        <group position={[0, -radius * 2.3, 0]}><Label className="capability-label">{node.label}</Label></group>
      </group>
    </Float>
  )
}

function TrajectoryRibbon({ nodes }: { nodes: SpatialNode[] }) {
  const recent = nodes.slice(-24)
  const points = recent.map((_, i) => [i * .34, Math.sin(i * .72) * .07, Math.cos(i * .42) * .14] as Vec3)
  return (
    <group position={[-3.95, .34, 3.08]}>
      <RoundedBox args={[8.08, .22, .76]} radius={.12} smoothness={5} position={[3.95, -.16, 0]}><meshPhysicalMaterial color="#0c141b" metalness={.54} roughness={.25} clearcoat={.46} /><Edges color="#273641" threshold={28} /></RoundedBox>
      {points.length > 1 && <Line points={points} color={P.cyan} lineWidth={1.1} transparent opacity={.32} />}
      {recent.map((node, i) => { const c = node.state === 'failure' ? P.rose : node.state === 'success' ? P.green : '#788b9b'; return <Float key={node.id} speed={.65} rotationIntensity={0} floatIntensity={.04}><mesh position={points[i]}><sphereGeometry args={[node.state === 'failure' ? .09 : .058, 24, 24]} /><meshStandardMaterial color={c} emissive={c} emissiveIntensity={node.state === 'success' ? 1.25 : .45} toneMapped={false} /></mesh></Float> })}
      <group position={[4, .3, 0]}><Label className="trajectory-label">TRAJECTORY · IMMUTABLE EVENT LEDGER</Label></group>
    </group>
  )
}

function semanticPositions(nodes: SpatialNode[]) {
  const map = new Map<string, Vec3>()
  nodes.filter((n) => n.kind === 'evidence').slice(0, 15).forEach((n, i) => map.set(n.id, [-5.95 - .84 + (i % 3) * .84, .93 + Math.floor(i / 3) * .72, -1.42]))
  const forge = nodes.filter((n) => n.kind === 'project' || n.kind === 'artifact').slice(0, 10)
  forge.forEach((n, i) => { const a = (i / Math.max(1, forge.length)) * Math.PI * 2; const r = .72 + (i % 2) * .29; map.set(n.id, [5.75 + Math.cos(a) * r, 1.16 + (i % 3) * .12, -2.15 + Math.sin(a) * r]) })
  nodes.filter((n) => n.kind === 'capability').slice(0, 10).forEach((n, i) => { const p = capabilityLocal(i); map.set(n.id, [p[0], 3.28 + p[1], -6.38]) })
  return map
}

function SemanticBeam({ from, to, relation, phase }: { from: Vec3; to: Vec3; relation: string; phase: number }) {
  const pulse = useRef<THREE.Mesh>(null)
  const color = relation === 'supports' ? P.amber : P.cyan
  const curve = useMemo(() => {
    const a = new THREE.Vector3(...from)
    const b = new THREE.Vector3(...to)
    const m = a.clone().lerp(b, .5)
    m.y = Math.max(a.y, b.y) + .72 + Math.abs(b.x - a.x) * .035
    return new THREE.QuadraticBezierCurve3(a, m, b)
  }, [from, to])
  const pts = useMemo(() => curve.getPoints(32), [curve])
  useFrame((state) => { if (pulse.current) pulse.current.position.copy(curve.getPoint((state.clock.elapsedTime * .12 + phase) % 1)) })
  return <group><Line points={pts} color={color} lineWidth={2.6} transparent opacity={.05} /><Line points={pts} color={color} lineWidth={.65} transparent opacity={.25} /><mesh ref={pulse}><sphereGeometry args={[.033, 18, 18]} /><meshBasicMaterial color={color} toneMapped={false} /></mesh></group>
}

function SemanticLinks({ nodes, connections }: { nodes: SpatialNode[]; connections: SpatialConnection[] }) {
  const positions = useMemo(() => semanticPositions(nodes), [nodes])
  const links = useMemo(() => connections.filter((l) => positions.has(l.from) && positions.has(l.to)).slice(0, 24), [connections, positions])
  return <group>{links.map((l, i) => <SemanticBeam key={l.id} from={positions.get(l.from)!} to={positions.get(l.to)!} relation={l.relation} phase={(i * .137) % 1} />)}</group>
}

function CoreMonolith() {
  const a = useRef<THREE.Group>(null)
  const b = useRef<THREE.Group>(null)
  useFrame((_, d) => { if (a.current) a.current.rotation.y += d * .08; if (b.current) b.current.rotation.y -= d * .13 })
  return (
    <group position={[0, 2.28, .72]}>
      <group ref={a}><mesh rotation={[Math.PI / 2.6, 0, 0]}><torusGeometry args={[.67, .02, 12, 112]} /><meshBasicMaterial color={P.cyan} transparent opacity={.52} toneMapped={false} /></mesh><mesh rotation={[-Math.PI / 2.9, .35, 0]}><torusGeometry args={[.94, .012, 12, 112]} /><meshBasicMaterial color={P.amber} transparent opacity={.4} toneMapped={false} /></mesh></group>
      <group ref={b}><mesh><icosahedronGeometry args={[.3, 3]} /><meshPhysicalMaterial color="#c8e4e0" emissive={P.cyan} emissiveIntensity={1.6} metalness={.46} roughness={.12} clearcoat={1} iridescence={.9} /></mesh></group>
      <pointLight color={P.cyan} intensity={8} distance={4.8} decay={2.2} />
    </group>
  )
}

function Atmosphere() {
  return <group><Sparkles count={115} scale={[18, 6.5, 14]} size={1.5} speed={.11} opacity={.25} color="#9bd2cc" noise={[1, .35, 1]} /><Sparkles count={45} scale={[13, 5, 11]} size={2.3} speed={.075} opacity={.17} color="#d8ae75" noise={[1, .45, 1]} /><fogExp2 attach="fog" args={[P.bg, .03]} /></group>
}

function Scene({ nodes, connections, focus, onFocus, onInspect }: Props) {
  const controls = useRef<CameraControls>(null)
  const t = useTextures()
  useEffect(() => {
    if (!controls.current) return
    if (focus === 'foundation') controls.current.setLookAt(-3.75, 2.92, 5.15, -2.85, 1.42, -.48, true)
    else if (focus === 'work-sample') controls.current.setLookAt(3.75, 2.92, 5.15, 2.85, 1.42, -.48, true)
    else controls.current.setLookAt(0, 5.05, 12.15, 0, 1.92, -1.95, true)
  }, [focus])
  const foundation = nodes.find((n) => n.id === 'station:foundation')
  const workSample = nodes.find((n) => n.id === 'station:work-sample')
  const evidence = nodes.filter((n) => n.kind === 'evidence')
  const projects = nodes.filter((n) => n.kind === 'project' || n.kind === 'artifact')
  const capabilities = nodes.filter((n) => n.kind === 'capability')
  const trajectory = nodes.filter((n) => n.kind === 'trajectory_event')
  return (
    <>
      <color attach="background" args={[P.bg]} />
      <Atmosphere />
      <ambientLight intensity={.42} color="#91a8ba" />
      <hemisphereLight args={['#91a9bc', '#1e140e', .76]} />
      <directionalLight position={[5, 9, 5.8]} intensity={2.35} color="#e0edf2" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-.00025} />
      <spotLight position={[-6.2, 7.2, 3.5]} intensity={15} color="#8ae4dc" distance={16} angle={.44} penumbra={.9} />
      <spotLight position={[6.2, 6.8, 2.7]} intensity={13} color="#e5af70" distance={15} angle={.42} penumbra={.88} />
      <Architecture floor={t.floor} metal={t.metal} />
      <CoreMonolith />
      <Workstation node={foundation} position={[-2.85, 0, -.68]} accent={P.cyan} wood={t.wood} metal={t.metal} onActivate={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[2.85, 0, -.68]} accent={P.amber} wood={t.wood} metal={t.metal} onActivate={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />
      <EvidenceVault nodes={evidence} onInspect={onInspect} />
      <ProjectForge nodes={projects} onInspect={onInspect} />
      <CapabilityField nodes={capabilities} onInspect={onInspect} />
      <TrajectoryRibbon nodes={trajectory} />
      <SemanticLinks nodes={nodes} connections={connections} />
      <CameraControls ref={controls} enabled={false} smoothTime={.76} />
    </>
  )
}

function PostFX() {
  return <EffectComposer multisampling={4}><Bloom intensity={1.02} luminanceThreshold={1} luminanceSmoothing={.24} mipmapBlur /><ChromaticAberration offset={[.00032, .0005]} /><Vignette eskil={false} offset={.13} darkness={.76} /></EffectComposer>
}

export function PremiumWorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 7.2, 16.8], fov: 42, near: .1, far: 90 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.2
        gl.outputColorSpace = THREE.SRGBColorSpace
        gl.shadowMap.type = THREE.PCFSoftShadowMap
        scene.background = new THREE.Color(P.bg)
      }}
      frameloop="always"
    >
      <Scene {...props} />
      <PostFX />
    </Canvas>
  )
}
