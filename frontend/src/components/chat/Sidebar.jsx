import s from '../../lib/chatStyles.js'
import { fmtDate } from '../../lib/chatUtils.js'

export default function Sidebar({
  conversations, activeConvId, selectConv,
  sidebarWsList, sidebarWsId, setSidebarWsId,
  convSearch, setConvSearch,
  searchResults, searchLoading,
  newChat, deleteConv, exportConv,
  openCreateWs, openEditWs,
}) {
  return (
    <div style={s.sidebar}>
      <div style={s.sideTop}><button onClick={newChat} style={s.newBtn}>+ New Chat</button></div>

      <div style={{ padding:'0.4rem 0.5rem', borderBottom:'1px solid #1e293b', display:'flex', gap:'0.25rem', flexWrap:'wrap', alignItems:'center' }}>
        <button onClick={() => setSidebarWsId(null)}
          style={{ ...s.wsPill, ...(sidebarWsId === null ? s.wsPillActive : {}) }}>
          All
        </button>
        {sidebarWsList.map(ws => (
          <span key={ws.id} style={{ display:'inline-flex', alignItems:'center' }}>
            <button onClick={() => setSidebarWsId(sidebarWsId === ws.id ? null : ws.id)}
              style={{ ...s.wsPill, ...(sidebarWsId === ws.id ? s.wsPillActive : {}) }}>
              {ws.name}
            </button>
            <button onClick={e => openEditWs(ws, e)} style={s.wsGearBtn} title="Workspace settings">⚙</button>
          </span>
        ))}
        <button onClick={openCreateWs} style={s.wsPlusBtn} title="New workspace">+</button>
      </div>

      <div style={s.sideSearchWrap}>
        <input value={convSearch} onChange={e => setConvSearch(e.target.value)}
          placeholder="Search conversations…" style={s.sideSearchInput} />
      </div>

      <div style={s.convList}>
        {searchLoading && <p style={{ color:'#475569', fontSize:'0.75rem', textAlign:'center', padding:'0.5rem' }}>Searching…</p>}
        {(searchResults !== null ? searchResults : conversations.filter(c => sidebarWsId === null || c.workspace_id === sidebarWsId)).map(c => (
          <div key={c.id} onClick={() => selectConv(c.id)}
            style={{ ...s.convItem, background: c.id === activeConvId ? '#1e293b' : 'transparent' }}>
            <div style={s.convMeta}>
              <span style={s.convTitle}>{c.title}</span>
              <span style={s.convDate}>
                {fmtDate(c.updated_at)}
                {c.memory_enabled === false && <span style={{ color:'#475569', marginLeft:'4px' }}>⊘</span>}
                {c.locked_model && <span style={{ color:'#6366f1', marginLeft:'4px' }}>🔒</span>}
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
