import s, { AMBER, FG4, RAISE } from '../../../lib/chatStyles.js'
import { fmtDate } from '../../../lib/chatUtils.js'

export default function Sidebar({
  conversations, activeConvId, selectConv,
  convSearch, setConvSearch,
  searchResults, searchLoading,
  newChat, deleteConv, exportConv,
}) {
  return (
    <div style={s.sidebar}>
      <div style={s.sideTop}><button onClick={newChat} style={s.newBtn}>+ New session</button></div>

      <div style={s.sideSearchWrap}>
        <input value={convSearch} onChange={e => setConvSearch(e.target.value)}
          placeholder="Search conversations…" style={s.sideSearchInput} />
      </div>

      <div style={s.convList}>
        {searchLoading && <p style={{ color:FG4, fontSize:'14px', textAlign:'center', padding:'0.5rem' }}>Searching…</p>}
        {(searchResults !== null ? searchResults : conversations).map(c => (
          <div key={c.id} onClick={() => selectConv(c.id)}
            style={{ ...s.convItem, background: c.id === activeConvId ? RAISE : 'transparent', boxShadow: c.id === activeConvId ? `inset 2px 0 0 ${AMBER}` : 'inset 2px 0 0 transparent' }}>
            <div style={s.convMeta}>
              <span style={s.convTitle}>{c.title}</span>
              <span style={s.convDate}>
                {fmtDate(c.updated_at)}
                {c.locked_model && <span style={{ color:AMBER, marginLeft:'4px' }}>🔒</span>}
              </span>
            </div>
            <button onClick={e => { e.stopPropagation(); exportConv(c.id, c.title) }} style={s.convDel} title="Export as Markdown">⬇</button>
            <button onClick={e => deleteConv(e, c.id)} style={s.convDel} title="Delete conversation">✕</button>
          </div>
        ))}
      </div>
    </div>
  )
}
