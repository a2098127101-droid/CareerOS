import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import type { SpatialNode } from '../../api/types'
import type { Alpha5Theme } from './ThemeSystem'

const COUNT = 1800

function hash(seed: number) {
  let value = seed | 0
  return () => {
    value = Math.imul(1664525, value) + 1013904223 | 0
    return ((value >>> 0) % 100000) / 100000
  }
}

function kindColor(kind: string, theme: Alpha5Theme) {
  if (kind === 'capability') return new THREE.Color(theme.accent)
  if (kind === 'evidence') return new THREE.Color(theme.secondary)
  if (kind === 'artifact') return new THREE.Color('#c7d2e2')
  if (kind === 'trajectory_event') return new THREE.Color('#7898a7')
  return new THREE.Color('#50636f')
}

export function InstancedDataField({ nodes, theme }: { nodes: SpatialNode[]; theme: Alpha5Theme }) {
  const mesh = useRef<THREE.InstancedMesh>(null)
  const group = useRef<THREE.Group>(null)
  const shader = useRef<THREE.WebGLProgramParametersWithUniforms['uniforms'] | null>(null)
  const geometry = useMemo(() => new THREE.OctahedronGeometry(.034, 0), [])
  const material = useMemo(() => {
    const value = new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: .62, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false })
    value.onBeforeCompile = (program) => {
      program.uniforms.uTime = { value: 0 }
      program.uniforms.uEnergy = { value: .6 }
      program.vertexShader = program.vertexShader
        .replace('#include <common>', '#include <common>\nuniform float uTime;\nuniform float uEnergy;')
        .replace('#include <begin_vertex>', `
          #include <begin_vertex>
          float instancePhase = instanceMatrix[3].x * .31 + instanceMatrix[3].z * .27;
          transformed.y += sin(uTime * (.45 + uEnergy * .18) + instancePhase) * (.028 + uEnergy * .018);
          transformed.x += cos(uTime * .24 + instancePhase * 1.7) * .012 * uEnergy;
        `)
      shader.current = program.uniforms
    }
    return value
  }, [])

  const nodeSignature = nodes.map((node) => `${node.id}:${node.kind}:${node.state}`).join('|')

  useEffect(() => {
    if (!mesh.current) return
    const random = hash(7391 + nodes.length * 97)
    const dummy = new THREE.Object3D()
    const source = nodes.length ? nodes : [{ kind: 'trajectory_event' } as SpatialNode]
    for (let i = 0; i < COUNT; i += 1) {
      const node = source[i % source.length]
      const ring = 5.7 + random() * 6.6
      const angle = random() * Math.PI * 2
      const y = .5 + random() * 5.6
      const sideBias = random() > .5 ? 1 : -1
      dummy.position.set(Math.cos(angle) * ring + sideBias * random() * .5, y, Math.sin(angle) * ring - 1.2)
      const scale = .42 + random() * 1.75
      dummy.scale.setScalar(scale)
      dummy.rotation.set(random() * Math.PI, random() * Math.PI, random() * Math.PI)
      dummy.updateMatrix()
      mesh.current.setMatrixAt(i, dummy.matrix)
      const color = kindColor(node.kind, theme)
      if (String(node.state).includes('verified') || String(node.data?.verificationLevel || '') === 'verified_evidence') color.multiplyScalar(1.32)
      mesh.current.setColorAt(i, color)
    }
    mesh.current.instanceMatrix.needsUpdate = true
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true
  // theme is intentionally included: whole field recolors with the control-room state.
  }, [nodeSignature, theme, nodes])

  useFrame((state, delta) => {
    if (group.current) {
      group.current.rotation.y += delta * (.006 + theme.particleSpeed * .006)
      group.current.position.y = Math.sin(state.clock.elapsedTime * .11) * .04
    }
    if (shader.current) {
      shader.current.uTime.value = state.clock.elapsedTime
      shader.current.uEnergy.value = theme.dataEnergy
    }
    material.opacity = THREE.MathUtils.damp(material.opacity, .42 + theme.dataEnergy * .17, 2.5, delta)
  })

  useEffect(() => () => {
    geometry.dispose()
    material.dispose()
  }, [geometry, material])

  return (
    <group ref={group}>
      <instancedMesh ref={mesh} args={[geometry, material, COUNT]} frustumCulled={false} />
    </group>
  )
}
