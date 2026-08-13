import { useFrame } from '@react-three/fiber'
import { useMemo } from 'react'
import * as THREE from 'three'
import type { Alpha5Theme } from './ThemeSystem'

const vertexShader = /* glsl */`
varying vec3 vWorldPosition;
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorldPosition = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}
`

const fragmentShader = /* glsl */`
uniform float uTime;
uniform float uDensity;
uniform vec3 uAccent;
uniform vec3 uSecondary;
varying vec3 vWorldPosition;

float hash31(vec3 p) {
  p = fract(p * .1031);
  p += dot(p, p.yzx + 33.33);
  return fract((p.x + p.y) * p.z);
}

float noise3(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float n000 = hash31(i + vec3(0,0,0));
  float n100 = hash31(i + vec3(1,0,0));
  float n010 = hash31(i + vec3(0,1,0));
  float n110 = hash31(i + vec3(1,1,0));
  float n001 = hash31(i + vec3(0,0,1));
  float n101 = hash31(i + vec3(1,0,1));
  float n011 = hash31(i + vec3(0,1,1));
  float n111 = hash31(i + vec3(1,1,1));
  return mix(mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y), mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y), f.z);
}

float insideRoom(vec3 p) {
  float x = step(abs(p.x), 9.3);
  float y = step(.05, p.y) * step(p.y, 6.5);
  float z = step(-7.0, p.z) * step(p.z, 6.8);
  return x * y * z;
}

void main() {
  vec3 ray = vWorldPosition - cameraPosition;
  float maxDistance = length(ray);
  vec3 direction = ray / max(maxDistance, .0001);
  vec3 accumulated = vec3(0.0);
  float alpha = 0.0;

  const int STEPS = 30;
  for (int i = 0; i < STEPS; i++) {
    float t = (float(i) + .5) / float(STEPS);
    vec3 p = cameraPosition + direction * maxDistance * t;
    float mask = insideRoom(p);
    float n = noise3(p * .48 + vec3(0.0, uTime * .035, uTime * .018));
    float mist = smoothstep(.42, .86, n) * .17;
    float leftBeam = exp(-pow(length(p.xz - vec2(-3.05, -.65)), 2.0) * .36) * smoothstep(0.0, 5.3, p.y);
    float rightBeam = exp(-pow(length(p.xz - vec2(3.05, -.65)), 2.0) * .36) * smoothstep(0.0, 5.3, p.y);
    float reactor = exp(-length(p - vec3(0.0, 2.4, .7)) * 1.3);
    float density = mask * (mist + leftBeam * .075 + rightBeam * .065 + reactor * .085) * uDensity;
    vec3 lightColor = mix(uAccent, uSecondary, clamp((p.x + 7.0) / 14.0, 0.0, 1.0));
    accumulated += lightColor * density * (1.0 - alpha);
    alpha += density * .085 * (1.0 - alpha);
  }

  float edgeFade = smoothstep(0.0, .24, alpha);
  gl_FragColor = vec4(accumulated * 1.65, alpha * edgeFade * .72);
}
`

export function VolumetricField({ theme }: { theme: Alpha5Theme }) {
  const material = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uDensity: { value: theme.volumeDensity },
      uAccent: { value: new THREE.Color(theme.accent) },
      uSecondary: { value: new THREE.Color(theme.secondary) },
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
  }), [])

  useFrame((state, delta) => {
    material.uniforms.uTime.value = state.clock.elapsedTime
    material.uniforms.uDensity.value = THREE.MathUtils.damp(material.uniforms.uDensity.value, theme.volumeDensity, 2.4, delta)
    material.uniforms.uAccent.value.lerp(new THREE.Color(theme.accent), 1 - Math.exp(-delta * 2.3))
    material.uniforms.uSecondary.value.lerp(new THREE.Color(theme.secondary), 1 - Math.exp(-delta * 2.3))
  })

  return (
    <mesh position={[0, 3.25, -.1]} material={material} renderOrder={20} frustumCulled={false}>
      <boxGeometry args={[18.6, 6.5, 13.8]} />
    </mesh>
  )
}
