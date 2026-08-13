import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { GPUComputationRenderer } from 'three/examples/jsm/misc/GPUComputationRenderer.js'
import type { SpatialConnection, SpatialNode } from '../../api/types'
import type { Alpha5Theme } from '../alpha5/ThemeSystem'
import { SHOWCASE_CLIPS, sampleTrack, smooth01 } from './ShowcaseSequenceConfig'
import { showcaseProgress, type ShowcaseRuntimeState } from './ShowcaseRuntime'

const SIZE = 48
const COUNT = SIZE * SIZE

const positionShader = /* glsl */`
uniform float delta;
void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 position = texture2D(texturePosition, uv);
  vec3 velocity = texture2D(textureVelocity, uv).xyz;
  position.xyz += velocity * delta;
  gl_FragColor = position;
}
`

const velocityShader = /* glsl */`
uniform float delta;
uniform float time;
uniform float topologyMix;
uniform float orbit;
uniform float attraction;
uniform float turbulence;
uniform sampler2D anchorA;
uniform sampler2D anchorB;
void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec3 position = texture2D(texturePosition, uv).xyz;
  vec3 velocity = texture2D(textureVelocity, uv).xyz;
  vec3 a = texture2D(anchorA, uv).xyz;
  vec3 b = texture2D(anchorB, uv).xyz;
  vec3 target = mix(a, b, topologyMix);

  vec3 toward = (target - position) * (.18 + attraction * .16);
  vec3 relative = position - target;
  vec3 tangent = normalize(vec3(-relative.z, .08, relative.x) + vec3(.0001));
  float wave = sin(position.y * 2.1 + time * .7 + uv.x * 17.0) + cos(position.z * 1.7 - time * .43 + uv.y * 13.0);
  vec3 curl = vec3(
    sin(position.z * 1.35 + time * .55),
    cos(position.x * 1.15 - time * .41) * .6,
    sin(position.y * 1.5 + time * .34)
  );
  velocity += (toward + tangent * orbit * .12 + curl * turbulence * .06 + normalize(relative + vec3(.001)) * wave * turbulence * .012) * delta;
  velocity *= pow(.982, delta * 60.0);
  float speed = length(velocity);
  if (speed > 2.0) velocity = velocity / speed * 2.0;
  gl_FragColor = vec4(velocity, 1.0);
}
`

const vertexShader = /* glsl */`
attribute vec2 reference;
uniform sampler2D positionTexture;
uniform float uTime;
uniform float uEnergy;
varying float vPulse;
varying vec2 vRef;
void main() {
  vec3 p = texture2D(positionTexture, reference).xyz;
  float pulse = .7 + sin(uTime * 2.1 + reference.x * 37.0 + reference.y * 29.0) * .3;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = (1.8 + uEnergy * 1.7) * pulse * (160.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
  vPulse = pulse;
  vRef = reference;
}
`

const fragmentShader = /* glsl */`
uniform sampler2D colorTexture;
uniform float uEnergy;
varying float vPulse;
varying vec2 vRef;
void main() {
  vec2 p = gl_PointCoord - .5;
  float d = length(p);
  if (d > .5) discard;
  vec3 color = texture2D(colorTexture, vRef).rgb;
  float core = smoothstep(.45, .02, d);
  float halo = smoothstep(.5, .16, d) * .5;
  gl_FragColor = vec4(color * (1.25 + core * uEnergy), (core + halo) * (.28 + uEnergy * .22) * vPulse);
}
`

function levelColor(node: SpatialNode, theme: Alpha5Theme) {
  const level = String(node.data?.verificationLevel || node.state || 'unobserved')
  if (level === 'verified_evidence') return new THREE.Color(theme.accent)
  if (level === 'evidence') return new THREE.Color(theme.secondary)
  if (level === 'signal') return new THREE.Color('#a9c0ca')
  return new THREE.Color('#40515c')
}

function graphLayout(capabilities: SpatialNode[], connections: SpatialConnection[]) {
  const ids = new Set(capabilities.map((node) => node.id))
  const degree = new Map<string, number>()
  capabilities.forEach((node) => degree.set(node.id, 0))
  connections.forEach((edge) => {
    if (ids.has(edge.from)) degree.set(edge.from, (degree.get(edge.from) || 0) + 1)
    if (ids.has(edge.to)) degree.set(edge.to, (degree.get(edge.to) || 0) + 1)
  })
  const maxDegree = Math.max(1, ...degree.values())
  return capabilities.map((node, index) => {
    const normalized = (degree.get(node.id) || 0) / maxDegree
    const angle = index / Math.max(1, capabilities.length) * Math.PI * 2 + normalized * .55
    const baseRadius = index % 2 ? 2.25 : 3.05
    const topologyRadius = THREE.MathUtils.lerp(3.15, 1.05, normalized)
    const level = String(node.data?.verificationLevel || node.state || 'unobserved')
    const lift = level === 'verified_evidence' ? .62 : level === 'evidence' ? .3 : level === 'signal' ? .08 : -.18
    return {
      a: new THREE.Vector3(Math.cos(angle) * baseRadius, 3.45 + Math.sin(index * 1.4) * .35, -5.95 + Math.sin(angle) * .6),
      b: new THREE.Vector3(Math.cos(angle * 1.12) * topologyRadius, 3.55 + lift + Math.sin(angle * 2.3) * .38, -5.9 + Math.sin(angle * 1.12) * topologyRadius * .34),
      normalized,
    }
  })
}

export function TopologyReflowNetwork({ capabilities, connections, theme, runtime }: { capabilities: SpatialNode[]; connections: SpatialConnection[]; theme: Alpha5Theme; runtime: ShowcaseRuntimeState }) {
  const { gl } = useThree()

  const system = useMemo(() => {
    const gpu = new GPUComputationRenderer(SIZE, SIZE, gl)
    const positionTexture = gpu.createTexture()
    const velocityTexture = gpu.createTexture()
    const posData = positionTexture.image.data as unknown as Float32Array
    const velData = velocityTexture.image.data as unknown as Float32Array
    const random = (index: number, salt: number) => {
      const x = Math.sin(index * 77.17 + salt * 19.91) * 43758.5453
      return x - Math.floor(x)
    }

    for (let i = 0; i < COUNT; i += 1) {
      const angle = i / COUNT * Math.PI * 2 * 9.0
      const radius = 1.6 + random(i, 1) * 2.0
      const offset = i * 4
      posData[offset] = Math.cos(angle) * radius
      posData[offset + 1] = 3.4 + (random(i, 2) - .5) * 1.7
      posData[offset + 2] = -5.9 + Math.sin(angle) * radius * .35
      posData[offset + 3] = 1
      velData[offset] = (random(i, 3) - .5) * .08
      velData[offset + 1] = (random(i, 4) - .5) * .06
      velData[offset + 2] = (random(i, 5) - .5) * .08
      velData[offset + 3] = 1
    }

    const anchorAData = new Float32Array(COUNT * 4)
    const anchorBData = new Float32Array(COUNT * 4)
    const colorData = new Float32Array(COUNT * 4)
    const anchorA = new THREE.DataTexture(anchorAData, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType)
    const anchorB = new THREE.DataTexture(anchorBData, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType)
    const colorTexture = new THREE.DataTexture(colorData, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType)
    anchorA.needsUpdate = true
    anchorB.needsUpdate = true
    colorTexture.needsUpdate = true

    const positionVariable = gpu.addVariable('texturePosition', positionShader, positionTexture)
    const velocityVariable = gpu.addVariable('textureVelocity', velocityShader, velocityTexture)
    gpu.setVariableDependencies(positionVariable, [positionVariable, velocityVariable])
    gpu.setVariableDependencies(velocityVariable, [positionVariable, velocityVariable])
    positionVariable.material.uniforms.delta = { value: 1 / 60 }
    velocityVariable.material.uniforms.delta = { value: 1 / 60 }
    velocityVariable.material.uniforms.time = { value: 0 }
    velocityVariable.material.uniforms.topologyMix = { value: .2 }
    velocityVariable.material.uniforms.orbit = { value: .3 }
    velocityVariable.material.uniforms.attraction = { value: .9 }
    velocityVariable.material.uniforms.turbulence = { value: .2 }
    velocityVariable.material.uniforms.anchorA = { value: anchorA }
    velocityVariable.material.uniforms.anchorB = { value: anchorB }
    const error = gpu.init()
    if (error) console.error(`Alpha6 topology GPGPU init failed: ${error}`)

    const geometry = new THREE.BufferGeometry()
    const references = new Float32Array(COUNT * 2)
    for (let y = 0; y < SIZE; y += 1) for (let x = 0; x < SIZE; x += 1) {
      const i = y * SIZE + x
      references[i * 2] = (x + .5) / SIZE
      references[i * 2 + 1] = (y + .5) / SIZE
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3))
    geometry.setAttribute('reference', new THREE.BufferAttribute(references, 2))

    const material = new THREE.ShaderMaterial({
      uniforms: { positionTexture: { value: null }, colorTexture: { value: colorTexture }, uTime: { value: 0 }, uEnergy: { value: .8 } },
      vertexShader,
      fragmentShader,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      toneMapped: false,
    })

    return { gpu, positionVariable, velocityVariable, anchorA, anchorB, colorTexture, anchorAData, anchorBData, colorData, geometry, material }
  }, [gl])

  const topologySignature = `${capabilities.map((node) => `${node.id}:${String(node.data?.verificationLevel || node.state)}`).join('|')}::${connections.map((edge) => `${edge.from}>${edge.to}:${edge.relation}`).join('|')}::${theme.name}`
  useEffect(() => {
    const source = capabilities.length ? capabilities : [{ id: 'placeholder', kind: 'capability', label: 'Capability', zone: 'capability', state: 'unobserved', refId: 'placeholder', data: {}, authority: 'server', readOnly: true } as SpatialNode]
    const layout = graphLayout(source, connections)
    for (let i = 0; i < COUNT; i += 1) {
      const nodeIndex = i % source.length
      const node = source[nodeIndex]
      const item = layout[nodeIndex]
      const local = Math.floor(i / source.length)
      const angle = local * 2.399963
      const spread = .06 + (local % 11) * .018
      const offset = i * 4
      system.anchorAData[offset] = item.a.x + Math.cos(angle) * spread
      system.anchorAData[offset + 1] = item.a.y + Math.sin(angle * .7) * spread
      system.anchorAData[offset + 2] = item.a.z + Math.sin(angle) * spread
      system.anchorAData[offset + 3] = 1
      system.anchorBData[offset] = item.b.x + Math.cos(angle * 1.1) * spread * (1.1 + item.normalized)
      system.anchorBData[offset + 1] = item.b.y + Math.sin(angle * .63) * spread * 1.35
      system.anchorBData[offset + 2] = item.b.z + Math.sin(angle * 1.1) * spread * (1.1 + item.normalized)
      system.anchorBData[offset + 3] = 1
      const color = levelColor(node, theme)
      system.colorData[offset] = color.r
      system.colorData[offset + 1] = color.g
      system.colorData[offset + 2] = color.b
      system.colorData[offset + 3] = 1
    }
    system.anchorA.needsUpdate = true
    system.anchorB.needsUpdate = true
    system.colorTexture.needsUpdate = true
  }, [topologySignature, capabilities, connections, theme, system])

  useFrame((state, delta) => {
    const dt = Math.min(.033, delta)
    let reflow = .22
    let orbit = .3
    let attraction = .9
    let turbulence = .24
    if (runtime.active && runtime.clip) {
      const clip = SHOWCASE_CLIPS[runtime.clip]
      const progress = showcaseProgress(runtime, state.clock.elapsedTime)
      const sample = sampleTrack(clip.topology, progress)
      const t = smooth01(sample.t)
      reflow = THREE.MathUtils.lerp(sample.a.reflow, sample.b.reflow, t)
      orbit = THREE.MathUtils.lerp(sample.a.orbit, sample.b.orbit, t)
      attraction = THREE.MathUtils.lerp(sample.a.attraction, sample.b.attraction, t)
      turbulence = THREE.MathUtils.lerp(sample.a.turbulence, sample.b.turbulence, t)
    }
    system.positionVariable.material.uniforms.delta.value = dt
    system.velocityVariable.material.uniforms.delta.value = dt
    system.velocityVariable.material.uniforms.time.value = state.clock.elapsedTime
    system.velocityVariable.material.uniforms.topologyMix.value = reflow
    system.velocityVariable.material.uniforms.orbit.value = orbit
    system.velocityVariable.material.uniforms.attraction.value = attraction
    system.velocityVariable.material.uniforms.turbulence.value = turbulence
    system.gpu.compute()
    system.material.uniforms.positionTexture.value = system.gpu.getCurrentRenderTarget(system.positionVariable).texture
    system.material.uniforms.uTime.value = state.clock.elapsedTime
    system.material.uniforms.uEnergy.value = theme.dataEnergy + reflow * .35
  })

  useEffect(() => () => {
    system.geometry.dispose()
    system.material.dispose()
    system.anchorA.dispose()
    system.anchorB.dispose()
    system.colorTexture.dispose()
    system.positionVariable.material.dispose()
    system.velocityVariable.material.dispose()
    const disposable = system.gpu as unknown as { dispose?: () => void }
    disposable.dispose?.()
  }, [system])

  return <points geometry={system.geometry} material={system.material} frustumCulled={false} />
}
