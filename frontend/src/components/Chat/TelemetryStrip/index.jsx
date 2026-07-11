import { useEffect, useState } from 'react'
import s from '../../../lib/chatStyles.js'
import { MODEL_KEYS, MODEL_LABELS } from '../../../lib/chatConstants.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function TelemetryStrip({ lastTtft, linkFault, dockTab, setDockTab, onOpenPalette, onLogout, userRole, narrow, onToggleRail }) {
  const p = usePanelProps()
  const { usageData, loadUsage } = p.usage
  const { settings, conv, modelParams } = p
  const [breakers, setBreakers] = useState(null)

  // refresh session spend when a reply finishes
  useEffect(() => { if (!conv.loading) loadUsage() }, [conv.loading])

  // circuit-breaker state: poll every 60s + refresh after each reply
  useEffect(() => {
    let dead = false
    async function poll() {
      try {
        const r = await fetch('/api/breakers', { headers: { Authorization: `Bearer ${p.token}` } })
        if (r.ok && !dead) setBreakers(await r.json())
      } catch { /* strip slot just stays hidden */ }
    }
    poll()
    const tid = setInterval(poll, 60000)
    return () => { dead = true; clearInterval(tid) }
  }, [conv.loading])

  const openModels = breakers ? Object.entries(breakers.models || {}).filter(([, o]) => o).map(([m]) => m) : []

  const lockedModel = conv.convLockModel
  const busModel = lockedModel
    ? (MODEL_LABELS[lockedModel] || lockedModel)
    : modelParams.selectedModel === 'auto'
      ? 'AUTO'
      : (MODEL_LABELS[MODEL_KEYS[modelParams.selectedModel]] || modelParams.selectedModel)

  return (
    <div style={s.teleStrip}>
      {narrow && <button onClick={onToggleRail} style={s.teleBtn} title="Conversations">☰</button>}
      <span style={s.teleBrand}>NIM · FLIGHT OPS</span>
      <span style={s.teleItem}>
        <span style={{ ...s.teleDot, ...(linkFault ? s.teleDotBad : {}) }} />
        LINK <span style={linkFault ? s.teleBad : s.teleOk}>{linkFault ? 'FAULT' : 'NOMINAL'}</span>
      </span>
      <span style={s.teleItem}>BUS <span style={s.teleVal}>{busModel}{lockedModel ? ' 🔒' : ''}</span></span>
      {breakers && (
        <span style={s.teleItem}>BRKR{' '}
          {openModels.length === 0
            ? <span style={s.teleOk}>CLOSED</span>
            : <span style={s.teleBad}>OPEN · {openModels.join(',').toUpperCase()}</span>}
        </span>
      )}
      <span style={s.teleItem}>SESSION <span style={s.teleVal}>${(usageData?.cost_usd || 0).toFixed(4)}</span></span>
      {lastTtft != null && (
        <span style={s.teleItem}>TTFT <span style={s.teleVal}>{(lastTtft / 1000).toFixed(1)}s</span></span>
      )}
      <div style={s.teleRight}>
        <button onClick={onOpenPalette} style={s.teleBtn} title="Search & actions (Ctrl+K)">⌘K</button>
        {['mind', 'files', 'ops', ...(userRole === 'admin' ? ['admin'] : [])].map(t => (
          <button key={t} onClick={() => setDockTab(dockTab === t ? null : t)}
            style={{ ...s.teleBtn, ...(dockTab === t ? s.teleBtnOn : {}) }}>
            {t}{t === 'mind' && p.insights.unreadCount > 0 && <span style={s.unreadBadge}>{p.insights.unreadCount}</span>}
            {t === 'files' && p.files.attachedFiles.length > 0 && <span style={s.unreadBadge}>{p.files.attachedFiles.length}</span>}
          </button>
        ))}
        {conv.activeConvId && (
          <button onClick={() => settings.setSettingsOpen(true)} style={s.teleBtn} title="Conversation settings">⚙</button>
        )}
        <button onClick={onLogout} style={s.teleBtn}>Logout</button>
      </div>
    </div>
  )
}
