import s, { GRN, RED, AMB, FG2, FG3, FG4, CYN, LINE, LINE2, TERM, DISP } from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function IntegrationsPanel() {
  const p = usePanelProps()
  const { integOpen, setIntegOpen, sources, loading, syncing, errorMsg, popupBlocked,
    connectedTypes, CONNECTOR_LABELS, CONNECTOR_TYPES, ENABLED_CONNECTOR_TYPES,
    deleteSource, syncSource, startOAuth, statusLabel, loadSources } = p.integ

  const upcoming = CONNECTOR_TYPES.filter(t => !ENABLED_CONNECTOR_TYPES.includes(t))

  const panelStyle = {
    ...s.toolLogPanel,
    transform: integOpen ? 'translateX(0)' : 'translateX(100%)',
    width: '400px',
    maxWidth: '92vw',
  }

  const sectionLabel = {
    fontFamily: DISP,
    fontSize: '9px',
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: FG4,
    marginBottom: '0.6rem',
    marginTop: '0.5rem',
  }

  const connectorIcon = {
    google_drive: '📁',
    google_calendar: '📅',
    notion: '📝',
    github: '💻',
  }

  return (
    <div style={panelStyle}>
      <div style={s.toolLogHdr}>
        <span style={s.toolLogTitle}>Integrations</span>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          <button onClick={loadSources} style={s.refreshBtn} disabled={loading}>{loading ? '…' : '↻'}</button>
          <button onClick={() => setIntegOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>

      <div style={s.toolLogBody}>
        {errorMsg && (
          <div style={{ color: RED, fontSize: '14px', fontFamily: TERM, marginBottom: '0.75rem', padding: '0.4rem 0.5rem', border: `1px solid ${RED}`, background: 'rgba(255,34,34,0.08)' }}>
            {errorMsg}
          </div>
        )}

        {popupBlocked && (
          <div style={{ color: AMB, fontSize: '14px', fontFamily: TERM, marginBottom: '0.75rem', padding: '0.4rem 0.5rem', border: `1px solid ${AMB}`, background: 'rgba(255,176,0,0.08)' }}>
            Popup blocked. Please allow popups for this site and try again.
          </div>
        )}

        {loading && sources.length === 0 && (
          <p style={s.emptyMem}>Loading…</p>
        )}

        {!loading && sources.length > 0 && (
          <>
            <div style={sectionLabel}>Connected Sources</div>
            {sources.map(src => {
              const st = statusLabel(src.status)
              return (
                <div key={src.id} style={{ ...s.toolLogRow, marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1rem' }}>{connectorIcon[src.connector_type] || '🔌'}</span>
                    <span style={{ flex: 1, fontSize: '17px', color: '#ffffff', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {CONNECTOR_LABELS[src.connector_type] || src.connector_type}
                    </span>
                    <span style={{ ...s.statusBadge, color: st.color, borderColor: st.color, fontSize: '8px' }}>{st.text}</span>
                  </div>
                  {src.display_name && (
                    <div style={{ fontSize: '14px', color: FG4, marginTop: '2px' }}>{src.display_name}</div>
                  )}
                  {src.resource_id && !src.display_name && (
                    <div style={{ fontSize: '14px', color: FG4, marginTop: '2px' }}>{src.resource_id}</div>
                  )}
                  {src.last_sync_at && (
                    <div style={{ fontSize: '13px', color: FG4, marginTop: '2px', fontFamily: TERM }}>
                      Synced {p.fmtDate(src.last_sync_at)}
                    </div>
                  )}
                  {!src.last_sync_at && (
                    <div style={{ fontSize: '13px', color: FG4, marginTop: '2px', fontFamily: TERM }}>
                      Never synced
                    </div>
                  )}
                  {src.error && (
                    <div style={{ fontSize: '13px', color: RED, marginTop: '2px', wordBreak: 'break-word' }}>{src.error}</div>
                  )}
                  <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.4rem', alignItems: 'center' }}>
                    <button onClick={() => syncSource(src.id)} disabled={syncing.has(src.id)}
                      style={{ ...s.attachBtn, fontSize: '0.68rem', color: GRN, borderColor: 'rgba(61,255,110,0.40)' }}>
                      {syncing.has(src.id) ? '…' : '⟳ Sync'}
                    </button>
                    <div style={{ flex: 1 }} />
                    <button onClick={() => { if (window.confirm('Remove this integration?')) deleteSource(src.id) }}
                      style={s.delBtn}>🗑</button>
                  </div>
                </div>
              )
            })}
          </>
        )}

        {!loading && sources.length === 0 && (
          <p style={s.emptyMem}>
            No integrations connected yet.
            <br /><span style={{ fontSize: '0.75rem' }}>Connect a service below.</span>
          </p>
        )}

        <div style={{ ...sectionLabel, marginTop: '1.2rem' }}>Available Connectors</div>
        {ENABLED_CONNECTOR_TYPES.map(type => {
          const connected = connectedTypes.has(type)
          return (
            <div key={type} style={{ ...s.toolLogRow, marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1rem' }}>{connectorIcon[type] || '🔌'}</span>
                <span style={{ flex: 1, fontSize: '16px', color: FG2, fontWeight: 600 }}>{CONNECTOR_LABELS[type]}</span>
                {connected ? (
                  <span style={{ ...s.statusBadge, color: GRN, borderColor: GRN }}>Connected ✓</span>
                ) : (
                  <button onClick={() => startOAuth(type)}
                    style={{ ...s.attachBtn, fontSize: '0.68rem', color: CYN, borderColor: `rgba(39,216,255,0.40)` }}>
                    + Connect
                  </button>
                )}
              </div>
            </div>
          )
        })}

        {upcoming.length > 0 && (
          <>
            <div style={{ ...sectionLabel, marginTop: '1.2rem' }}>More integrations on the way</div>
            {upcoming.map(type => (
              <div key={type} style={{ ...s.toolLogRow, marginBottom: '6px', opacity: 0.6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1rem' }}>{connectorIcon[type] || '🔌'}</span>
                  <span style={{ flex: 1, fontSize: '16px', color: FG4, fontWeight: 600 }}>{CONNECTOR_LABELS[type]}</span>
                  <span style={{ ...s.statusBadge, color: FG4, borderColor: LINE2 }}>Soon</span>
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
