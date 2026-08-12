import { useEffect, useMemo, useState } from 'react'
import { foundationApi } from '../api/client'
import type { FoundationTask } from '../api/types'

type Props = {
  task?: FoundationTask | null
  mode: string
  progress: number
  onClose: () => void
  onChanged: () => Promise<void>
}

function itemText(item: any) {
  return item?.title || item?.text || item?.name || item?.id || ''
}

export function FoundationPanel({ task, mode, progress, onClose, onChanged }: Props) {
  const [answer, setAnswer] = useState<Record<string, any>>({})
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string[]>([])
  const [hint, setHint] = useState('')

  useEffect(() => {
    setAnswer(task?.type === 'order' ? { order: (task.data?.items || []).map((item: any) => item.id), reason: '' } : {})
    setMessage([])
    setHint('')
  }, [task?.id])

  const data = task?.data || {}
  const items = useMemo(() => (data.items || data.issues || data.facts || []) as any[], [data])

  function toggle(id: string, key = 'selected') {
    const current = new Set<string>(answer[key] || [])
    current.has(id) ? current.delete(id) : current.add(id)
    setAnswer({ ...answer, [key]: [...current] })
  }

  function move(id: string, delta: number) {
    const order = [...(answer.order || items.map((item) => item.id))]
    const index = order.indexOf(id)
    const target = index + delta
    if (index < 0 || target < 0 || target >= order.length) return
    ;[order[index], order[target]] = [order[target], order[index]]
    setAnswer({ ...answer, order })
  }

  function collectAnswer() {
    if (!task) return {}
    if (task.type === 'order') return { order: answer.order || [], reason: answer.reason || '' }
    if (task.type === 'select' || task.type === 'spot_issues') return { selected: answer.selected || [], reason: answer.reason || '' }
    if (task.type === 'categorize') return { mapping: answer.mapping || {} }
    if (task.type === 'handoff') return { fields: answer.fields || {} }
    if (task.type === 'revise') return { revised: answer.revised || '', changeReason: answer.changeReason || '' }
    if (task.type === 'transfer') return { choice: answer.choice || '', reason: answer.reason || '' }
    if (task.type === 'mini_project') return {
      keyFactIds: answer.keyFactIds || [],
      decision: answer.decision || '',
      handoff: answer.handoff || '',
    }
    return answer
  }

  async function submit() {
    if (!task || busy) return
    setBusy(true)
    setMessage([])
    try {
      const result = await foundationApi.complete(task.id, collectAnswer())
      if (!result.ok) {
        const issues = Array.isArray(result.issues) ? result.issues : [result.issues || '这一步还差一点']
        setMessage(issues)
        try {
          const support = await foundationApi.agentHint(task.id)
          const response = support?.decision?.response
          if (response) setMessage([...issues, response])
        } catch {
          // Domain result remains authoritative even if the Agent language layer is unavailable.
        }
        return
      }
      setMessage(['这一步已经由服务器记录。正在同步新的 SceneState。'])
      await onChanged()
    } catch (error) {
      setMessage([error instanceof Error ? error.message : '提交失败'])
    } finally {
      setBusy(false)
    }
  }

  async function getHint() {
    if (!task || busy || Number(task.hintBudget || 0) <= 0) return
    setBusy(true)
    try {
      const result = await foundationApi.agentHint(task.id)
      setHint(result?.decision?.response || '先只处理眼前最关键的一步。')
      await onChanged()
    } catch (error) {
      setHint(error instanceof Error ? error.message : '暂时无法取得提示')
    } finally {
      setBusy(false)
    }
  }

  if (!task) {
    return (
      <aside className="work-panel open">
        <div className="panel-head">
          <div><span className="eyebrow">Foundation · {mode}</span><h2>基础动作已完成</h2></div>
          <button className="icon-button" onClick={onClose}>×</button>
        </div>
        <div className="completion-card">
          <strong>{Math.round(progress)}%</strong>
          <p>服务器当前没有基础任务需要继续。表达练习和跨材料探索仍可从兼容工作台进入；新的 Real Work Sample 会在八个基础实践完成后开放。</p>
          <a className="secondary-button" href="/static/foundation.html">打开兼容工作台</a>
        </div>
      </aside>
    )
  }

  return (
    <aside className="work-panel open">
      <div className="panel-head">
        <div><span className="eyebrow">Foundation Workstation · {Math.round(progress)}%</span><h2>{task.title}</h2></div>
        <button className="icon-button" onClick={onClose}>×</button>
      </div>
      <p className="panel-intro">{task.intro}</p>
      {task.why && <p className="why-card">为什么练这个：{task.why}</p>}

      <div className="task-body">
        {task.type === 'order' && (
          <>
            <div className="material-stack">
              {(answer.order || []).map((id: string, index: number) => {
                const item = items.find((row) => row.id === id)
                return <div className="material-card row" key={id}>
                  <span className="rank">{index + 1}</span>
                  <div><strong>{itemText(item)}</strong><p>{item?.detail}</p></div>
                  <div className="row-actions"><button onClick={() => move(id, -1)}>↑</button><button onClick={() => move(id, 1)}>↓</button></div>
                </div>
              })}
            </div>
            <label className="field"><span>为什么这样排？</span><textarea value={answer.reason || ''} onChange={(e) => setAnswer({ ...answer, reason: e.target.value })} /></label>
          </>
        )}

        {task.type === 'select' && (
          <><p className="question">{data.question}</p><div className="material-stack">
            {items.map((item) => <label className="material-card selectable" key={item.id}><input type="checkbox" checked={(answer.selected || []).includes(item.id)} onChange={() => toggle(item.id)} /><span>{itemText(item)}</span></label>)}
          </div></>
        )}

        {task.type === 'categorize' && (
          <div className="material-stack">
            {(data.items || []).map((item: any) => <label className="material-card" key={item.id}><strong>{item.text}</strong><select value={(answer.mapping || {})[item.id] || ''} onChange={(e) => setAnswer({ ...answer, mapping: { ...(answer.mapping || {}), [item.id]: e.target.value } })}><option value="">放到哪一类？</option>{(data.categories || []).map((category: string) => <option key={category}>{category}</option>)}</select></label>)}
          </div>
        )}

        {task.type === 'spot_issues' && (
          <>
            <div className="mini-table">{(data.rows || []).map((row: any) => <div key={row.id}><span>{row.name}</span><span>{row.phone || '—'}</span><span>{row.date}</span></div>)}</div>
            <div className="material-stack">{(data.issues || []).map((item: any) => <label className="material-card selectable" key={item.id}><input type="checkbox" checked={(answer.selected || []).includes(item.id)} onChange={() => toggle(item.id)} /><span>{item.text}</span></label>)}</div>
            <label className="field"><span>为什么这些会影响后续？</span><textarea value={answer.reason || ''} onChange={(e) => setAnswer({ ...answer, reason: e.target.value })} /></label>
          </>
        )}

        {task.type === 'handoff' && (
          <><div className="brief-card">{data.situation}</div>{(data.fields || []).map((field: any) => <label className="field" key={field.id}><span>{field.label}</span><textarea placeholder={field.placeholder} value={(answer.fields || {})[field.id] || ''} onChange={(e) => setAnswer({ ...answer, fields: { ...(answer.fields || {}), [field.id]: e.target.value } })} /></label>)}</>
        )}

        {task.type === 'revise' && (
          <><div className="comparison-card"><small>第一版</small><p>{data.original}</p><small>收到的反馈</small><p>{data.feedback}</p></div><label className="field"><span>改出 V2</span><textarea value={answer.revised || ''} onChange={(e) => setAnswer({ ...answer, revised: e.target.value })} /></label><label className="field"><span>这次真正改了什么？</span><textarea value={answer.changeReason || ''} onChange={(e) => setAnswer({ ...answer, changeReason: e.target.value })} /></label></>
        )}

        {task.type === 'transfer' && (
          <><p className="question">{data.question}</p><div className="material-stack">{items.map((item) => <label className="material-card selectable" key={item.id}><input type="radio" name="transfer" checked={answer.choice === item.id} onChange={() => setAnswer({ ...answer, choice: item.id })} /><span><strong>{item.title}</strong><small>{item.detail}</small></span></label>)}</div><label className="field"><span>你的判断依据</span><textarea value={answer.reason || ''} onChange={(e) => setAnswer({ ...answer, reason: e.target.value })} /></label></>
        )}

        {task.type === 'mini_project' && (
          <><div className="brief-card">{data.brief}</div><div className="material-stack">{(data.facts || []).map((item: any) => <label className="material-card selectable" key={item.id}><input type="checkbox" checked={(answer.keyFactIds || []).includes(item.id)} onChange={() => toggle(item.id, 'keyFactIds')} /><span>{item.text}</span></label>)}</div><label className="field"><span>你准备先处理什么？</span><textarea value={answer.decision || ''} onChange={(e) => setAnswer({ ...answer, decision: e.target.value })} /></label><label className="field"><span>交接给下一位</span><textarea value={answer.handoff || ''} onChange={(e) => setAnswer({ ...answer, handoff: e.target.value })} /></label></>
        )}
      </div>

      {hint && <div className="agent-support"><span>Agent</span><p>{hint}</p></div>}
      {message.length > 0 && <div className="message-stack">{message.map((item, index) => <p key={index}>{item}</p>)}</div>}
      <div className="panel-actions">
        {Number(task.hintBudget || 0) > 0 && <button className="ghost-button" disabled={busy} onClick={getHint}>给一点提示</button>}
        <button className="primary-button" disabled={busy} onClick={submit}>{busy ? '处理中…' : '提交这一步'}</button>
      </div>
      <a className="legacy-link" href="/static/foundation.html">出现兼容问题时打开旧工作台</a>
    </aside>
  )
}
