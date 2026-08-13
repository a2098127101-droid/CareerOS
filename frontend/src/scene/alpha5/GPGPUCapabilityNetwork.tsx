import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import * as THREE from 'three'
import { GPUComputationRenderer } from 'three/examples/jsm/misc/GPUComputationRenderer.js'
import type { SpatialNode } from '../../api/types'
import type { Alpha5Theme } from './ThemeSystem'

const SIZE = 32
const COUNT = SIZE * SIZE

function anchorFor(index: number, total: number) {
  const ring = index % 2 === 0 ? 2.45 : 1.58
  const angle = (index / Math.max(1, total)) * Math.PI * 2 + (index % 2) * .28
  return new THREE.Vector3(Math.cos(angle) * ring, 3.45 + Math.sin(index * 1.7) * .42, -5.95 + Math.sin(angle) * .78)
}

function levelColor(level: string, theme: Alpha5Theme) {
  if (level === 'verified_evidence') return new THREE.Color(theme.accent)
  if (level === 'evidence') return new THREE.Color(theme.secondary)
  if (level === 'signal') return new THREE.Color('#a7bbc8')
  return new THREE.Color('#45535d')
}

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
uniform float energy;
uniform sampler2D anchorTexture;
void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec3 position = texture2D(texturePosition, uv).xyz;
  vec3 velocity = texture2D(textureVelocity, uv).xyz;
  vec3 anchor = texture2D(anchorTexture, uv).xyz;

  vec3 toAnchor = (anchor - position) * (0.26 + energy * 0.055);
  vec3 curl = vec3(
    sin(position.y * 1.7 + time * .43 + uv.y * 7.0),
    cos(position.z * 1.4 + time * .31 + uv.x * 6.0) * .55,
    sin(position.x * 1.5 - time * .37 + uv.x * 4.0)
  );
  vec3 tangent = normalize(vec3(-(position.z - anchor.z), .12, position.x - anchor.x) + vec3(.001));
  velocity += (toAnchor + curl * (.09 + energy * .045) + tangent * .055 * energy) * delta;
  velocity *= pow(.985, delta * 60.0);
  float speed = length(velocity);
  if (speed > 1.45) velocity = velocity / speed * 1.45;
  gl_FragColor = vec4(velocity, 1.0);
}
`

const pointVertex = /* glsl */`
attribute vec2 reference;
uniform sampler2D positionTexture;
uniform float uEnergy;
uniform float uTime;
varying vec2 vReference;
varying float vPulse;
void main() {
  vec3 p = texture2D(positionTexture, reference).xyz;
  float pulse = .78 + sin(uTime * 1.8 + reference.x * 31.0 + reference.y * 17.0) * .22;
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_PointSize = (2.0 + uEnergy * 1.35) * pulse * (150.0 / max(1.0, -mv.z));
  gl_Position = projectionMatrix * mv;
  vReference = reference;
  vPulse = pulse;
}
`

const pointFragment = /* glsl */`
uniform sampler2D colorTexture;
uniform float uEnergy;
varying vec2 vReference;
varying float vPulse;
void main() {
  vec2 p = gl_PointCoord - .5;
  float d = length(p);
  if (d > .5) discard;
  vec3 color = texture2D(colorTexture, vReference).rgb;
  float core = smoothstep(.5, .02, d);
  float halo = smoothstep(.5, .18, d) * .46;
  float alpha = (core + halo) * (.34 + uEnergy * .25) * vPulse;
  gl_FragColor = vec4(color * (1.2 + core * uEnergy), alpha);
}
`

export function GPGPUCapabilityNetwork({ capabilities, theme }: { capabilities: SpatialNode[]; theme: Alpha5Theme }) {
  const { gl } = useThree()

  const system = useMemo(() => {
    const gpu = new GPUComputationRenderer(SIZE, SIZE, gl)
    const positionTexture = gpu.createTexture()
    const velocityTexture = gpu.createTexture()
    const posData = positionTexture.image.data as unknown as Float32Array
    const velData = velocityTexture.image.data as unknown as Float32Array
    const random = (index: number, salt: number) => {
      const x = Math.sin(index * 91.17 + salt * 17.31) * 43758.5453
      return x - Math.floor(x)
    }

    for (let i = 0; i < COUNT; i += 1) {
      const a = anchorFor(i % 10, 10)
      const offset = i * 4
      posData[offset] = a.x + (random(i, 1) - .5) * 1.35
      posData[offset + 1] = a.y + (random(i, 2) - .5) * 1.1
      posData[offset + 2] = a.z + (random(i, 3) - .5) * 1.15
      posData[offset + 3] = 1
      velData[offset] = (random(i, 4) - .5) * .06
      velData[offset + 1] = (random(i, 5) - .5) * .04
      velData[offset + 2] = (random(i, 6) - .5) * .06
      velData[offset + 3] = 1
    }

    const anchorData = new Float32Array(COUNT * 4)
    const colorData = new Float32Array(COUNT * 4)
    const anchorTexture = new THREE.DataTexture(anchorData, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType)
    const colorTexture = new THREE.DataTexture(colorData, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType)
    anchorTexture.needsUpdate = true
    colorTexture.needsUpdate = true

    const positionVariable = gpu.addVariable('texturePosition', positionShader, positionTexture)
    const velocityVariable = gpu.addVariable('textureVelocity', velocityShader, velocityTexture)
    gpu.setVariableDependencies(positionVariable, [positionVariable, velocityVariable])
    gpu.setVariableDependencies(velocityVariable, [positionVariable, velocityVariable])
    positionVariable.material.uniforms.delta = { value: 1 / 60 }
    velocityVariable.material.uniforms.delta = { value: 1 / 60 }
    velocityVariable.material.uniforms.time = { value: 0 }
    velocityVariable.material.uniforms.energy = { value: .7 }
    velocityVariable.material.uniforms.anchorTexture = { value: anchorTexture }

    const error = gpu.init()
    if (error) console.error(`Alpha5 GPGPU init failed: ${error}`)

    const geometry = new THREE.BufferGeometry()
    const references = new Float32Array(COUNT * 2)
    for (let y = 0; y < SIZE; y += 1) {
      for (let x = 0; x < SIZE; x += 1) {
        const i = y * SIZE + x
        references[i * 2] = (x + .5) / SIZE
        references[i * 2 + 1] = (y + .5) / SIZE
      }
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3))
    geometry.setAttribute('reference', new THREE.BufferAttribute(references, 2))

    const material = new THREE.ShaderMaterial({
      uniforms: {
        positionTexture: { value: null },
        colorTexture: { value: colorTexture },
        uEnergy: { value: .7 },
        uTime: { value: 0 },
      },
      vertexShader: pointVertex,
      fragmentShader: pointFragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      toneMapped: false,
    })

    return { gpu, positionVariable, velocityVariable, anchorTexture, colorTexture, anchorData, colorData, geometry, material }
  }, [gl])

  const signature = capabilities.map((node) => `${node.id}:${String(node.data?.verificationLevel || node.state)}`).join('|')
  useEffect(() => {
    const source = capabilities.length ? capabilities : Array.from({ length: 10 }, (_, i) => ({ id: `placeholder:${i}`, state: 'unobserved', kind: 'capability', label: `capability ${i}`, data: {} } as SpatialNode))
    for (let i = 0; i < COUNT; i += 1) {
      const nodeIndex = i % source.length
      const node = source[nodeIndex]
      const anchor = anchorFor(nodeIndex, source.length)
      const offset = i * 4
      const spread = .18 + ((i / source.length) % 7) * .018
      const phase = i * 1.618
      system.anchorData[offset] = anchor.x + Math.sin(phase) * spread
      system.anchorData[offset + 1] = anchor.y + Math.cos(phase * .73) * spread
      system.anchorData[offset + 2] = anchor.z + Math.sin(phase * .51) * spread
      system.anchorData[offset + 3] = 1
      const level = String(node.data?.verificationLevel || node.state || 'unobserved')
      const color = levelColor(level, theme)
      system.colorData[offset] = color.r
      system.colorData[offset + 1] = color.g
      system.colorData[offset + 2] = color.b
      system.colorData[offset + 3] = 1
    }
    system.anchorTexture.needsUpdate = true
    system.colorTexture.needsUpdate = true
  }, [signature, capabilities, theme, system])

  useFrame((state, delta) => {
    const dt = Math.min(.033, delta)
    system.positionVariable.material.uniforms.delta.value = dt
    system.velocityVariable.material.uniforms.delta.value = dt
    system.velocityVariable.material.uniforms.time.value = state.clock.elapsedTime
    system.velocityVariable.material.uniforms.energy.value = theme.dataEnergy
    system.gpu.compute()
    system.material.uniforms.positionTexture.value = system.gpu.getCurrentRenderTarget(system.positionVariable).texture
    system.material.uniforms.uEnergy.value = theme.dataEnergy
    system.material.uniforms.uTime.value = state.clock.elapsedTime
  })

  useEffect(() => () => {
    system.geometry.dispose()
    system.material.dispose()
    system.anchorTexture.dispose()
    system.colorTexture.dispose()
    system.positionVariable.material.dispose()
    system.velocityVariable.material.dispose()
    const disposable = system.gpu as unknown as { dispose?: () => void }
    disposable.dispose?.()
  }, [system])

  return <points geometry={system.geometry} material={system.material} frustumCulled={false} />
}
