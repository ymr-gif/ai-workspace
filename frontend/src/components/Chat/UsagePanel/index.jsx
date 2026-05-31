import { useState } from 'react'
import s, { LINE, FG5, FG3 } from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function UsagePanel() {
  const p = usePanelProps()
  const { usageOpen, setUsageOpen, usageData, usageLoading, loadUsage } = p.usage
  const { token } = p
  const [exporting, setExporting] = useState(false)

  async function exportAll() {
    setExporting(true)
    try {
      const r = await fetch('/api/export/full', { headers: { Authorization: `Bearer ${token}` } })
      if (!r.ok) return
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'export.zip'; a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ } finally { setExporting(false) }
  }

  return (
    <div style={{ ...s.usagePanel, transform: usageOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.usageHdr}>
        <span style={s.usageTitle}>$ Token Usage</span>
        <div style={{ display:'flex', gap:'0.4rem', alignItems:'center' }}>
          <button onClick={loadUsage} style={s.refreshBtn} disabled={usageLoading}>{usageLoading ? '…' : '↻'}</button>
          <button onClick={() => setUsageOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>
      <div style={s.usageBody}>
        {!usageData && !usageLoading && <div style={s.emptyMem}>No data</div>}
        {usageData && (
          <>
            {[
              ['Messages',    usageData.message_count?.toLocaleString()],
              ['Prompt tok',  usageData.prompt_tokens?.toLocaleString()],
              ['Output tok',  usageData.completion_tokens?.toLocaleString()],
              ['Total tok',   usageData.total_tokens?.toLocaleString()],
              ['Est. cost',   `$${(usageData.cost_usd || 0).toFixed(4)}`],
            ].map(([k, v]) => (
              <div key={k} style={s.usageStat}>
                <span style={s.usageKey}>{k}</span>
                <span style={s.usageVal}>{v}</span>
              </div>
            ))}
          </>
        )}
        <div style={{ marginTop:'1.25rem', borderTop:`1px solid ${LINE}`, paddingTop:'1rem' }}>
          <button onClick={exportAll} disabled={exporting} style={{ ...s.actionBtn, width:'100%', justifyContent:'center', padding:'0.45rem' }}>
            {exporting ? 'Exporting…' : '⬇ Export All Data'}
          </button>
          <div style={{ fontSize:'13px', color:FG5, marginTop:'0.4rem', textAlign:'center' }}>
            ZIP: conversations · files · memory · graph
          </div>
        </div>
      </div>
    </div>
  )
}
