import { useFrame } from '@react-three/fiber'
import { useEffect, useMemo } from 'react'
import * as THREE from 'three'

type Props = {
  color: string
  glitch?: number
  scanSpeed?: number
  intensity?: number
  seed?: number
}

const vertexShader = /* glsl */`
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`

const fragmentShader = /* glsl */`
  precision highp float;
  varying vec2 vUv;
  uniform float uTime;
  uniform float uGlitch;
  uniform float uScanSpeed;
  uniform float uIntensity;
  uniform float uSeed;
  uniform vec3 uAccent;

  float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    p += dot(p, p + 34.345 + uSeed);
    return fract(p.x * p.y);
  }

  float sdLine(float y, float width) {
    return smoothstep(width, 0.0, abs(y));
  }

  void main() {
    vec2 uv = vUv;
    float t = uTime * uScanSpeed;
    float burst = step(0.94, hash(vec2(floor(uTime * 5.0), uSeed))) * uGlitch;
    float slice = step(0.72, hash(vec2(floor(uv.y * 19.0), floor(uTime * 8.0) + uSeed)));
    uv.x += (slice - 0.5) * burst * 0.09;

    float gridX = smoothstep(0.97, 1.0, abs(sin(uv.x * 42.0)));
    float gridY = smoothstep(0.985, 1.0, abs(sin(uv.y * 28.0)));
    float grid = max(gridX * 0.13, gridY * 0.1);

    float scanY = fract(t * 0.18);
    float scan = sdLine(uv.y - scanY, 0.012) * 1.7 + sdLine(uv.y - fract(scanY + 0.44), 0.004) * 0.45;

    float wave = sin(uv.x * 18.0 + t * 2.8) * 0.035 + sin(uv.x * 43.0 - t * 1.4) * 0.018;
    float trace = sdLine(uv.y - (0.52 + wave), 0.008);
    float trace2 = sdLine(uv.y - (0.35 + sin(uv.x * 12.0 - t * 2.1) * 0.025), 0.005) * 0.45;

    float edge = smoothstep(0.16, 0.0, min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y)));
    float noise = hash(uv * vec2(710.0, 390.0) + floor(uTime * 18.0)) * 0.08;

    vec3 base = vec3(0.004, 0.014, 0.019);
    vec3 glow = uAccent * (grid + scan + trace * 1.55 + trace2 + noise);
    glow += uAccent * edge * 0.08;

    float glitchBand = step(0.83, hash(vec2(floor(uv.y * 15.0), floor(uTime * 10.0)))) * burst;
    glow.rb += vec2(glitchBand * 0.42, glitchBand * 0.28);

    vec3 color = base + glow * uIntensity;
    float vignette = smoothstep(0.95, 0.22, length(uv - 0.5));
    color *= 0.58 + vignette * 0.58;
    gl_FragColor = vec4(color, 1.0);
  }
`

export function ShaderScreen({ color, glitch = .45, scanSpeed = 1, intensity = 1, seed = 1 }: Props) {
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uGlitch: { value: glitch },
      uScanSpeed: { value: scanSpeed },
      uIntensity: { value: intensity },
      uSeed: { value: seed },
      uAccent: { value: new THREE.Color(color) },
    },
    toneMapped: false,
  }), [color, glitch, scanSpeed, intensity, seed])

  useEffect(() => () => material.dispose(), [material])
  useFrame((state) => {
    material.uniforms.uTime.value = state.clock.elapsedTime
  })

  return <primitive object={material} attach="material" />
}
