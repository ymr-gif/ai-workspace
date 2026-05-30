import s from '../../lib/chatStyles.js'

const STATUS_FILTERS = ['all', 'active', 'paused', 'completed']

const STATUS_STYLE = {
  active:    { color: '#34d399', bg: 'rgba(52,211,153,0.12)',  border: 'rgba(52,211,153,0.25)'  },
  paused:    { color: '#fbbf24', bg: 'rgba(251,191,36,0.12)',  border: 'rgba(251,191,36,0.25)'  },
  completed: { color: '#818cf8', bg: 'rgba(129,140,248,0.12)', border: 'rgba(129,140,248,0.25)' },
}

function StatusBadge({ status }) {
  const st = STATUS_STYLE[status] || STATUS_STYLE.active
  return (
    <span style={{ fontSize: '0.62rem', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', background: st.bg, color: st.color, border: `1px solid ${st.border}`, textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>
      {status}
    </span>
  )
}

export default function GoalsPanel({
  goalsOpen, setGoalsOpen,
  goals, goalsLoading,
  statusFilter, changeFilter,
  formOpen, setFormOpen,
  editTarget,
  formTitle, setFormTitle,
  formDesc, setFormDesc,
  formStatus, setFormStatus,
  formSaving,
  loadGoals,
  saveGoal,
  deleteGoal,
  toggleStatus,
  linkConversation,
  openCreate,
  openEdit,
  activeConvId,
}) {
  const inputStyle = { ...s.sideSearchInput, width: '100%', padding: '0.4rem 0.6rem', fontSize: '0.82rem', boxSizing: 'border-box' }

  return (
    <div style={{ ...s.toolLogPanel, transform: goalsOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.toolLogHdr}>
        <span style={s.toolLogTitle}>🎯 Goals</span>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <button onClick={openCreate} style={{ ...s.actionBtn, color: '#34d399', borderColor: 'rgba(52,211,153,0.35)', padding: '0.2rem 0.6rem' }}>+ New</button>
          <button onClick={() => loadGoals(statusFilter)} style={s.refreshBtn} disabled={goalsLoading}>{goalsLoading ? '…' : '↻'}</button>
          <button onClick={() => setGoalsOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', padding: '0.5rem 1.25rem', borderBottom: '1px solid #1e293b', flexShrink: 0 }}>
        {STATUS_FILTERS.map(f => (
          <button key={f} onClick={() => changeFilter(f)}
            style={{ ...s.wsPill, ...(statusFilter === f ? s.wsPillActive : {}), textTransform: 'capitalize' }}>
            {f}
          </button>
        ))}
      </div>

      {formOpen && (
        <div style={{ position: 'absolute', inset: 0, background: '#0f172a', zIndex: 2, display: 'flex', flexDirection: 'column' }}>
          <div style={s.toolLogHdr}>
            <span style={s.toolLogTitle}>{editTarget ? 'Edit Goal' : 'New Goal'}</span>
            <button onClick={() => setFormOpen(false)} style={s.closeBtn}>✕</button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <div>
              <div style={s.editLabel}>Title</div>
              <input value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="e.g. Ship ROADMAP #13" style={inputStyle} />
            </div>
            <div>
              <div style={s.editLabel}>Description (optional)</div>
              <textarea value={formDesc} onChange={e => setFormDesc(e.target.value)} rows={3}
                placeholder="Details, acceptance criteria…" style={{ ...s.editArea, minHeight: '70px' }} />
            </div>
            <div>
              <div style={s.editLabel}>Status</div>
              <select value={formStatus} onChange={e => setFormStatus(e.target.value)}
                style={{ ...inputStyle, appearance: 'auto', cursor: 'pointer' }}>
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>
          <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid #1e293b', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', flexShrink: 0 }}>
            <button onClick={() => setFormOpen(false)} style={s.cancelBtn}>Cancel</button>
            <button onClick={saveGoal} disabled={formSaving || !formTitle.trim()} style={s.saveBtn}>
              {formSaving ? 'Saving…' : editTarget ? 'Update' : 'Create'}
            </button>
          </div>
        </div>
      )}

      <div style={s.toolLogBody}>
        {goalsLoading && goals.length === 0 && <p style={s.emptyMem}>Loading…</p>}
        {!goalsLoading && goals.length === 0 && (
          <p style={s.emptyMem}>No goals{statusFilter !== 'all' ? ` with status "${statusFilter}"` : ''}.<br /><span style={{ fontSize: '0.75rem' }}>Use + New to add one.</span></p>
        )}
        {goals.map(goal => {
          const linkedCount = goal.linked_conversation_ids?.length || 0
          const alreadyLinked = activeConvId && (goal.linked_conversation_ids || []).includes(activeConvId)
          return (
            <div key={goal.id} style={{ ...s.toolLogRow, marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                <span style={{ flex: 1, fontSize: '0.82rem', color: '#e2e8f0', fontWeight: 600, lineHeight: 1.4 }}>{goal.title}</span>
                <StatusBadge status={goal.status} />
              </div>
              {goal.description && (
                <div style={{ fontSize: '0.72rem', color: '#64748b', marginTop: '3px', lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {goal.description}
                </div>
              )}
              {linkedCount > 0 && (
                <div style={{ fontSize: '0.65rem', color: '#475569', marginTop: '3px' }}>
                  🔗 {linkedCount} conversation{linkedCount !== 1 ? 's' : ''}
                </div>
              )}
              <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
                {goal.status !== 'completed' && (
                  <button onClick={() => toggleStatus(goal)}
                    style={{ ...s.attachBtn, ...(goal.status === 'active' ? s.attachedBtn : {}), fontSize: '0.68rem' }}>
                    {goal.status === 'active' ? '● Active' : '○ Paused'}
                  </button>
                )}
                {activeConvId && goal.status === 'active' && (
                  <button onClick={() => !alreadyLinked && linkConversation(goal.id, activeConvId)}
                    disabled={alreadyLinked}
                    style={{ ...s.attachBtn, fontSize: '0.68rem', color: alreadyLinked ? '#475569' : '#38bdf8', borderColor: alreadyLinked ? '#334155' : 'rgba(56,189,248,0.3)', cursor: alreadyLinked ? 'default' : 'pointer' }}>
                    {alreadyLinked ? '✓ Linked' : '🔗 Link conv'}
                  </button>
                )}
                <div style={{ flex: 1 }} />
                <button onClick={() => openEdit(goal)} style={{ ...s.actionBtn, fontSize: '0.68rem' }}>Edit</button>
                <button onClick={() => deleteGoal(goal.id)} style={{ ...s.delBtn, fontSize: '0.68rem' }}>🗑</button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
