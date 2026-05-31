import s, { RED, FG5 } from '../../../lib/chatStyles.js'

export default function WorkspaceModal({
  wsModalOpen, setWsModalOpen,
  wsModalTarget,
  wsFieldName, setWsFieldName,
  wsFieldDesc, setWsFieldDesc,
  wsFieldSys, setWsFieldSys,
  saveWsModal, deleteWs, wsSaving,
}) {
  if (!wsModalOpen) return null
  return (
    <div style={s.wsModal} onClick={e => e.stopPropagation()}>
      <div style={s.settingsHeader}>
        <span style={s.settingsTitle}>{wsModalTarget ? `⚙ ${wsModalTarget.name}` : '+ New Workspace'}</span>
        <button onClick={() => setWsModalOpen(false)} style={s.closeBtn}>✕</button>
      </div>
      <div style={s.settingsBody}>
        <div style={{ ...s.editLabel, marginTop:0 }}>Name</div>
        <input value={wsFieldName} onChange={e => setWsFieldName(e.target.value)}
          style={{ ...s.editArea, height:'2.2rem', resize:'none', padding:'0.4rem 0.6rem' }}
          placeholder="My Workspace" onKeyDown={e => e.key === 'Enter' && saveWsModal()} />
        <div style={s.editLabel}>Description</div>
        <input value={wsFieldDesc} onChange={e => setWsFieldDesc(e.target.value)}
          style={{ ...s.editArea, height:'2.2rem', resize:'none', padding:'0.4rem 0.6rem' }}
          placeholder="Optional description" />
        <div style={s.editLabel}>System Prompt (AI persona for all conversations)</div>
        <textarea value={wsFieldSys} onChange={e => setWsFieldSys(e.target.value)}
          rows={4} style={s.editArea} placeholder="You are an expert in…" />
      </div>
      <div style={{ ...s.settingsFooter, justifyContent: wsModalTarget ? 'space-between' : 'flex-end' }}>
{wsModalTarget && (
            <button onClick={deleteWs} style={{ ...s.cancelBtn, color:RED, borderColor:FG5 }}>Delete</button>
          )}
        <div style={{ display:'flex', gap:'0.5rem' }}>
          <button onClick={() => setWsModalOpen(false)} style={s.cancelBtn}>Cancel</button>
          <button onClick={saveWsModal} disabled={wsSaving || !wsFieldName.trim()} style={s.saveBtn}>
            {wsSaving ? 'Saving…' : wsModalTarget ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}
