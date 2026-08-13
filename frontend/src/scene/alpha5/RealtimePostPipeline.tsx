import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js'
import { ShaderPass } from 'three/examples/jsm/postprocessing/ShaderPass.js'
import { SSRPass } from 'three/examples/jsm/postprocessing/SSRPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import type { Alpha5Theme } from './ThemeSystem'

const volumetricShader = {
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    tDepth: { value: null as THREE.Texture | null },
    uTime: { value: 0 },
    uDensity: { value: .7 },
    uAccent: { value: new THREE.Color('#66f2e4') },
    uSecondary: { value: new THREE.Color('#f0ba76') },
    uInverseProjection: { value: new THREE.Matrix4() },
    uCameraWorld: { value: new THREE.Matrix4() },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform sampler2D tDepth;
    uniform float uTime;
    uniform float uDensity;
    uniform vec3 uAccent;
    uniform vec3 uSecondary;
    uniform mat4 uInverseProjection;
    uniform mat4 uCameraWorld;
    varying vec2 vUv;

    float hash31(vec3 p) {
      p = fract(p * .1031);
      p += dot(p, p.yzx + 33.33);
      return fract((p.x + p.y) * p.z);
    }

    float noise3(vec3 p) {
      vec3 i = floor(p);
      vec3 f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      float a = hash31(i);
      float b = hash31(i + vec3(1,0,0));
      float c = hash31(i + vec3(0,1,0));
      float d = hash31(i + vec3(1,1,0));
      float e = hash31(i + vec3(0,0,1));
      float f1 = hash31(i + vec3(1,0,1));
      float g = hash31(i + vec3(0,1,1));
      float h = hash31(i + vec3(1,1,1));
      return mix(mix(mix(a,b,f.x), mix(c,d,f.x), f.y), mix(mix(e,f1,f.x), mix(g,h,f.x), f.y), f.z);
    }

    float roomMask(vec3 p) {
      return step(abs(p.x), 9.5) * step(.0, p.y) * step(p.y, 6.7) * step(-7.3, p.z) * step(p.z, 6.8);
    }

    vec3 reconstructWorld(vec2 uv, float depth) {
      vec4 clip = vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
      vec4 view = uInverseProjection * clip;
      view /= max(.0001, view.w);
      return (uCameraWorld * vec4(view.xyz, 1.0)).xyz;
    }

    void main() {
      vec4 base = texture2D(tDiffuse, vUv);
      float depth = texture2D(tDepth, vUv).x;
      vec3 cameraWorld = (uCameraWorld * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
      vec3 world = reconstructWorld(vUv, min(depth, .99995));
      vec3 ray = world - cameraWorld;
      float maxDistance = min(length(ray), 24.0);
      vec3 direction = normalize(ray + vec3(.000001));
      vec3 scattering = vec3(0.0);
      float transmittance = 1.0;

      const int STEPS = 20;
      for (int i = 0; i < STEPS; i++) {
        float t = (float(i) + .5) / float(STEPS);
        vec3 p = cameraWorld + direction * maxDistance * t;
        float mask = roomMask(p);
        float n = noise3(p * .5 + vec3(0.0, uTime * .03, uTime * .017));
        float mist = smoothstep(.48, .88, n) * .13;
        float leftBeam = exp(-pow(length(p.xz - vec2(-3.0, -.65)), 2.0) * .4) * smoothstep(.1, 5.6, p.y);
        float rightBeam = exp(-pow(length(p.xz - vec2(3.0, -.65)), 2.0) * .4) * smoothstep(.1, 5.6, p.y);
        float reactor = exp(-length(p - vec3(0.0, 2.45, .65)) * 1.25);
        float density = mask * (mist + leftBeam * .07 + rightBeam * .062 + reactor * .078) * uDensity;
        vec3 lightColor = mix(uAccent, uSecondary, clamp((p.x + 7.5) / 15.0, 0.0, 1.0));
        scattering += lightColor * density * transmittance * .11;
        transmittance *= exp(-density * .14);
      }

      vec3 color = base.rgb * mix(.94, 1.0, transmittance) + scattering * 1.45;
      gl_FragColor = vec4(color, base.a);
    }
  `,
}

const transitionShader = {
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    uProgress: { value: 1 },
    uTime: { value: 0 },
    uAccent: { value: new THREE.Color('#66f2e4') },
  },
  vertexShader: /* glsl */`
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: /* glsl */`
    uniform sampler2D tDiffuse;
    uniform float uProgress;
    uniform float uTime;
    uniform vec3 uAccent;
    varying vec2 vUv;

    float hash21(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }

    void main() {
      float strength = sin(clamp(uProgress, 0.0, 1.0) * 3.14159265);
      vec2 centered = vUv - .5;
      float radial = length(centered);
      float scan = floor(vUv.y * 92.0 + uTime * 12.0);
      float slice = (hash21(vec2(scan, floor(uTime * 9.0))) - .5) * .045 * strength;
      vec2 warped = vUv + centered * radial * .12 * strength;
      warped.x += slice * smoothstep(.1, .8, strength);
      warped += normalize(centered + vec2(.0001)) * sin(radial * 38.0 - uTime * 8.0) * .0025 * strength;

      float chroma = .0065 * strength;
      float r = texture2D(tDiffuse, warped + vec2(chroma, 0.0)).r;
      float g = texture2D(tDiffuse, warped).g;
      float b = texture2D(tDiffuse, warped - vec2(chroma, 0.0)).b;
      vec3 color = vec3(r, g, b);

      float gate = smoothstep(.0, .025, abs(fract((vUv.y + uProgress * 1.25) * 3.0) - .5));
      float line = (1.0 - gate) * strength;
      color += uAccent * line * .42;
      color += uAccent * pow(max(0.0, 1.0 - abs(radial - (.08 + uProgress * .62)) * 13.0), 3.0) * strength * .18;
      float vignette = smoothstep(.82, .24, radial);
      color *= mix(.82 + vignette * .18, 1.0, 1.0 - strength * .15);
      gl_FragColor = vec4(color, 1.0);
    }
  `,
}

export function RealtimePostPipeline({ theme, transitionKey }: { theme: Alpha5Theme; transitionKey: string }) {
  const { gl, scene, camera, size } = useThree()
  const age = useRef(1)

  const pipeline = useMemo(() => {
    const composer = new EffectComposer(gl)
    composer.setPixelRatio(Math.min(gl.getPixelRatio(), 1.35))

    const ssr = new SSRPass({ renderer: gl, scene, camera, width: Math.max(1, size.width), height: Math.max(1, size.height) })
    ssr.opacity = .46
    ssr.maxDistance = 4.2
    ssr.thickness = .075
    ssr.blur = true
    ssr.distanceAttenuation = true
    ssr.fresnel = true
    ssr.infiniteThick = false

    const volumetric = new ShaderPass(volumetricShader)
    volumetric.uniforms.tDepth.value = ssr.beautyRenderTarget.depthTexture
    const bloom = new UnrealBloomPass(new THREE.Vector2(size.width, size.height), 1.15, .5, .78)
    const transition = new ShaderPass(transitionShader)
    const output = new OutputPass()

    composer.addPass(ssr)
    composer.addPass(volumetric)
    composer.addPass(bloom)
    composer.addPass(transition)
    composer.addPass(output)

    return { composer, ssr, volumetric, bloom, transition, output }
  }, [gl, scene, camera])

  useEffect(() => {
    pipeline.composer.setSize(size.width, size.height)
    pipeline.composer.setPixelRatio(Math.min(gl.getPixelRatio(), 1.35))
    pipeline.ssr.setSize(size.width, size.height)
    pipeline.bloom.setSize(size.width, size.height)
  }, [size.width, size.height, gl, pipeline])

  useEffect(() => {
    age.current = 0
  }, [transitionKey])

  useFrame((state, delta) => {
    age.current = Math.min(1, age.current + delta / .95)
    camera.updateMatrixWorld()

    pipeline.volumetric.uniforms.uTime.value = state.clock.elapsedTime
    pipeline.volumetric.uniforms.uDensity.value = THREE.MathUtils.damp(pipeline.volumetric.uniforms.uDensity.value, theme.volumeDensity, 2.6, delta)
    pipeline.volumetric.uniforms.uInverseProjection.value.copy((camera as THREE.PerspectiveCamera).projectionMatrixInverse)
    pipeline.volumetric.uniforms.uCameraWorld.value.copy(camera.matrixWorld)
    ;(pipeline.volumetric.uniforms.uAccent.value as THREE.Color).lerp(new THREE.Color(theme.accent), 1 - Math.exp(-delta * 2.8))
    ;(pipeline.volumetric.uniforms.uSecondary.value as THREE.Color).lerp(new THREE.Color(theme.secondary), 1 - Math.exp(-delta * 2.8))

    pipeline.transition.uniforms.uProgress.value = age.current
    pipeline.transition.uniforms.uTime.value = state.clock.elapsedTime
    ;(pipeline.transition.uniforms.uAccent.value as THREE.Color).lerp(new THREE.Color(theme.accent), 1 - Math.exp(-delta * 3.2))

    pipeline.bloom.strength = THREE.MathUtils.damp(pipeline.bloom.strength, theme.bloom, 3, delta)
    pipeline.ssr.opacity = THREE.MathUtils.damp(pipeline.ssr.opacity, .34 + theme.dataEnergy * .12, 2.8, delta)
    pipeline.ssr.maxDistance = THREE.MathUtils.damp(pipeline.ssr.maxDistance, 3.6 + theme.dataEnergy * .8, 2.4, delta)
    pipeline.composer.render(delta)
  }, 1)

  useEffect(() => () => {
    pipeline.ssr.dispose()
    pipeline.volumetric.dispose()
    pipeline.bloom.dispose()
    pipeline.transition.dispose()
    pipeline.output.dispose()
    pipeline.composer.dispose()
  }, [pipeline])

  return null
}
