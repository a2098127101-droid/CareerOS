export type Vec3 = [number, number, number]

export type ShowcaseClipName =
  | 'establishing'
  | 'topology_reflow'
  | 'evidence_scan'
  | 'artifact_destruction'
  | 'artifact_assembly'
  | 'room_transformation'
  | 'grand_finale'
  | 'server_verification'
  | 'server_awakening'
  | 'server_revision'
  | 'server_transfer'
  | 'server_completed'

export type CameraKeyframe = {
  at: number
  position: Vec3
  target: Vec3
  fov: number
  ease?: 'linear' | 'smooth' | 'cinematic'
}

export type LightingKeyframe = {
  at: number
  keyIntensity: number
  accentIntensity: number
  secondaryIntensity: number
  rimIntensity: number
  exposure: number
  fogBoost: number
  pulse: number
}

export type RoomKeyframe = {
  at: number
  transform: number
  wings: number
  iris: number
  gantry: number
  ceiling: number
  reactor: number
}

export type ArtifactKeyframe = {
  at: number
  explode: number
  assemble: number
  spin: number
  scatter: number
  feedback: number
}

export type TopologyKeyframe = {
  at: number
  reflow: number
  orbit: number
  attraction: number
  turbulence: number
}

export type ShowcaseClip = {
  name: ShowcaseClipName
  duration: number
  camera: CameraKeyframe[]
  lighting: LightingKeyframe[]
  room: RoomKeyframe[]
  artifact: ArtifactKeyframe[]
  topology: TopologyKeyframe[]
}

const camera = (...frames: CameraKeyframe[]) => frames
const lighting = (...frames: LightingKeyframe[]) => frames
const room = (...frames: RoomKeyframe[]) => frames
const artifact = (...frames: ArtifactKeyframe[]) => frames
const topology = (...frames: TopologyKeyframe[]) => frames

export const SHOWCASE_CLIPS: Record<ShowcaseClipName, ShowcaseClip> = {
  establishing: {
    name: 'establishing', duration: 6.5,
    camera: camera(
      { at: 0, position: [0, 8.2, 19.8], target: [0, 2.3, -.4], fov: 43, ease: 'cinematic' },
      { at: .48, position: [-7.6, 5.5, 11.8], target: [0, 2.5, -.2], fov: 39, ease: 'smooth' },
      { at: 1, position: [0, 6.8, 15.8], target: [0, 2.25, -.8], fov: 40, ease: 'cinematic' },
    ),
    lighting: lighting(
      { at: 0, keyIntensity: .7, accentIntensity: .45, secondaryIntensity: .4, rimIntensity: .25, exposure: .92, fogBoost: .2, pulse: 0 },
      { at: .6, keyIntensity: 1, accentIntensity: .9, secondaryIntensity: .8, rimIntensity: .72, exposure: 1.02, fogBoost: .45, pulse: .2 },
      { at: 1, keyIntensity: .86, accentIntensity: .72, secondaryIntensity: .65, rimIntensity: .52, exposure: 1, fogBoost: .3, pulse: 0 },
    ),
    room: room({ at: 0, transform: .08, wings: .04, iris: .12, gantry: .05, ceiling: .08, reactor: .2 }, { at: 1, transform: .2, wings: .18, iris: .25, gantry: .14, ceiling: .2, reactor: .35 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .1, scatter: 0, feedback: 0 }, { at: 1, explode: 0, assemble: 1, spin: .16, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .1, orbit: .18, attraction: .8, turbulence: .2 }, { at: 1, reflow: .2, orbit: .26, attraction: .9, turbulence: .25 }),
  },
  topology_reflow: {
    name: 'topology_reflow', duration: 7.5,
    camera: camera(
      { at: 0, position: [0, 5.8, 12.8], target: [0, 3.45, -5.8], fov: 38 },
      { at: .45, position: [-4.8, 4.9, 6.2], target: [0, 3.5, -6], fov: 34, ease: 'cinematic' },
      { at: 1, position: [4.6, 5.2, 7.3], target: [0, 3.45, -5.9], fov: 35, ease: 'smooth' },
    ),
    lighting: lighting({ at: 0, keyIntensity: .8, accentIntensity: 1, secondaryIntensity: .55, rimIntensity: .8, exposure: 1, fogBoost: .55, pulse: .25 }, { at: .55, keyIntensity: 1.05, accentIntensity: 1.5, secondaryIntensity: .75, rimIntensity: 1.25, exposure: 1.08, fogBoost: .85, pulse: 1 }, { at: 1, keyIntensity: .9, accentIntensity: 1.05, secondaryIntensity: .65, rimIntensity: .9, exposure: 1.02, fogBoost: .62, pulse: .35 }),
    room: room({ at: 0, transform: .2, wings: .2, iris: .25, gantry: .2, ceiling: .2, reactor: .35 }, { at: 1, transform: .45, wings: .38, iris: .55, gantry: .42, ceiling: .48, reactor: .65 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .12, scatter: 0, feedback: 0 }, { at: 1, explode: 0, assemble: 1, spin: .2, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .2, orbit: .3, attraction: .9, turbulence: .25 }, { at: .55, reflow: 1, orbit: 1, attraction: 1.55, turbulence: 1.2 }, { at: 1, reflow: .7, orbit: .72, attraction: 1.15, turbulence: .55 }),
  },
  evidence_scan: {
    name: 'evidence_scan', duration: 6.5,
    camera: camera({ at: 0, position: [-7.8, 4.6, 7.4], target: [-6, 2.35, -1.2], fov: 36 }, { at: .55, position: [-5.7, 3.3, 2.4], target: [-6, 2.4, -1.1], fov: 31, ease: 'cinematic' }, { at: 1, position: [-2.6, 4.7, 8.7], target: [-3.5, 2.8, -2.8], fov: 37 }),
    lighting: lighting({ at: 0, keyIntensity: .72, accentIntensity: .7, secondaryIntensity: 1.05, rimIntensity: .7, exposure: .98, fogBoost: .5, pulse: .1 }, { at: .5, keyIntensity: .9, accentIntensity: 1.1, secondaryIntensity: 1.65, rimIntensity: 1.15, exposure: 1.08, fogBoost: .82, pulse: .9 }, { at: 1, keyIntensity: .82, accentIntensity: .85, secondaryIntensity: 1.1, rimIntensity: .82, exposure: 1.02, fogBoost: .55, pulse: .2 }),
    room: room({ at: 0, transform: .3, wings: .32, iris: .35, gantry: .25, ceiling: .3, reactor: .5 }, { at: 1, transform: .42, wings: .46, iris: .5, gantry: .38, ceiling: .4, reactor: .58 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .15, scatter: 0, feedback: 0 }, { at: 1, explode: 0, assemble: 1, spin: .22, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .55, orbit: .5, attraction: 1, turbulence: .35 }, { at: 1, reflow: .7, orbit: .6, attraction: 1.12, turbulence: .42 }),
  },
  artifact_destruction: {
    name: 'artifact_destruction', duration: 7,
    camera: camera({ at: 0, position: [5.7, 4.1, 7.4], target: [3.4, 1.65, 1.8], fov: 36 }, { at: .52, position: [4.4, 2.7, 4.6], target: [3.35, 1.7, 1.8], fov: 31, ease: 'cinematic' }, { at: 1, position: [6.2, 4.3, 8.3], target: [3.2, 1.8, 1.5], fov: 37 }),
    lighting: lighting({ at: 0, keyIntensity: .78, accentIntensity: .55, secondaryIntensity: 1.1, rimIntensity: .6, exposure: .96, fogBoost: .45, pulse: .15 }, { at: .5, keyIntensity: .62, accentIntensity: .4, secondaryIntensity: 1.8, rimIntensity: 1.35, exposure: .9, fogBoost: .9, pulse: 1 }, { at: 1, keyIntensity: .8, accentIntensity: .7, secondaryIntensity: 1.2, rimIntensity: .8, exposure: 1, fogBoost: .6, pulse: .35 }),
    room: room({ at: 0, transform: .42, wings: .42, iris: .5, gantry: .38, ceiling: .42, reactor: .58 }, { at: 1, transform: .55, wings: .55, iris: .65, gantry: .52, ceiling: .58, reactor: .72 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .12, scatter: 0, feedback: 0 }, { at: .46, explode: 1, assemble: .05, spin: 1, scatter: 1, feedback: 1 }, { at: 1, explode: .82, assemble: .18, spin: .65, scatter: .7, feedback: 1 }),
    topology: topology({ at: 0, reflow: .55, orbit: .5, attraction: 1, turbulence: .4 }, { at: 1, reflow: .65, orbit: .62, attraction: .95, turbulence: .55 }),
  },
  artifact_assembly: {
    name: 'artifact_assembly', duration: 7,
    camera: camera({ at: 0, position: [6, 4.2, 7.8], target: [3.35, 1.7, 1.8], fov: 36 }, { at: .5, position: [4.15, 2.85, 4.2], target: [3.3, 1.65, 1.75], fov: 30, ease: 'cinematic' }, { at: 1, position: [2.4, 4.8, 9.2], target: [2.7, 1.9, .8], fov: 38 }),
    lighting: lighting({ at: 0, keyIntensity: .75, accentIntensity: .65, secondaryIntensity: 1.25, rimIntensity: .72, exposure: .96, fogBoost: .55, pulse: .2 }, { at: .55, keyIntensity: 1, accentIntensity: 1.4, secondaryIntensity: 1.25, rimIntensity: 1.4, exposure: 1.08, fogBoost: .85, pulse: 1 }, { at: 1, keyIntensity: .9, accentIntensity: 1, secondaryIntensity: .85, rimIntensity: .92, exposure: 1.04, fogBoost: .55, pulse: .25 }),
    room: room({ at: 0, transform: .55, wings: .55, iris: .65, gantry: .52, ceiling: .58, reactor: .72 }, { at: 1, transform: .68, wings: .68, iris: .78, gantry: .65, ceiling: .7, reactor: .82 }),
    artifact: artifact({ at: 0, explode: .82, assemble: .18, spin: .7, scatter: .72, feedback: 1 }, { at: .58, explode: .15, assemble: .88, spin: .36, scatter: .18, feedback: .35 }, { at: 1, explode: 0, assemble: 1, spin: .18, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .6, orbit: .58, attraction: 1, turbulence: .48 }, { at: 1, reflow: .72, orbit: .7, attraction: 1.2, turbulence: .35 }),
  },
  room_transformation: {
    name: 'room_transformation', duration: 8,
    camera: camera({ at: 0, position: [0, 6.5, 15.4], target: [0, 2.5, 0], fov: 40 }, { at: .5, position: [-8.8, 5.8, 9.8], target: [0, 2.9, -.2], fov: 38, ease: 'cinematic' }, { at: 1, position: [8.4, 6.2, 10.5], target: [0, 2.8, -.5], fov: 39 }),
    lighting: lighting({ at: 0, keyIntensity: .85, accentIntensity: .82, secondaryIntensity: .72, rimIntensity: .75, exposure: 1, fogBoost: .5, pulse: .15 }, { at: .5, keyIntensity: 1.2, accentIntensity: 1.5, secondaryIntensity: 1.35, rimIntensity: 1.6, exposure: 1.12, fogBoost: 1, pulse: 1 }, { at: 1, keyIntensity: 1.05, accentIntensity: 1.2, secondaryIntensity: 1.05, rimIntensity: 1.25, exposure: 1.08, fogBoost: .75, pulse: .45 }),
    room: room({ at: 0, transform: .25, wings: .2, iris: .25, gantry: .2, ceiling: .22, reactor: .35 }, { at: .6, transform: 1, wings: 1, iris: 1, gantry: 1, ceiling: 1, reactor: 1 }, { at: 1, transform: .88, wings: .9, iris: .95, gantry: .88, ceiling: .92, reactor: 1 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .15, scatter: 0, feedback: 0 }, { at: 1, explode: 0, assemble: 1, spin: .4, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .55, orbit: .55, attraction: 1, turbulence: .35 }, { at: 1, reflow: .85, orbit: .92, attraction: 1.3, turbulence: .5 }),
  },
  grand_finale: {
    name: 'grand_finale', duration: 8.5,
    camera: camera({ at: 0, position: [8.4, 6.2, 10.5], target: [0, 2.8, -.5], fov: 39 }, { at: .38, position: [0, 8.4, 13.2], target: [0, 2.6, -2.4], fov: 38, ease: 'cinematic' }, { at: .7, position: [-6.5, 4.8, 8.4], target: [0, 2.7, -2.2], fov: 35 }, { at: 1, position: [0, 7.2, 18.4], target: [0, 2.35, -.8], fov: 40, ease: 'cinematic' }),
    lighting: lighting({ at: 0, keyIntensity: 1, accentIntensity: 1.1, secondaryIntensity: 1, rimIntensity: 1.1, exposure: 1.05, fogBoost: .7, pulse: .3 }, { at: .55, keyIntensity: 1.5, accentIntensity: 1.85, secondaryIntensity: 1.55, rimIntensity: 2, exposure: 1.2, fogBoost: 1.25, pulse: 1 }, { at: 1, keyIntensity: .92, accentIntensity: .85, secondaryIntensity: .75, rimIntensity: .82, exposure: 1, fogBoost: .4, pulse: 0 }),
    room: room({ at: 0, transform: .88, wings: .9, iris: .95, gantry: .88, ceiling: .92, reactor: 1 }, { at: .6, transform: 1, wings: 1, iris: 1, gantry: 1, ceiling: 1, reactor: 1 }, { at: 1, transform: .3, wings: .28, iris: .35, gantry: .3, ceiling: .32, reactor: .48 }),
    artifact: artifact({ at: 0, explode: 0, assemble: 1, spin: .35, scatter: 0, feedback: 0 }, { at: .55, explode: .18, assemble: .95, spin: 1, scatter: .15, feedback: .2 }, { at: 1, explode: 0, assemble: 1, spin: .12, scatter: 0, feedback: 0 }),
    topology: topology({ at: 0, reflow: .82, orbit: .9, attraction: 1.2, turbulence: .45 }, { at: .55, reflow: 1, orbit: 1.4, attraction: 1.65, turbulence: .9 }, { at: 1, reflow: .28, orbit: .3, attraction: .9, turbulence: .22 }),
  },
  server_verification: null as never,
  server_awakening: null as never,
  server_revision: null as never,
  server_transfer: null as never,
  server_completed: null as never,
}

function cloneClip(name: ShowcaseClipName, source: ShowcaseClipName, duration: number): ShowcaseClip {
  const base = SHOWCASE_CLIPS[source]
  return { ...base, name, duration }
}

SHOWCASE_CLIPS.server_verification = cloneClip('server_verification', 'evidence_scan', 6.5)
SHOWCASE_CLIPS.server_awakening = cloneClip('server_awakening', 'grand_finale', 7.2)
SHOWCASE_CLIPS.server_revision = cloneClip('server_revision', 'artifact_destruction', 6.8)
SHOWCASE_CLIPS.server_transfer = cloneClip('server_transfer', 'artifact_assembly', 6.8)
SHOWCASE_CLIPS.server_completed = cloneClip('server_completed', 'grand_finale', 7.5)

export const AUTO_DEMO_ORDER: ShowcaseClipName[] = [
  'establishing',
  'topology_reflow',
  'evidence_scan',
  'artifact_destruction',
  'artifact_assembly',
  'room_transformation',
  'grand_finale',
]

export function sampleTrack<T extends { at: number }>(track: T[], progress: number): { a: T; b: T; t: number } {
  if (track.length === 1) return { a: track[0], b: track[0], t: 0 }
  const p = Math.max(0, Math.min(1, progress))
  let upper = track.findIndex((frame) => frame.at >= p)
  if (upper <= 0) return { a: track[0], b: track[0], t: 0 }
  if (upper === -1) upper = track.length - 1
  const a = track[upper - 1]
  const b = track[upper]
  const span = Math.max(.00001, b.at - a.at)
  return { a, b, t: Math.max(0, Math.min(1, (p - a.at) / span)) }
}

export function smooth01(value: number) {
  const t = Math.max(0, Math.min(1, value))
  return t * t * (3 - 2 * t)
}
