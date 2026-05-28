import s from '../../lib/chatStyles.js'

export default function UsagePanel({
  usageOpen, setUsageOpen,
  usageData, usageLoading,
  loadUsage,
}) {
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
      </div>
    </div>
  )
}
