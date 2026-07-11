import { useEffect } from 'react'
import s from '../../../lib/chatStyles.js'
import { MODEL_KEYS, MODEL_LABELS } from '../../../lib/chatConstants.js'
import { usePanelProps } from '../PanelPropsContext.js'

// Header telemetry: frontend-known data only. Breaker state has no frontend
// source today — slot reserved (needs a backend status endpoint).
export default function TelemetryStrip({ lastTtft, linkFault, dockTab, setDockTab, onOpenPalette, onLogout, userRole, narrow, onToggleRail }) {
  const p = usePanelProps()
  const { usageData, loadUsage } = p.usage
  const { settings, conv, modelParams } = p

  // refresh session spend when a reply finishes
  useEffect(() => { if (!conv.loading) loadUsage() }, [conv.loading])

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
