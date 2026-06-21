import s, { FG4, GRN, RED } from '../../../lib/chatStyles.js'
import { MODEL_KEYS, MODEL_LABELS } from '../../../lib/chatConstants.js'
import { usePanelProps } from '../PanelPropsContext.js'

const NOTIF_LABELS = {
  email_digest: 'Email Digest',
  email_scheduled: 'Email Scheduled',
  email_insights: 'Email Insights',
  push_enabled: 'Push',
}

export default function SettingsModal() {
  const p = usePanelProps()
  const { settingsOpen, setSettingsOpen, editSysPrompt, setEditSysPrompt, editLockModel, setEditLockModel, saveSettings, settingsSaving } = p.settings
  const { prefs, prefsLoading, vapidPublicKey, pushSupported, togglePref } = p.notificationPrefs || {}
  if (!settingsOpen) return null
  return (
    <div style={s.settingsModal} onClick={e => e.stopPropagation()}>
      <div style={s.settingsHeader}>
        <span style={s.settingsTitle}>Settings</span>
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
        {editLockModel && <div style={{ fontSize:'14px', color:FG4, marginTop:'0.4rem' }}>All messages in this conversation will use {MODEL_LABELS[MODEL_KEYS[editLockModel]] || editLockModel}.</div>}

        <div style={s.notifSection}>
          <div style={s.notifLabel}>Notifications</div>
          {prefsLoading ? (
            <div style={{ fontFamily:'inherit', fontSize:'15px', color:FG4 }}>Loading preferences...</div>
          ) : prefs ? (
            Object.keys(NOTIF_LABELS).map(key => {
              const isPush = key === 'push_enabled'
              const disabled = isPush && (!vapidPublicKey || !pushSupported)
              const val = prefs[key]
              return (
                <div key={key} style={s.notifRow}>
                  <span style={s.notifText}>{NOTIF_LABELS[key]}</span>
                  <button
                    onClick={() => togglePref(key)}
                    disabled={disabled}
                    style={{
                      padding:'0.2rem 0.55rem', border:'1px solid',
                      borderColor: val ? RED : (disabled ? '#2a2a2a' : '#4a4a4a'),
                      background: val ? 'rgba(255,34,34,0.10)' : 'none',
                      color: val ? RED : (disabled ? '#2a2a2a' : '#8f8f8f'),
                      cursor: disabled ? 'default' : 'pointer',
                      fontFamily:"'Silkscreen',monospace", fontSize:'9px',
                      letterSpacing:'0.08em', textTransform:'uppercase',
                    }}>
                    {val ? 'ON' : 'OFF'}
                  </button>
                </div>
              )
            })
          ) : (
            <div style={{ fontFamily:'inherit', fontSize:'15px', color:RED }}>Failed to load preferences</div>
          )}
        </div>
      </div>
      <div style={s.settingsFooter}>
        <button onClick={() => setSettingsOpen(false)} style={s.cancelBtn}>Cancel</button>
        <button onClick={saveSettings} disabled={settingsSaving} style={s.saveBtn}>
          {settingsSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  )
}
