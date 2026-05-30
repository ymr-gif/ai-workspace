import { useState } from 'react'
import s from '../../lib/chatStyles.js'

const PRESETS = ['daily', 'weekly', 'monthly']

function runStatus(run) {
  if (run.status === 'success') return { color: '#34d399', label: '✓' }
  if (run.status === 'error')   return { color: '#f87171', label: '✗' }
  return { color: '#94a3b8', label: '…' }
}

export default function AutomationsPanel({
  autoOpen, setAutoOpen,
  schedules, schedulesLoading,
  formOpen, setFormOpen,
  editTarget,
  formName, setFormName,
  formPrompt, setFormPrompt,
  formSchedule, setFormSchedule,
  formModel, setFormModel,
  formWsId, setFormWsId,
  formSaving,
  runsMap, runsLoading,
  expandedId, triggeringId,
  loadSchedules, saveSchedule, deleteSchedule, toggleActive, triggerRun, openCreate, openEdit, toggleExpanded,
  sidebarWsList,
}) {
  const [customCron, setCustomCron] = useState('')
  const selectedPreset = PRESETS.includes(formSchedule) ? formSchedule : 'custom'

  function handlePreset(val) {
    if (val === 'custom') {
      setFormSchedule(customCron || '0 9 * * 1')
    } else {
      setFormSchedule(val)
    }
  }

  const inputStyle = { ...s.sideSearchInput, width: '100%', padding: '0.4rem 0.6rem', fontSize: '0.82rem', boxSizing: 'border-box' }

  return (
    <div style={{ ...s.toolLogPanel, transform: autoOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.toolLogHdr}>
        <span style={s.toolLogTitle}>⏱ Automations</span>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <button onClick={openCreate} style={{ ...s.actionBtn, color: '#818cf8', borderColor: 'rgba(99,102,241,0.4)', padding: '0.2rem 0.6rem' }}>+ New</button>
          <button onClick={loadSchedules} style={s.refreshBtn} disabled={schedulesLoading}>{schedulesLoading ? '…' : '↻'}</button>
          <button onClick={() => setAutoOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>

      {formOpen && (
        <div style={{ position: 'absolute', inset: 0, background: '#0f172a', zIndex: 2, display: 'flex', flexDirection: 'column' }}>
          <div style={s.toolLogHdr}>
            <span style={s.toolLogTitle}>{editTarget ? 'Edit Schedule' : 'New Schedule'}</span>
            <button onClick={() => setFormOpen(false)} style={s.closeBtn}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <div style={s.editLabel}>Name</div>
              <input value={formName} onChange={e => setFormName(e.target.value)} placeholder="e.g. Daily standup" style={inputStyle} />
            </div>
            <div>
              <div style={s.editLabel}>Prompt</div>
              <textarea value={formPrompt} onChange={e => setFormPrompt(e.target.value)} rows={4}
                placeholder="The prompt to run on schedule…" style={{ ...s.editArea, minHeight: '90px' }} />
            </div>
            <div>
              <div style={s.editLabel}>Schedule</div>
              <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
                {[...PRESETS, 'custom'].map(p => (
                  <button key={p} onClick={() => handlePreset(p)}
                    style={{ ...s.wsPill, ...(selectedPreset === p ? s.wsPillActive : {}), textTransform: 'capitalize' }}>
                    {p}
                  </button>
                ))}
              </div>
              {selectedPreset === 'custom' && (
                <input value={formSchedule}
                  onChange={e => { setFormSchedule(e.target.value); setCustomCron(e.target.value) }}
                  placeholder="Cron: 0 9 * * 1"
                  style={{ ...inputStyle, fontFamily: 'monospace' }} />
              )}
            </div>
            <div>
              <div style={s.editLabel}>Model override (optional)</div>
              <input value={formModel} onChange={e => setFormModel(e.target.value)} placeholder="e.g. llama" style={inputStyle} />
            </div>
            {sidebarWsList?.length > 0 && (
              <div>
                <div style={s.editLabel}>Workspace (optional)</div>
                <select value={formWsId} onChange={e => setFormWsId(e.target.value)}
                  style={{ ...inputStyle, appearance: 'auto', cursor: 'pointer' }}>
                  <option value="">— None —</option>
                  {sidebarWsList.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              </div>
            )}
          </div>
          <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid #1e293b', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', flexShrink: 0 }}>
            <button onClick={() => setFormOpen(false)} style={s.cancelBtn}>Cancel</button>
            <button onClick={saveSchedule} disabled={formSaving || !formName.trim() || !formPrompt.trim()} style={s.saveBtn}>
              {formSaving ? 'Saving…' : editTarget ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}

      <div style={s.toolLogBody}>
        {schedulesLoading && schedules.length === 0 && <p style={s.emptyMem}>Loading…</p>}
        {!schedulesLoading && schedules.length === 0 && (
          <p style={s.emptyMem}>No schedules yet.<br /><span style={{ fontSize: '0.75rem' }}>Use + New to automate a prompt.</span></p>
        )}
        {schedules.map(sc => (
          <div key={sc.id} style={{ ...s.toolLogRow, marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ flex: 1, fontSize: '0.82rem', color: '#e2e8f0', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{sc.name}</span>
              <span style={{ fontSize: '0.65rem', fontFamily: 'monospace', color: '#818cf8', background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: '4px', padding: '1px 5px', flexShrink: 0 }}>{sc.schedule}</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: '#64748b', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {sc.prompt?.slice(0, 80)}{sc.prompt?.length > 80 ? '…' : ''}
            </div>
            <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <button onClick={() => toggleActive(sc)} style={{ ...s.attachBtn, ...(sc.is_active ? s.attachedBtn : {}), fontSize: '0.68rem' }}>
                {sc.is_active ? '● Active' : '○ Paused'}
              </button>
              <button onClick={() => triggerRun(sc.id)} disabled={triggeringId === sc.id}
                style={{ ...s.attachBtn, fontSize: '0.68rem', color: '#34d399', borderColor: 'rgba(52,211,153,0.3)' }}>
                {triggeringId === sc.id ? '…' : '▶ Run'}
              </button>
              <button onClick={() => toggleExpanded(sc.id)} style={{ ...s.attachBtn, fontSize: '0.68rem' }}>
                {expandedId === sc.id ? '▲ Runs' : '▼ Runs'}
              </button>
              <div style={{ flex: 1 }} />
              <button onClick={() => openEdit(sc)} style={{ ...s.actionBtn, fontSize: '0.68rem' }}>Edit</button>
              <button onClick={() => deleteSchedule(sc.id)} style={{ ...s.delBtn, fontSize: '0.68rem' }}>🗑</button>
            </div>
            {expandedId === sc.id && (
              <div style={{ marginTop: '0.5rem', borderTop: '1px solid #1e293b', paddingTop: '0.4rem' }}>
                {runsLoading[sc.id] && <div style={{ fontSize: '0.7rem', color: '#475569', textAlign: 'center' }}>Loading…</div>}
                {!runsLoading[sc.id] && (!runsMap[sc.id] || runsMap[sc.id].length === 0) && (
                  <div style={{ fontSize: '0.7rem', color: '#475569', textAlign: 'center' }}>No runs yet</div>
                )}
                {runsMap[sc.id]?.map(run => {
                  const st = runStatus(run)
                  return (
                    <div key={run.id} style={{ display: 'flex', gap: '0.4rem', alignItems: 'flex-start', fontSize: '0.7rem', padding: '3px 0', borderBottom: '1px solid #0f172a' }}>
                      <span style={{ color: st.color, fontWeight: 700, flexShrink: 0 }}>{st.label}</span>
                      <span style={{ color: '#475569', flexShrink: 0, whiteSpace: 'nowrap' }}>
                        {run.started_at ? new Date(run.started_at).toLocaleString() : '—'}
                      </span>
                      {run.error && <span style={{ color: '#f87171', flex: 1, wordBreak: 'break-word' }}>{run.error}</span>}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
