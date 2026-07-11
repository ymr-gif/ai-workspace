import s, { LINE, CYN } from '../../../lib/chatStyles.js'
import { fmtDate } from '../../../lib/chatUtils.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function InsightsPanel() {
  const p = usePanelProps()
  const { insightsOpen, setInsightsOpen, insights, insightsLoading, loadInsights, markInsightRead, deleteInsight } = p.insights
  return (
    <div style={s.insightsPanel}>
      <div style={s.insightsHdr}>
        <span style={s.insightsTitle}>💡 Insights</span>
        <div style={{ display:'flex', gap:'0.4rem', alignItems:'center' }}>
          <button onClick={() => loadInsights(true)} style={s.refreshBtn} disabled={insightsLoading}>{insightsLoading ? '…' : '↻'}</button>
        </div>
      </div>
      <div style={s.insightsBody}>
        {insightsLoading && insights.length === 0 && <p style={s.emptyMem}>Loading…</p>}
        {!insightsLoading && insights.length === 0 && (
          <p style={s.emptyMem}>No insights yet.<br /><span style={{ fontSize:'0.75rem' }}>Generated after every 10 exchanges.</span></p>
        )}
        {insights.map(i => (
          <div key={i.id} style={{ ...s.insightRow, borderColor: i.is_read ? LINE : `rgba(79,156,240,0.35)`, opacity: i.is_read ? 0.65 : 1 }}
            onClick={() => !i.is_read && markInsightRead(i.id)}>
            {!i.is_read && <span style={s.insightDot} />}
            <div style={{ ...s.insightContent, paddingLeft: i.is_read ? '15px' : 0 }}>
              <div>{i.content}</div>
              <div style={s.insightMeta}>{fmtDate(i.created_at)}{i.is_read ? ' · read' : ''}</div>
            </div>
            <button style={s.insightDel} onClick={e => { e.stopPropagation(); deleteInsight(i.id) }} title="Delete">🗑</button>
          </div>
        ))}
      </div>
    </div>
  )
}
