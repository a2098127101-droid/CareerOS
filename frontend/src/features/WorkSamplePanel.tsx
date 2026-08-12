import { useEffect, useMemo, useState } from 'react'
import { workSampleApi } from '../api/client'
import type { WorkSampleState, WorkSampleSubmission } from '../api/types'

type Props = {
  workSample: WorkSampleState
  onClose: () => void
  onChanged: () => Promise<void>
}

const EMPTY: WorkSampleSubmission = { priority_ticket_ids: [], handoff: '', work_notes: '' }

export function WorkSamplePanel({ workSample, onClose, onChanged }: Props) {
  const [value, setValue] = useState<WorkSampleSubmission>(EMPTY)
  const [busy, setBusy] = useState(false)
  const [issues, setIssues] = useState<string[]>([])
  const status = workSample.status
  const transferMode = status === 'transfer_ready'

  useEffect(() => {
    if (status === 'revision_required') {
      setValue({
        priority_ticket_ids: [...(workSample.v1?.priorityTicketIds || [])],
        handoff: workSample.v1?.handoff || '',
        work_notes: workSample.v1?.workNotes || '',
      })
    } else if (status === 'transfer_ready') {
      setValue(EMPTY)
    } else if (status === 'working_v1' || status === 'ready') {
      setValue(EMPTY)
    }
    setIssues([])
  }, [status, workSample.v1])

  const tickets = useMemo(() => transferMode ? workSample.definition.transfer.materials : workSample.definition.materials.tickets, [transferMode, workSample])

  function toggle(id: string) {
    const selected = new Set(value.priority_ticket_ids)
    selected.has(id) ? selected.delete(id) : selected.add(id)
    setValue({ ...value, priority_ticket_ids: [...selected] })
  }

  async function start() {
    setBusy(true)
    setIssues([])
    try {
      await workSampleApi.start()
      await onChanged()
    } catch (error) {
      setIssues([error instanceof Error ? error.message : '无法开始工作样本'])
    } finally {
      setBusy(false)
    }
  }

  async function submit() {
    setBusy(true)
    setIssues([])
    try {
      const result = status === 'revision_required'
        ? await workSampleApi.submitV2(value)
        : transferMode
          ? await workSampleApi.submitTransfer(value)
          : await workSampleApi.submitV1(value)
      if (!result.ok) {
        setIssues(result.issues || ['当前交接还不能进入下一阶段'])
        return
      }
      await onChanged()
    } catch (error) {
      setIssues([error instanceof Error ? error.message : '提交失败'])
    } finally {
      setBusy(false)
    }
  }

  if (!workSample.unlocked) {
    return (
      <aside className="work-panel wide open">
        <div className="panel-head"><div><span className="eyebrow">Real Work Sample</span><h2>真实工作样本还未开放</h2></div><button className="icon-button" onClick={onClose}>×</button></div>
        <div className="completion-card"><p>{workSample.unlockReason}</p><p>这里不是课程门槛。先把前面的几个基础动作做过一遍，进入真实材料时才不会被复杂界面本身卡住。</p></div>
      </aside>
    )
  }

  if (status === 'ready') {
    return (
      <aside className="work-panel wide open">
        <div className="panel-head"><div><span className="eyebrow">Real Work Sample · 01</span><h2>{workSample.definition.title}</h2></div><button className="icon-button" onClick={onClose}>×</button></div>
        <p className="panel-intro">{workSample.definition.roleContext}</p>
        <div className="deliverable-card"><small>这次真正要交的东西</small><strong>{workSample.definition.deliverable}</strong></div>
        <div className="constraint-list">{workSample.definition.constraints.map((item) => <span key={item}>{item}</span>)}</div>
        {issues.length > 0 && <div className="message-stack">{issues.map((item) => <p key={item}>{item}</p>)}</div>}
        <div className="panel-actions"><button className="primary-button" disabled={busy} onClick={start}>{busy ? '正在打开材料…' : '进入工作台'}</button></div>
      </aside>
    )
  }

  if (status === 'completed') {
    return (
      <aside className="work-panel wide open">
        <div className="panel-head"><div><span className="eyebrow">Real Work Sample · complete</span><h2>这轮工作样本已经完成</h2></div><button className="icon-button" onClick={onClose}>×</button></div>
        <div className="completion-card"><strong>V1 → Feedback → V2 → Transfer</strong><p>系统已经保存第一版、主管反馈、修订版和换材料结果。这里仍不会自动宣布“能力已掌握”；SceneState 的能力节点只读取 Capability Verification 2.0。</p></div>
        <div className="evidence-chip-row">{workSample.evidenceIds.map((id) => <span key={id}>{id}</span>)}</div>
      </aside>
    )
  }

  return (
    <aside className="work-panel wide open">
      <div className="panel-head">
        <div><span className="eyebrow">{transferMode ? 'Transfer · no hints' : status === 'revision_required' ? 'Supervisor Feedback → V2' : 'Real Work Sample · V1'}</span><h2>{transferMode ? workSample.definition.transfer.title : workSample.definition.title}</h2></div>
        <button className="icon-button" onClick={onClose}>×</button>
      </div>
      <p className="panel-intro">{transferMode ? workSample.definition.transfer.roleContext : workSample.definition.roleContext}</p>

      {!transferMode && (
        <section className="work-materials">
          <div className="material-column"><h3>现场消息</h3>{workSample.definition.materials.messages.map((message) => <article className="message-card" key={message.id}><div><span>{message.time}</span><strong>{message.from}</strong></div><p>{message.text}</p></article>)}</div>
          <div className="material-column"><h3>补充信号</h3>{workSample.definition.materials.customerSignals.map((signal) => <article className="signal-card" key={signal.id}><small>{signal.type}</small><p>{signal.text}</p></article>)}</div>
        </section>
      )}

      <section className="ticket-board">
        <div className="section-title"><div><h3>待处理事项</h3><p>像值班交接一样选出你准备放到最前面的事项，不需要把每一张卡都“答题”。</p></div><span>{value.priority_ticket_ids.length} selected</span></div>
        <div className="ticket-grid">{tickets.map((ticket) => <button type="button" className={`ticket-card ${value.priority_ticket_ids.includes(ticket.id) ? 'selected' : ''}`} key={ticket.id} onClick={() => toggle(ticket.id)}><div><span>{ticket.id}</span><small>{ticket.deadline}</small></div><strong>{ticket.subject}</strong><p>{ticket.impact}</p><small>{ticket.status || ticket.detail}</small></button>)}</div>
      </section>

      {status === 'revision_required' && workSample.supervisorFeedback.length > 0 && (
        <section className="supervisor-feedback"><span>主管看完 V1 后留下的反馈</span>{workSample.supervisorFeedback.map((item, index) => <p key={index}>{item}</p>)}</section>
      )}

      <section className="handoff-editor">
        <label className="field"><span>{status === 'revision_required' ? '修改后的 V2 交接' : transferMode ? '新材料交接' : '10:30 交给主管的 V1'}</span><textarea rows={8} placeholder="把当前风险、处理顺序、依据和下一步写成下一位可以直接接手的交接。" value={value.handoff} onChange={(event) => setValue({ ...value, handoff: event.target.value })} /></label>
        <label className="field"><span>工作过程记录</span><textarea rows={4} placeholder="你主要用什么标准判断优先级？哪些信息还没有确认？" value={value.work_notes} onChange={(event) => setValue({ ...value, work_notes: event.target.value })} /></label>
      </section>

      {issues.length > 0 && <div className="message-stack">{issues.map((item, index) => <p key={index}>{item}</p>)}</div>}
      <div className="panel-actions"><button className="primary-button" disabled={busy} onClick={submit}>{busy ? '正在记录…' : status === 'revision_required' ? '提交 V2' : transferMode ? '完成换材料交接' : '提交 V1 给主管'}</button></div>
    </aside>
  )
}
