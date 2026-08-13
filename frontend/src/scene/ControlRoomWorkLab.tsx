import {
  CameraControls,
  ContactShadows,
  CubeCamera,
  Edges,
  Float,
  Html,
  Line,
  MeshReflectorMaterial,
  MeshTransmissionMaterial,
  RoundedBox,
  Sparkles,
  useCursor,
} from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, ChromaticAberration, DepthOfField, EffectComposer, Vignette } from '@react-three/postprocessing'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import type { SpatialConnection, SpatialNode } from '../api/types'
import { Alpha4Presentation, DirectorCamera, capabilityPosition, evidencePosition, useAlpha4Event } from './alpha4/Alpha4Presentation'
import { ShaderScreen } from './alpha4/ShaderScreen'

type Focus = 'hub' | 'foundation' | 'work-sample'
type Vec3 = [number, number, number]

type Props = {
  nodes: SpatialNode[]
  connections: SpatialConnection[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

const C = {
  bg: '#020509',
  panel: '#08121a',
  steel: '#263945',
  cyan: '#68f5e5',
  amber: '#ffc67a',
  green: '#75ffc0',
  blue: '#75b7ff',
  rose: '#f28d91',
  ivory: '#f4efe7',
}

const capabilityColor: Record<string, string> = {
  unobserved: '#46545e',
  signal: '#aab6c0',
  evidence: '#ffc475',
  verified_evidence: '#74ffc0',
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html transform center distanceFactor={7.8} pointerEvents="none"><div className={`scene-label ${className}`}>{children}</div></Html>
}

function makeSurface(kind: 'floor' | 'metal' | 'wood') {
  const canvas = document.createElement('canvas')
  canvas.width = kind === 'wood' ? 1024 : 768
  canvas.height = kind === 'wood' ? 256 : 768
  const ctx = canvas.getContext('2d')
  if (!ctx) return new THREE.Texture()
  if (kind === 'wood') {
    const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
    gradient.addColorStop(0, '#7f684f')
    gradient.addColorStop(.52, '#574331')
    gradient.addColorStop(1, '#35271d')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    for (let y = 2; y < canvas.height; y += 3) {
      ctx.strokeStyle = `rgba(20,10,5,${.025 + (y % 21) / 620})`
      ctx.beginPath()
      for (let x = -20; x < canvas.width + 20; x += 9) {
        const py = y + Math.sin(x * .018 + y * .045) * 1.8 + Math.sin(x * .007 + y * .13) * .8
        if (x === -20) ctx.moveTo(x, py)
        else ctx.lineTo(x, py)
      }
      ctx.stroke()
    }
  } else {
    ctx.fillStyle = kind === 'floor' ? '#061018' : '#777f84'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < image.data.length; i += 4) {
      const n = Math.random() * (kind === 'floor' ? 8 : 38)
      image.data[i] += n
      image.data[i + 1] += n
      image.data[i + 2] += n
    }
    ctx.putImageData(image, 0, 0)
    if (kind === 'floor') {
      for (let p = 0; p <= canvas.width; p += 64) {
        ctx.strokeStyle = p % 256 === 0 ? 'rgba(103,240,226,.08)' : 'rgba(160,190,205,.03)'
        ctx.lineWidth = p % 256 === 0 ? 1.3 : .55
        ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, canvas.height); ctx.stroke()
        ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(canvas.width, p); ctx.stroke()
      }
    } else {
      for (let y = 0; y < canvas.height; y += 2) {
        ctx.strokeStyle = `rgba(255,255,255,${.018 + Math.random() * .04})`
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke()
      }
    }
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(kind === 'floor' ? 5.2 : kind === 'wood' ? 2.5 : 2.4, kind === 'floor' ? 4.2 : kind === 'wood' ? 1 : 5.8)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 12
  return texture
}

function useSurfaces() {
  const surfaces = useMemo(() => ({ floor: makeSurface('floor'), metal: makeSurface('metal'), wood: makeSurface('wood') }), [])
  useEffect(() => () => Object.values(surfaces).forEach((surface) => surface.dispose()), [surfaces])
  return surfaces
}

function Glow({ position, scale, color, power = 2 }: { position: Vec3; scale: Vec3; color: string; power?: number }) {
  return <mesh position={position} scale={scale}><boxGeometry /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={power} toneMapped={false} /></mesh>
}

function Cable({ a, b }: { a: Vec3; b: Vec3 }) {
  const data = useMemo(() => {
    const start = new THREE.Vector3(...a)
    const end = new THREE.Vector3(...b)
    const d = end.clone().sub(start)
    return {
      midpoint: start.clone().add(end).multiplyScalar(.5),
      length: d.length(),
      quaternion: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()),
    }
  }, [a, b])
  return <mesh position={data.midpoint} quaternion={data.quaternion}><cylinderGeometry args={[.014, .014, data.length, 12]} /><meshStandardMaterial color="#455661" metalness={.9} roughness={.2} /></mesh>
}

function DynamicReactor() {
  const ring = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (!ring.current) return
    ring.current.rotation.y += delta * .32
    ring.current.rotation.z = Math.sin(state.clock.elapsedTime * .35) * .12
  })
  return (
    <group position={[0, 2.35, .72]}>
      <CubeCamera resolution={256} frames={Infinity} near={.1} far={30}>
        {(texture) => (
          <group>
            <mesh>
              <icosahedronGeometry args={[.42, 5]} />
              <meshPhysicalMaterial envMap={texture} envMapIntensity={2.8} color="#bededc" metalness={1} roughness={.035} clearcoat={1} clearcoatRoughness={.025} />
            </mesh>
            <mesh scale={1.18}><icosahedronGeometry args={[.42, 2]} /><meshBasicMaterial color={C.cyan} transparent opacity={.12} wireframe toneMapped={false} /></mesh>
          </group>
        )}
      </CubeCamera>
      <group ref={ring}>
        <mesh rotation={[Math.PI / 2.4, .2, 0]}><torusKnotGeometry args={[.82, .024, 220, 22, 2, 5]} /><meshPhysicalMaterial color="#667780" metalness={.92} roughness={.13} clearcoat={.7} /></mesh>
        <mesh rotation={[-Math.PI / 2.7, -.25, 0]}><torusGeometry args={[1.12, .018, 12, 150]} /><meshBasicMaterial color={C.amber} transparent opacity={.5} toneMapped={false} /></mesh>
      </group>
      <pointLight color={C.cyan} intensity={11} distance={6} decay={2.1} />
    </group>
  )
}

function RefractiveBulkhead({ position, rotation = [0, 0, 0], width = 3 }: { position: Vec3; rotation?: Vec3; width?: number }) {
  return (
    <group position={position} rotation={rotation}>
      <RoundedBox args={[width + .18, 3.55, .13]} radius={.075} smoothness={5}>
        <meshPhysicalMaterial color="#13242d" metalness={.72} roughness={.24} />
        <Edges color="#314b58" threshold={24} />
      </RoundedBox>
      <RoundedBox args={[width, 3.36, .045]} radius={.065} smoothness={5} position={[0, 0, .105]}>
        <MeshTransmissionMaterial
          transmission={1}
          thickness={.58}
          roughness={.08}
          chromaticAberration={.045}
          anisotropicBlur={.12}
          distortion={.08}
          distortionScale={.34}
          temporalDistortion={.08}
          samples={4}
          resolution={256}
          backside
          color="#8bcbd0"
        />
      </RoundedBox>
      <Glow position={[-width * .39, 0, .16]} scale={[.012, 2.7, .012]} color={C.cyan} power={1.2} />
      <Glow position={[width * .39, 0, .16]} scale={[.012, 2.7, .012]} color={C.amber} power={.9} />
    </group>
  )
}

function ControlRoomArchitecture({ floor, metal }: { floor: THREE.Texture; metal: THREE.Texture }) {
  const ceilingA = useRef<THREE.Group>(null)
  const ceilingB = useRef<THREE.Group>(null)
  useFrame((state, delta) => {
    if (ceilingA.current) ceilingA.current.rotation.z += delta * .025
    if (ceilingB.current) ceilingB.current.rotation.z = -state.clock.elapsedTime * .037
  })
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[28, 22]} />
        <MeshReflectorMaterial map={floor} color="#061018" roughness={.58} metalness={.36} blur={[420, 150]} mixBlur={1} mixStrength={23} mirror={.38} resolution={512} depthScale={.36} minDepthThreshold={.32} maxDepthThreshold={1.7} />
      </mesh>

      <RoundedBox args={[19.2, 7.4, .5]} radius={.22} smoothness={6} position={[0, 3.55, -7.35]} receiveShadow><meshPhysicalMaterial color="#050c12" metalness={.62} roughness={.34} roughnessMap={metal} clearcoat={.42} /></RoundedBox>
      <RoundedBox args={[15.8, 5.85, .08]} radius={.13} smoothness={6} position={[0, 3.4, -7.04]}><meshPhysicalMaterial color="#0a1922" metalness={.42} roughness={.16} clearcoat={.92} /></RoundedBox>

      {Array.from({ length: 11 }, (_, i) => {
        const x = -8.4 + i * 1.68
        return <group key={i} position={[x, 3.45, -6.9]}><RoundedBox args={[.12, 5.2, .11]} radius={.04} smoothness={3}><meshStandardMaterial color="#263945" metalness={.82} roughness={.2} roughnessMap={metal} /></RoundedBox><Glow position={[0, 0, .075]} scale={[.018, 4.35, .01]} color={i % 3 === 0 ? C.amber : C.cyan} power={i % 3 === 0 ? .7 : 1.1} /></group>
      })}

      {[-8.8, 8.8].map((x) => <RoundedBox key={x} args={[.3, 6.7, 15.8]} radius={.12} smoothness={5} position={[x, 3.25, .1]}><meshPhysicalMaterial color="#091219" metalness={.7} roughness={.34} roughnessMap={metal} /></RoundedBox>)}

      <group position={[0, 5.1, .6]} rotation={[Math.PI / 2, 0, 0]}>
        <group ref={ceilingA}><mesh><torusGeometry args={[4.25, .11, 20, 180]} /><meshPhysicalMaterial color="#15252f" metalness={.9} roughness={.17} clearcoat={.7} /></mesh><mesh><torusGeometry args={[4.25, .021, 10, 180]} /><meshBasicMaterial color={C.cyan} transparent opacity={.7} toneMapped={false} /></mesh></group>
        <group ref={ceilingB}><mesh><torusGeometry args={[3.18, .065, 18, 160]} /><meshPhysicalMaterial color="#5d4938" metalness={.55} roughness={.23} clearcoat={.62} /></mesh><mesh><torusGeometry args={[3.18, .012, 10, 160]} /><meshBasicMaterial color={C.amber} transparent opacity={.56} toneMapped={false} /></mesh></group>
      </group>
      <Cable a={[-4.5, 6.45, -1.4]} b={[-2.9, 5.1, .3]} />
      <Cable a={[4.5, 6.45, -1.4]} b={[2.9, 5.1, .3]} />
      <Cable a={[-3.4, 6.45, 2.4]} b={[-2.15, 5.1, 1.5]} />
      <Cable a={[3.4, 6.45, 2.4]} b={[2.15, 5.1, 1.5]} />

      <RefractiveBulkhead position={[-7.0, 2.3, 2.75]} rotation={[0, .15, 0]} width={2.65} />
      <RefractiveBulkhead position={[7.0, 2.3, 2.75]} rotation={[0, -.15, 0]} width={2.65} />
      <RefractiveBulkhead position={[-5.7, 2.25, 5.55]} rotation={[0, .36, 0]} width={2.25} />
      <RefractiveBulkhead position={[5.7, 2.25, 5.55]} rotation={[0, -.36, 0]} width={2.25} />

      {Array.from({ length: 7 }, (_, i) => <group key={i} position={[-6.9 + i * 2.3, .045, 4.6]}><Glow position={[0, 0, 0]} scale={[1.3, .014, .05]} color={i % 2 ? C.cyan : C.amber} power={1.15} /></group>)}
      <ContactShadows position={[0, .014, .4]} opacity={.62} scale={22} blur={3.1} far={8} />
    </group>
  )
}

function HoloConsole({ position, color, seed, label }: { position: Vec3; color: string; seed: number; label: string }) {
  const root = useRef<THREE.Group>(null)
  useFrame((state) => { if (root.current) root.current.rotation.y = Math.sin(state.clock.elapsedTime * .16 + seed) * .04 })
  return (
    <group ref={root} position={position}>
      <RoundedBox args={[2.25, .55, 1.15]} radius={.12} smoothness={5} rotation={[-.2, 0, 0]}><meshPhysicalMaterial color="#091219" metalness={.74} roughness={.22} clearcoat={.62} /><Edges color="#2d4653" threshold={24} /></RoundedBox>
      <mesh position={[0, .46, -.15]} rotation={[-.28, 0, 0]}>
        <planeGeometry args={[1.92, .72]} />
        <ShaderScreen color={color} seed={seed} glitch={.58} scanSpeed={.8 + seed * .06} intensity={1.1} />
      </mesh>
      <Glow position={[0, .08, .58]} scale={[1.66, .012, .018]} color={color} power={1.25} />
      <group position={[0, 1.02, -.12]}><Label className="zone-label">{label}</Label></group>
    </group>
  )
}

function Workstation({ node, position, color, wood, metal, seed, onActivate }: { node?: SpatialNode; position: Vec3; color: string; wood: THREE.Texture; metal: THREE.Texture; seed: number; onActivate: () => void }) {
  const root = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const locked = node?.state === 'locked'
  const active = locked ? '#58646d' : color
  useFrame((state, delta) => {
    if (root.current) {
      const s = THREE.MathUtils.damp(root.current.scale.x, hovered ? 1.055 : 1, 7, delta)
      root.current.scale.setScalar(s)
      root.current.position.y = THREE.MathUtils.damp(root.current.position.y, hovered ? .055 : 0, 7, delta)
    }
    if (halo.current) halo.current.rotation.z = state.clock.elapsedTime * (hovered ? .34 : .08)
  })
  return (
    <group ref={root} position={position} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onActivate() }}>
      <spotLight position={[0, 5.2, 1.5]} color={active} intensity={hovered ? 42 : locked ? 7 : 27} distance={10} angle={.47} penumbra={.9} castShadow />
      <RoundedBox args={[3.72, .33, 2.62]} radius={.19} smoothness={6} position={[0, .16, 0]} castShadow receiveShadow><meshPhysicalMaterial color="#091219" metalness={.84} roughness={.19} roughnessMap={metal} clearcoat={.66} /><Edges color={hovered ? active : '#304653'} threshold={20} /></RoundedBox>
      <group ref={halo} position={[0, .34, 0]} rotation={[-Math.PI / 2, 0, 0]}><mesh><ringGeometry args={[1.1, 1.43, 110]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .52 : locked ? .05 : .22} toneMapped={false} /></mesh><mesh><ringGeometry args={[1.65, 1.69, 110]} /><meshBasicMaterial color={active} transparent opacity={hovered ? .82 : locked ? .04 : .38} toneMapped={false} /></mesh></group>
      <RoundedBox args={[3.06, .18, 1.6]} radius={.1} smoothness={6} position={[0, .92, 0]} castShadow><meshPhysicalMaterial map={wood} color={locked ? '#474a4b' : '#725b45'} roughness={.28} metalness={.05} clearcoat={.62} /></RoundedBox>
      {[-1.31, 1.31].map((x) => <RoundedBox key={x} args={[.19, 1.3, 1.17]} radius={.06} smoothness={4} position={[x, .58, 0]} castShadow><meshStandardMaterial color="#1d2a33" metalness={.82} roughness={.22} roughnessMap={metal} /></RoundedBox>)}
      <RoundedBox args={[2.16, 1.4, .15]} radius={.09} smoothness={6} position={[0, 1.74, -.4]} castShadow><meshPhysicalMaterial color="#050b10" metalness={.88} roughness={.12} clearcoat={.95} /><Edges color={hovered ? active : '#3a515e'} threshold={24} /></RoundedBox>
      <mesh position={[0, 1.74, -.313]}>
        <planeGeometry args={[1.92, 1.16]} />
        <ShaderScreen color={active} seed={seed} glitch={locked ? .08 : hovered ? .85 : .48} scanSpeed={hovered ? 1.35 : .9} intensity={locked ? .3 : hovered ? 1.45 : 1.1} />
      </mesh>
      <RoundedBox args={[1.24, .065, .44]} radius={.04} smoothness={4} position={[-.38, 1.03, .36]} rotation={[-.08, 0, 0]}><meshPhysicalMaterial color="#121b22" metalness={.65} roughness={.25} clearcoat={.48} /></RoundedBox>
      {Array.from({ length: 8 }, (_, i) => <Glow key={i} position={[-.84 + i * .145, 1.07, .25]} scale={[.05, .006, .13]} color={i < 5 ? active : '#34434d'} power={i < 5 ? 1.35 : .12} />)}
      <Float speed={1.1} rotationIntensity={.02} floatIntensity={.07}><group position={[0, 2.72, -.14]}><RoundedBox args={[2.05, .46, .055]} radius={.085} smoothness={5}><MeshTransmissionMaterial transmission={1} thickness={.3} roughness={.06} chromaticAberration={.03} anisotropicBlur={.08} distortionScale={.2} temporalDistortion={.04} samples={3} resolution={128} color="#94c9cd" /></RoundedBox><Edges color={active} threshold={18} /><group position={[0, 0, .07]}><Label className={locked ? 'muted workstation-label' : 'workstation-label'}>{node?.label || 'Workstation'}</Label></group></group></Float>
    </group>
  )
}

function EvidenceVault({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-6.05, 0, -2.04]}>
      <RoundedBox args={[3.2, 4.75, .58]} radius={.18} smoothness={6} position={[0, 2.4, 0]} castShadow><meshPhysicalMaterial color="#071119" metalness={.68} roughness={.18} clearcoat={.72} /><Edges color="#2b4653" threshold={22} /></RoundedBox>
      <RoundedBox args={[2.82, 4.05, .065]} radius={.08} smoothness={5} position={[0, 2.4, .34]}><MeshTransmissionMaterial transmission={1} thickness={.34} roughness={.09} chromaticAberration={.04} anisotropicBlur={.12} distortionScale={.2} temporalDistortion={.03} samples={3} resolution={192} color="#75b8bf" /></RoundedBox>
      {Array.from({ length: 6 }, (_, i) => <group key={i} position={[0, .76 + i * .62, .48]}><RoundedBox args={[2.56, .065, .36]} radius={.025} smoothness={3}><meshStandardMaterial color="#2d3d48" metalness={.84} roughness={.2} /></RoundedBox><Glow position={[0, .04, .19]} scale={[2.18, .012, .015]} color={i === 5 ? C.green : C.amber} power={.9} /></group>)}
      {nodes.slice(0, 15).map((node, index) => <EvidenceCapsule key={node.id} node={node} index={index} onInspect={onInspect} />)}
      <group position={[0, 5.08, .35]}><Label className="zone-label">EVIDENCE VAULT / CANONICAL RECORDS</Label></group>
    </group>
  )
}

function EvidenceCapsule({ node, index, onInspect }: { node: SpatialNode; index: number; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const verified = node.state === 'verified' || String(node.data?.verificationStatus || '') === 'VERIFIED'
  const color = verified ? C.green : C.amber
  const p = evidencePosition(index)
  useFrame((state, delta) => {
    if (!ref.current) return
    const s = THREE.MathUtils.damp(ref.current.scale.x, hovered ? 1.2 : 1, 8, delta)
    ref.current.scale.setScalar(s)
    ref.current.rotation.y = THREE.MathUtils.damp(ref.current.rotation.y, hovered ? -.16 : Math.sin(state.clock.elapsedTime * .3 + index) * .025, 6, delta)
  })
  return (
    <group ref={ref} position={[p[0] + 6.05, p[1], p[2] + 2.62]} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onInspect(node) }}>
      <RoundedBox args={[.62, .32, .18]} radius={.06} smoothness={5}><meshPhysicalMaterial color="#13232b" metalness={.42} roughness={.15} clearcoat={1} /><Edges color={color} threshold={20} /></RoundedBox>
      <mesh position={[0, 0, .105]}><planeGeometry args={[.46, .2]} /><ShaderScreen color={color} seed={index + 8} glitch={verified ? .15 : .45} scanSpeed={1.1} intensity={verified ? 1.5 : .8} /></mesh>
      <mesh position={[.23, .11, .135]}><sphereGeometry args={[.028, 20, 20]} /><meshBasicMaterial color={color} toneMapped={false} /></mesh>
    </group>
  )
}

function CapabilityConstellation({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  const frame = useRef<THREE.Group>(null)
  useFrame((state) => { if (frame.current) frame.current.rotation.z = Math.sin(state.clock.elapsedTime * .13) * .015 })
  return (
    <group ref={frame}>
      <group position={[0, 3.42, -6.22]}>
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[3.22, .022, 12, 150]} /><meshBasicMaterial color={C.cyan} transparent opacity={.14} toneMapped={false} /></mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]} scale={[.67, .67, .67]}><torusGeometry args={[3.22, .015, 12, 150]} /><meshBasicMaterial color={C.amber} transparent opacity={.13} toneMapped={false} /></mesh>
        <Sparkles count={60} scale={[7.8, 3.6, .6]} size={2.1} speed={.08} opacity={.26} color={C.cyan} noise={[1, 1, .2]} />
      </group>
      {nodes.slice(0, 10).map((node, index) => <CapabilityOrb key={node.id} node={node} index={index} onInspect={onInspect} />)}
      <group position={[0, 5.55, -6.0]}><Label className="zone-label">CAPABILITY CONSTELLATION / VERIFIED STATE ONLY</Label></group>
    </group>
  )
}

function CapabilityOrb({ node, index, onInspect }: { node: SpatialNode; index: number; onInspect: (node: SpatialNode) => void }) {
  const ref = useRef<THREE.Group>(null)
  const ring = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  useCursor(hovered)
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  const color = capabilityColor[level] || capabilityColor.unobserved
  const radius = level === 'verified_evidence' ? .25 : level === 'evidence' ? .205 : level === 'signal' ? .175 : .135
  const p = capabilityPosition(index)
  useFrame((state, delta) => {
    if (ref.current) {
      const pulse = level === 'verified_evidence' ? 1 + Math.sin(state.clock.elapsedTime * 2.5 + index) * .035 : 1
      const target = hovered ? 1.25 : pulse
      const s = THREE.MathUtils.damp(ref.current.scale.x, target, hovered ? 8 : 4, delta)
      ref.current.scale.setScalar(s)
    }
    if (ring.current) ring.current.rotation.z += delta * (hovered ? 1.45 : level === 'verified_evidence' ? .48 : .22)
  })
  return (
    <Float speed={.72} rotationIntensity={.04} floatIntensity={.12}>
      <group ref={ref} position={p} onPointerOver={(e) => { e.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)} onClick={(e) => { e.stopPropagation(); onInspect(node) }}>
        <CubeCamera resolution={128} frames={level === 'verified_evidence' ? Infinity : 1} near={.1} far={20}>
          {(texture) => <mesh><sphereGeometry args={[radius, 64, 64]} /><meshPhysicalMaterial envMap={texture} envMapIntensity={level === 'verified_evidence' ? 3 : 1.4} color={color} emissive={color} emissiveIntensity={level === 'verified_evidence' ? 2.5 : level === 'evidence' ? .9 : .12} roughness={.08} metalness={.72} clearcoat={1} clearcoatRoughness={.04} iridescence={level === 'verified_evidence' ? 1 : .2} toneMapped={level !== 'verified_evidence'} /></mesh>}
        </CubeCamera>
        <group ref={ring}><mesh rotation={[0, 0, Math.PI / 4]}><torusGeometry args={[radius * 1.75, .014, 10, 90]} /><meshBasicMaterial color={color} transparent opacity={hovered ? .88 : level === 'unobserved' ? .12 : .5} toneMapped={false} /></mesh><mesh rotation={[Math.PI / 2.65, 0, -Math.PI / 5]}><torusGeometry args={[radius * 2.1, .007, 10, 90]} /><meshBasicMaterial color={color} transparent opacity={level === 'verified_evidence' ? .48 : .12} toneMapped={false} /></mesh></group>
        <group position={[0, -radius * 2.5, 0]}><Label className="capability-label">{node.label}</Label></group>
      </group>
    </Float>
  )
}

function TrajectoryDeck({ nodes }: { nodes: SpatialNode[] }) {
  const recent = nodes.slice(-26)
  const points = recent.map((_, i) => [i * .3, Math.sin(i * .66) * .08, Math.cos(i * .38) * .16] as Vec3)
  return (
    <group position={[-3.75, .36, 3.12]}>
      <RoundedBox args={[7.75, .24, .82]} radius={.13} smoothness={5} position={[3.75, -.17, 0]}><meshPhysicalMaterial color="#071119" metalness={.62} roughness={.21} clearcoat={.58} /><Edges color="#263d49" threshold={28} /></RoundedBox>
      {points.length > 1 && <Line points={points} color={C.cyan} lineWidth={1.15} transparent opacity={.32} />}
      {recent.map((node, i) => {
        const color = node.state === 'failure' ? C.rose : node.state === 'success' ? C.green : '#758995'
        return <Float key={node.id} speed={.65} rotationIntensity={0} floatIntensity={.04}><mesh position={points[i]}><sphereGeometry args={[node.state === 'failure' ? .095 : .06, 24, 24]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={node.state === 'success' ? 1.4 : .4} toneMapped={false} /></mesh></Float>
      })}
      <group position={[3.8, .34, 0]}><Label className="trajectory-label">TRAJECTORY / IMMUTABLE EVENT DECK</Label></group>
    </group>
  )
}

function Scene({ nodes, connections, focus, onFocus, onInspect }: Props) {
  const controls = useRef<CameraControls>(null)
  const surfaces = useSurfaces()
  const event = useAlpha4Event(nodes)
  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const trajectory = nodes.filter((node) => node.kind === 'trajectory_event')

  return (
    <>
      <color attach="background" args={[C.bg]} />
      <fogExp2 attach="fog" args={[C.bg, .025]} />
      <ambientLight intensity={.36} color="#91a9bc" />
      <hemisphereLight args={['#8da8bd', '#130d09', .72]} />
      <directionalLight position={[5.5, 9.5, 6]} intensity={2.6} color="#dfedf3" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-.00024} />
      <spotLight position={[-6.4, 7.4, 3.8]} intensity={17} color={C.cyan} distance={17} angle={.43} penumbra={.92} />
      <spotLight position={[6.4, 7.0, 3.2]} intensity={15} color={C.amber} distance={16} angle={.42} penumbra={.9} />

      <ControlRoomArchitecture floor={surfaces.floor} metal={surfaces.metal} />
      <DynamicReactor />

      <Workstation node={foundation} position={[-2.95, 0, -.62]} color={C.cyan} wood={surfaces.wood} metal={surfaces.metal} seed={1} onActivate={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[2.95, 0, -.62]} color={C.amber} wood={surfaces.wood} metal={surfaces.metal} seed={4} onActivate={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />

      <HoloConsole position={[-6.1, .42, 5.0]} color={C.cyan} seed={2} label="TRACE ANALYTICS" />
      <HoloConsole position={[6.1, .42, 5.0]} color={C.amber} seed={6} label="EVIDENCE ROUTER" />
      <HoloConsole position={[-6.75, .42, -.1]} color={C.green} seed={9} label="VERIFY NODE" />
      <HoloConsole position={[6.75, .42, -.1]} color={C.blue} seed={12} label="ARTIFACT MATRIX" />

      <EvidenceVault nodes={evidence} onInspect={onInspect} />
      <CapabilityConstellation nodes={capabilities} onInspect={onInspect} />
      <TrajectoryDeck nodes={trajectory} />

      <Alpha4Presentation nodes={nodes} connections={connections} focus={focus} event={event} />
      <DirectorCamera controls={controls} focus={focus} event={event} nodes={nodes} />
      <CameraControls ref={controls} enabled={false} smoothTime={.72} />
    </>
  )
}

function PostFX({ focus }: { focus: Focus }) {
  return (
    <EffectComposer multisampling={4}>
      <DepthOfField focusDistance={focus === 'hub' ? .022 : .012} focalLength={focus === 'hub' ? .036 : .054} bokehScale={focus === 'hub' ? 2.4 : 3.25} height={620} />
      <Bloom intensity={1.22} luminanceThreshold={.82} luminanceSmoothing={.2} mipmapBlur />
      <ChromaticAberration offset={[.00042, .00062]} radialModulation modulationOffset={.35} />
      <Vignette eskil={false} offset={.11} darkness={.82} />
    </EffectComposer>
  )
}

export function ControlRoomWorkLab(props: Props) {
  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: [0, 7.5, 17.4], fov: 41, near: .1, far: 100 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      onCreated={({ gl, scene }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping
        gl.toneMappingExposure = 1.23
        gl.outputColorSpace = THREE.SRGBColorSpace
        gl.shadowMap.type = THREE.PCFSoftShadowMap
        scene.background = new THREE.Color(C.bg)
      }}
      frameloop="always"
    >
      <Scene {...props} />
      <PostFX focus={props.focus} />
    </Canvas>
  )
}
