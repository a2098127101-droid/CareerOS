import { CameraControls, Html } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import type { SpatialNode } from '../api/types'

type Focus = 'hub' | 'foundation' | 'work-sample'

type Props = {
  nodes: SpatialNode[]
  focus: Focus
  onFocus: (focus: Focus) => void
  onInspect: (node: SpatialNode) => void
}

const capabilityColors: Record<string, string> = {
  unobserved: '#38404a',
  signal: '#7c8796',
  evidence: '#d4a84f',
  verified_evidence: '#78d7b1',
}

function Label({ children, className = '' }: { children: string; className?: string }) {
  return <Html center transform distanceFactor={9}><div className={`scene-label ${className}`}>{children}</div></Html>
}

function Workstation({ node, position, onClick }: { node?: SpatialNode; position: [number, number, number]; onClick: () => void }) {
  const locked = node?.state === 'locked'
  return (
    <group position={position} onClick={(event) => { event.stopPropagation(); onClick() }}>
      <mesh position={[0, 0.7, 0]} castShadow receiveShadow>
        <boxGeometry args={[2.7, 0.16, 1.45]} />
        <meshStandardMaterial color={locked ? '#343a42' : '#7f6b54'} roughness={0.78} />
      </mesh>
      <mesh position={[0, 1.42, -0.28]} castShadow>
        <boxGeometry args={[1.55, 1.02, 0.12]} />
        <meshStandardMaterial color={locked ? '#222831' : '#19242d'} roughness={0.35} metalness={0.12} />
      </mesh>
      <mesh position={[0, 1.42, -0.20]}>
        <planeGeometry args={[1.32, 0.78]} />
        <meshStandardMaterial emissive={locked ? '#24282e' : '#5ea4a4'} emissiveIntensity={locked ? 0.08 : 0.5} color="#101418" />
      </mesh>
      <group position={[0, 0.96, 0.83]}><Label className={locked ? 'muted' : ''}>{node?.label || 'Workstation'}</Label></group>
    </group>
  )
}

function EvidenceShelf({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[-4.7, 0, -1.2]}>
      <mesh position={[0, 1.8, 0]} receiveShadow>
        <boxGeometry args={[2.8, 3.6, 0.35]} />
        <meshStandardMaterial color="#222931" roughness={0.9} />
      </mesh>
      {nodes.slice(0, 18).map((node, index) => {
        const column = index % 3
        const row = Math.floor(index / 3)
        return (
          <mesh
            key={node.id}
            position={[-0.85 + column * 0.85, 3.05 - row * 0.47, 0.28]}
            onClick={(event) => { event.stopPropagation(); onInspect(node) }}
            castShadow
          >
            <boxGeometry args={[0.62, 0.28, 0.23]} />
            <meshStandardMaterial color={node.state === 'verified' ? '#8fbca8' : '#a99171'} roughness={0.72} />
          </mesh>
        )
      })}
      <group position={[0, 3.78, 0.25]}><Label>Evidence</Label></group>
    </group>
  )
}

function ProjectTable({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[4.4, 0, -1.4]}>
      <mesh position={[0, 0.78, 0]} receiveShadow castShadow>
        <boxGeometry args={[3.1, 0.18, 1.65]} />
        <meshStandardMaterial color="#615345" roughness={0.82} />
      </mesh>
      {nodes.slice(0, 10).map((node, index) => (
        <mesh key={node.id} position={[-1.05 + (index % 5) * 0.52, 0.95 + Math.floor(index / 5) * 0.18, 0]} onClick={(event) => { event.stopPropagation(); onInspect(node) }} castShadow>
          <boxGeometry args={[0.42, 0.06, 0.75]} />
          <meshStandardMaterial color={node.kind === 'artifact' ? '#b7a07d' : '#718aa0'} roughness={0.72} />
        </mesh>
      ))}
      <group position={[0, 1.32, -0.65]}><Label>Projects · Versions</Label></group>
    </group>
  )
}

function CapabilityField({ nodes, onInspect }: { nodes: SpatialNode[]; onInspect: (node: SpatialNode) => void }) {
  return (
    <group position={[0, 2.1, -5.1]}>
      {nodes.slice(0, 10).map((node, index) => {
        const x = (index % 5 - 2) * 1.15
        const y = Math.floor(index / 5) * 0.9
        const level = String(node.data?.verificationLevel || node.state || 'unobserved')
        const scale = level === 'verified_evidence' ? 0.27 : level === 'evidence' ? 0.23 : level === 'signal' ? 0.19 : 0.15
        return (
          <group key={node.id} position={[x, y, 0]} onClick={(event) => { event.stopPropagation(); onInspect(node) }}>
            <mesh>
              <sphereGeometry args={[scale, 24, 24]} />
              <meshStandardMaterial
                color={capabilityColors[level] || capabilityColors.unobserved}
                emissive={capabilityColors[level] || capabilityColors.unobserved}
                emissiveIntensity={level === 'verified_evidence' ? 0.65 : level === 'evidence' ? 0.32 : 0.08}
                roughness={0.4}
              />
            </mesh>
            <group position={[0, -0.38, 0]}><Label className="capability-label">{node.label}</Label></group>
          </group>
        )
      })}
      <group position={[0, 2.0, 0]}><Label>Capability · server verified only</Label></group>
    </group>
  )
}

function TrajectoryLine({ nodes }: { nodes: SpatialNode[] }) {
  return (
    <group position={[-2.9, 0.12, 2.9]}>
      {nodes.slice(-24).map((node, index) => (
        <mesh key={node.id} position={[index * 0.24, 0, Math.sin(index * 0.72) * 0.12]}>
          <sphereGeometry args={[node.state === 'failure' ? 0.07 : 0.045, 12, 12]} />
          <meshStandardMaterial color={node.state === 'failure' ? '#c67c72' : node.state === 'success' ? '#78b89a' : '#727e8b'} />
        </mesh>
      ))}
    </group>
  )
}

function Scene({ nodes, focus, onFocus, onInspect }: Props) {
  const controls = useRef<any>(null)
  useEffect(() => {
    if (!controls.current) return
    if (focus === 'foundation') controls.current.setLookAt(-2.5, 2.5, 4.2, -2.2, 1.0, -0.6, true)
    else if (focus === 'work-sample') controls.current.setLookAt(2.7, 2.5, 4.3, 2.35, 1.0, -0.65, true)
    else controls.current.setLookAt(0, 5.2, 9.8, 0, 1.1, -0.8, true)
  }, [focus])

  const foundation = nodes.find((node) => node.id === 'station:foundation')
  const workSample = nodes.find((node) => node.id === 'station:work-sample')
  const evidence = nodes.filter((node) => node.kind === 'evidence')
  const projects = nodes.filter((node) => node.kind === 'project' || node.kind === 'artifact')
  const capabilities = nodes.filter((node) => node.kind === 'capability')
  const trajectory = nodes.filter((node) => node.kind === 'trajectory_event')

  return (
    <>
      <color attach="background" args={['#0d1117']} />
      <fog attach="fog" args={['#0d1117', 10, 22]} />
      <ambientLight intensity={0.82} />
      <hemisphereLight args={['#9db3c3', '#2a221d', 0.65]} />
      <directionalLight position={[4, 9, 5]} intensity={2.0} castShadow shadow-mapSize={[1024, 1024]} />
      <spotLight position={[-4, 6, 3]} intensity={1.2} angle={0.45} penumbra={0.7} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[22, 18]} />
        <meshStandardMaterial color="#171c22" roughness={0.96} />
      </mesh>
      <Workstation node={foundation} position={[-2.4, 0, -0.7]} onClick={() => onFocus('foundation')} />
      <Workstation node={workSample} position={[2.4, 0, -0.7]} onClick={() => workSample?.state === 'locked' ? workSample && onInspect(workSample) : onFocus('work-sample')} />
      <EvidenceShelf nodes={evidence} onInspect={onInspect} />
      <ProjectTable nodes={projects} onInspect={onInspect} />
      <CapabilityField nodes={capabilities} onInspect={onInspect} />
      <TrajectoryLine nodes={trajectory} />
      <CameraControls ref={controls} enabled={false} smoothTime={0.55} />
    </>
  )
}

export function WorkLab(props: Props) {
  return (
    <Canvas shadows dpr={[1, 1.7]} camera={{ position: [0, 5.2, 9.8], fov: 46, near: 0.1, far: 60 }} frameloop="demand">
      <Scene {...props} />
    </Canvas>
  )
}
