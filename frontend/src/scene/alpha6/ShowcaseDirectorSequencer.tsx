import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { SHOWCASE_CLIPS, sampleTrack, smooth01 } from './ShowcaseSequenceConfig'
import { showcaseProgress, type ShowcaseRuntimeState } from './ShowcaseRuntime'

export function ShowcaseDirectorSequencer({ runtime }: { runtime: ShowcaseRuntimeState }) {
  const { camera } = useThree()
  const position = new THREE.Vector3()
  const target = new THREE.Vector3()

  useFrame((state, delta) => {
    if (!runtime.active || !runtime.clip) return
    const clip = SHOWCASE_CLIPS[runtime.clip]
    const progress = showcaseProgress(runtime, state.clock.elapsedTime)
    const sample = sampleTrack(clip.camera, progress)
    const t = sample.a.ease === 'linear' ? sample.t : smooth01(sample.t)
    position.set(
      THREE.MathUtils.lerp(sample.a.position[0], sample.b.position[0], t),
      THREE.MathUtils.lerp(sample.a.position[1], sample.b.position[1], t),
      THREE.MathUtils.lerp(sample.a.position[2], sample.b.position[2], t),
    )
    target.set(
      THREE.MathUtils.lerp(sample.a.target[0], sample.b.target[0], t),
      THREE.MathUtils.lerp(sample.a.target[1], sample.b.target[1], t),
      THREE.MathUtils.lerp(sample.a.target[2], sample.b.target[2], t),
    )
    const camera3d = camera as THREE.PerspectiveCamera
    const response = sample.a.ease === 'cinematic' ? 5.2 : 7.5
    camera3d.position.lerp(position, 1 - Math.exp(-delta * response))
    camera3d.fov = THREE.MathUtils.damp(camera3d.fov, THREE.MathUtils.lerp(sample.a.fov, sample.b.fov, t), response, delta)
    camera3d.updateProjectionMatrix()
    const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(camera3d.quaternion)
    const currentTarget = camera3d.position.clone().add(forward.multiplyScalar(5))
    currentTarget.lerp(target, 1 - Math.exp(-delta * response))
    camera3d.lookAt(currentTarget)
  }, -1)

  return null
}
