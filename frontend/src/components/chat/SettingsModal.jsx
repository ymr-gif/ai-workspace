import s from '../../lib/chatStyles.js'
import { MODEL_KEYS, MODEL_LABELS } from '../../lib/chatConstants.js'

export default function SettingsModal({
  settingsOpen, setSettingsOpen,
  editSysPrompt, setEditSysPrompt,
  editLockModel, setEditLockModel,
  editWsId, setEditWsId,
  sidebarWsList,
  saveSettings, settingsSaving,
}) {
  if (!settingsOpen) return null
  return (
    <div style={s.settingsModal} onClick={e => e.stopPropagation()}>
      <div style={s.settingsHeader}>
        <span style={s.settingsTitle}>⚙ Conversation Settings</span>
        <button onClick={() => setSettingsOpen(false)} style={s.closeBtn}>✕</button>
      </div>
      <div style={s.settingsBody}>
        <div style={{ ...s.editLabel, marginTop:0 }}>System Prompt</div>
        <textarea value={editSysPrompt} onChange={e => setEditSysPrompt(e.target.value)}
          rows={5} style={s.editArea} placeholder="You are a helpful assistant specializing in…" />
        <div style={{ ...s.editLabel, marginTop:'1rem' }}>Model Lock</div>
        <div style={{ ...s.modelPills, marginTop:'0.4rem', flexWrap:'wrap' }}>
          {[['', 'Auto (route)'], ['llama', 'LLaMA 8B'], ['coder', 'DeepSeek'], ['reasoning', '70B Reasoning']].map(([key, label]) => (
            <button key={key} onClick={() => setEditLockModel(key)}
              style={{ ...s.pill, ...(editLockModel === key ? s.pillActive : {}) }}>
              {label}
            </button>
          ))}
        </div>
        {editLockModel && <div style={{ fontSize:'0.7rem', color:'#475569', marginTop:'0.4rem' }}>All messages in this conversation will use {MODEL_LABELS[MODEL_KEYS[editLockModel]] || editLockModel}.</div>}
        {sidebarWsList.length > 0 && (
          <>
            <div style={{ ...s.editLabel, marginTop:'1rem' }}>Workspace</div>
            <select value={editWsId} onChange={e => setEditWsId(e.target.value)}
              style={{ ...s.editArea, height:'2.2rem', resize:'none', padding:'0.3rem 0.6rem', cursor:'pointer' }}>
              <option value="">— None —</option>
              {sidebarWsList.map(ws => (
                <option key={ws.id} value={ws.id}>{ws.name}</option>
              ))}
            </select>
          </>
        )}
      </div>
      <div style={s.settingsFooter}>
        <button onClick={() => setSettingsOpen(false)} style={s.cancelBtn}>Cancel</button>
        <button onClick={saveSettings} disabled={settingsSaving} style={s.saveBtn}>
          {settingsSaving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
