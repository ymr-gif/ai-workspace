import s, { LINE } from '../../../lib/chatStyles.js'
import { fmtDate } from '../../../lib/chatUtils.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function ToolLogPanel() {
  const p = usePanelProps()
  const { toolLogOpen, setToolLogOpen, toolLogs, toolLogsLoading, loadToolLogs } = p.toolLog
  const { activeConvId } = p.conv
  return (
    <div style={{ ...s.toolLogPanel, transform: toolLogOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.toolLogHdr}>
        <span style={s.toolLogTitle}>🔧 AI Tool Call History</span>
        <div style={{ display:'flex', gap:'0.4rem', alignItems:'center' }}>
          <button onClick={() => loadToolLogs(activeConvId)} style={s.refreshBtn} disabled={toolLogsLoading}>
            {toolLogsLoading ? '…' : '↻'}
          </button>
          <button onClick={() => setToolLogOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>
      <div style={{ padding:'0.5rem 1.25rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', gap:'0.4rem' }}>
        <button onClick={() => loadToolLogs(activeConvId)}
          style={{ ...s.wsPill, ...(activeConvId ? s.wsPillActive : {}) }}>
          This conversation
        </button>
        <button onClick={() => loadToolLogs(null)}
          style={{ ...s.wsPill, ...(!activeConvId ? s.wsPillActive : {}) }}>
          All
        </button>
      </div>
      <div style={s.toolLogBody}>
        {toolLogsLoading && <p style={s.emptyMem}>Loading…</p>}
        {!toolLogsLoading && toolLogs.length === 0 && (
          <p style={s.emptyMem}>No tool calls yet.<br /><span style={{ fontSize:'0.75rem' }}>Attach files and ask the AI to read or edit them.</span></p>
        )}
        {!toolLogsLoading && toolLogs.map(log => (
          <div key={log.id} style={s.toolLogRow}>
            <div style={s.toolLogMeta}>
              <span style={s.toolLogName}>⚙ {log.tool_name}</span>
              <span style={s.toolLogTime}>{fmtDate(log.created_at)}</span>
            </div>
            {log.args && Object.keys(log.args).length > 0 && (
              <div style={s.toolLogArgs}>
                {Object.entries(log.args).map(([k, v]) =>
                  `${k}: ${typeof v === 'string' ? v.slice(0, 80) : JSON.stringify(v).slice(0, 80)}`
                ).join(' · ')}
              </div>
            )}
            {log.result_preview && (
              <div style={s.toolLogResult}>{log.result_preview.slice(0, 200)}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
