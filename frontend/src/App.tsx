import { useMemo, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import type { SpatialNode } from './api/types'
import { FoundationPanel } from './features/FoundationPanel'
import { WorkSamplePanel } from './features/WorkSamplePanel'
import { ShowcaseCGWorkLab } from './scene/ShowcaseCGWorkLab'
import { useSceneState } from './state/SceneStateProvider'

function levelLabel(value: string) {
  return ({
    unobserved: '尚未形成信号',
    signal: 'Signal · 已观察到',
    evidence: 'Evidence · 多情境证据',
    verified_evidence: 'Verified Evidence · 已核验',
  } as Record<string, string>)[value] || value
}

function Inspector({ node, onClose }: { node: SpatialNode; onClose: () => void }) {
  const data = node.data || {}
  const nextRequired = Array.isArray(data.nextRequired) ? data.nextRequired : []
  return (
    <section className="inspector">
      <div className="inspector-head"><div><span>{node.kind}</span><strong>{node.label}</strong></div><button onClick={onClose}>×</button></div>
      <div className="inspector-status"><span>Server state</span><strong>{node.kind === 'capability' ? levelLabel(String(data.verificationLevel || node.state)) : node.state}</strong></div>
      {node.kind === 'capability' && <>
        <p>{data.plain}</p>
        <div className="metric-grid">
          <div><small>任务情境</small><strong>{data.metrics?.distinctTaskContexts ?? 0}</strong></div>
          <div><small>独立完成</small><strong>{data.metrics?.independent ?? 0}</strong></div>
          <div><small>迁移成功</small><strong>{data.metrics?.transferSuccesses ?? 0}</strong></div>
          <div><small>核验证据</small><strong>{data.metrics?.verifiedEvidenceCount ?? 0}</strong></div>
        </div>
        {nextRequired.length > 0 && <div className="next-required"><small>离下一层还差什么</small>{nextRequired.map((item: string) => <p key={item}>{item}</p>)}</div>}
      </>}
      {node.kind === 'evidence' && <p>验证状态：{String(data.verificationStatus || 'SELF_REPORTED')}。3D 只读取该状态，不会自行升级 Evidence。</p>}
      {node.kind === 'artifact' && <p>服务器保存的 {String(data.kind || 'artifact')} 版本 V{String(data.version || 1)}。历史版本不会被场景动画覆盖。</p>}
      {node.kind === 'trajectory_event' && <p>{String(data.taskId || '实践过程')} · {String(data.at || '')}</p>}
      {node.kind === 'workstation' && node.state === 'locked' && <p>该工作站当前由服务器锁定。SceneState 变化后空间表现才会同步改变。</p>}
      <footer>authority=server · readOnly=true</footer>
    </section>
  )
}

function SpatialShell() {
  const { scene, loading, refreshing, error, lastSyncedAt, refresh } = useSceneState()
  const location = useLocation()
  const navigate = useNavigate()
  const [inspected, setInspected] = useState<SpatialNode | null>(null)

  const focus = location.pathname.endsWith('/foundation') ? 'foundation' : location.pathname.endsWith('/work-sample') ? 'work-sample' : 'hub'
  const nodes = scene?.spatial?.nodes || []
  const connections = scene?.spatial?.connections || []
  const verified = scene?.capabilities?.summary?.verified_evidence || 0
  const evidence = scene?.capabilities?.summary?.evidence || 0
  const signal = scene?.capabilities?.summary?.signal || 0
  const currentTask = scene?.foundation?.currentTask || null
  const currentTaskTitle = currentTask?.title || (scene?.foundation?.foundationComplete ? '基础动作已完成' : '正在同步当前任务')

  const headline = useMemo(() => {
    if (!scene) return '正在进入 Work Lab'
    if (focus === 'foundation') return currentTaskTitle
    if (focus === 'work-sample') return scene.workSample.definition.title
    return currentTaskTitle
  }, [scene, focus, currentTaskTitle])

  if (loading && !scene) return <main className="boot-screen"><div className="boot-mark">S</div><h1>StepIn Work Lab</h1><p>正在读取服务器 SceneState…</p></main>
  if (!scene) return <main className="boot-screen error"><div className="boot-mark">!</div><h1>暂时无法进入 Work Lab</h1><p>{error}</p><button className="primary-button" onClick={() => void refresh()}>重试</button><a href="/static/foundation.html">打开旧工作台</a></main>

  return (
    <main className="spatial-shell">
      <div className="scene-layer">
        <ShowcaseCGWorkLab
          nodes={nodes}
          connections={connections}
          focus={focus}
          onFocus={(next) => navigate(next === 'hub' ? '/' : `/${next}`)}
          onInspect={setInspected}
        />
      </div>

      <header className="topbar glass">
        <button className="brand-button" onClick={() => navigate('/')}><span>S</span><div><strong>StepIn</strong><small>Spatial Practice Alpha 7 · Adaptive Showcase</small></div></button>
        <div className="now-context"><span>现在只做这一件事</span><strong>{headline}</strong></div>
        <div className="sync-state"><span className={refreshing ? 'sync-dot active' : 'sync-dot'} />{refreshing ? '同步中' : '服务器已同步'}<small>{lastSyncedAt ? new Date(lastSyncedAt).toLocaleTimeString() : ''}</small></div>
      </header>

      <nav className="dock glass" aria-label="Work Lab navigation">
        <button className={focus === 'hub' ? 'active' : ''} onClick={() => navigate('/')}><span>◫</span><small>Adaptive Showcase</small></button>
        <button className={focus === 'foundation' ? 'active' : ''} onClick={() => navigate('/foundation')}><span>01</span><small>Foundation</small></button>
        <button className={focus === 'work-sample' ? 'active' : ''} onClick={() => navigate('/work-sample')}><span>02</span><small>Work Sample</small></button>
        <button onClick={() => setInspected(nodes.find((node) => node.kind === 'capability') || null)}><span>{verified}</span><small>Verified</small></button>
      </nav>

      <section className="growth-strip glass">
        <div><small>Signal</small><strong>{signal}</strong></div>
        <div><small>Evidence</small><strong>{evidence}</strong></div>
        <div><small>Verified</small><strong>{verified}</strong></div>
        <div><small>Evidence items</small><strong>{scene.evidence.count}</strong></div>
        <div><small>Trajectory</small><strong>{scene.trajectory.summary?.events || 0}</strong></div>
      </section>

      {error && <button className="sync-warning" onClick={() => void refresh()}>{error} · 点击重试</button>}

      <Routes>
        <Route path="/" element={null} />
        <Route path="/foundation" element={<FoundationPanel task={currentTask} mode={scene.foundation.mode} progress={scene.foundation.progress || 0} onClose={() => navigate('/')} onChanged={refresh} />} />
        <Route path="/work-sample" element={<WorkSamplePanel workSample={scene.workSample} onClose={() => navigate('/')} onChanged={refresh} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      {inspected && <Inspector node={inspected} onClose={() => setInspected(null)} />}
      <div className="authority-badge">ADAPTIVE SHOWCASE READS SERVER STATE · RENDER QUALITY DOES NOT AWARD GROWTH</div>
    </main>
  )
}

export default function App() {
  return <SpatialShell />
}
