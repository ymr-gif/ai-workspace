/* NIM AI Gateway — core components. Attaches to window. */
const NIM_S = window.NIM_S;

/* ---- tiny markdown renderer (demo-only; real app uses react-markdown) ---- */
function nimMd(text) {
  const esc = (t) => t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>');
  const lines = text.split('\n'); let html = ''; let inList = false;
  for (const ln of lines) {
    if (/^\s*[-*]\s+/.test(ln)) {
      if (!inList) { html += '<ul>'; inList = true; }
      html += '<li>' + inline(ln.replace(/^\s*[-*]\s+/, '')) + '</li>';
    } else {
      if (inList) { html += '</ul>'; inList = false; }
      if (ln.trim()) html += '<p>' + inline(ln) + '</p>';
    }
  }
  if (inList) html += '</ul>';
  return html;
}
function NimMd({ text }) {
  return <div className="md-body" dangerouslySetInnerHTML={{ __html: nimMd(text) }} />;
}

/* ---------------------------------------------------------------- Login */
function LoginScreen({ onLogin }) {
  const ls = {
    page: { display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' },
    box:  { background:'#1e293b', padding:'2rem', borderRadius:'12px', width:'340px' },
    h2:   { marginBottom:'1.5rem', fontWeight:700, fontSize:'1.2rem', color:'#f1f5f9' },
    form: { display:'flex', flexDirection:'column', gap:'0.8rem' },
    input:{ padding:'0.65rem 0.9rem', borderRadius:'8px', border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:'1rem', outline:'none' },
    btn:  { padding:'0.75rem', borderRadius:'8px', background:'#6366f1', color:'#fff', border:'none', cursor:'pointer', fontWeight:600, fontSize:'1rem' },
    hint: { fontSize:'0.72rem', color:'#475569', textAlign:'center', marginTop:'0.25rem' },
  };
  return (
    <div style={ls.page}>
      <div style={ls.box}>
        <h2 style={ls.h2}>NIM AI Gateway</h2>
        <form style={ls.form} onSubmit={(e) => { e.preventDefault(); onLogin(); }}>
          <input style={ls.input} placeholder="Username" defaultValue="yusuf" />
          <input style={ls.input} type="password" placeholder="Password" defaultValue="demo" />
          <button type="submit" style={ls.btn}>Sign in</button>
          <div style={ls.hint}>demo — any credentials work</div>
        </form>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Sidebar */
function Sidebar({ conversations, activeConvId, selectConv, wsList, wsId, setWsId, search, setSearch, newChat }) {
  const wsPill = (active) => ({ ...NIM_S.wsPill, ...(active ? NIM_S.wsPillActive : {}) });
  const shown = conversations.filter(c => wsId === null || c.workspace_id === wsId)
    .filter(c => !search || c.title.toLowerCase().includes(search.toLowerCase()));
  return (
    <div style={NIM_S.sidebar}>
      <div style={NIM_S.sideTop}><button onClick={newChat} style={NIM_S.newBtn}>+ New Session</button></div>
      <div style={{ padding:'0.4rem 0.5rem', borderBottom:`1px solid ${window.NIM_C.LINE}`, display:'flex', gap:'0.25rem', flexWrap:'wrap', alignItems:'center' }}>
        <button onClick={() => setWsId(null)} style={wsPill(wsId === null)}>All</button>
        {wsList.map(ws => (
          <span key={ws.id} style={{ display:'inline-flex', alignItems:'center' }}>
            <button onClick={() => setWsId(wsId === ws.id ? null : ws.id)} style={wsPill(wsId === ws.id)}>{ws.name}</button>
            <button style={NIM_S.wsGearBtn} title="Workspace settings">⚙</button>
          </span>
        ))}
        <button style={NIM_S.wsPlusBtn} title="New workspace">+</button>
      </div>
      <div style={NIM_S.sideSearchWrap}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search conversations…" style={NIM_S.sideSearchInput} />
      </div>
      <div style={NIM_S.convList} className="nim-scroll">
        {shown.map(c => (
          <div key={c.id} onClick={() => selectConv(c.id)}
            style={{ ...NIM_S.convItem, background: c.id === activeConvId ? '#121212' : 'transparent', borderLeftColor: c.id === activeConvId ? window.NIM_C.RED : 'transparent' }}>
            <div style={NIM_S.convMeta}>
              <span style={NIM_S.convTitle}>{c.title}</span>
              <span style={NIM_S.convDate}>
                {c.updated_at}
                {c.memory_enabled === false && <span style={{ color:window.NIM_C.FG4, marginLeft:'4px' }}>⊘</span>}
                {c.locked_model && <span style={{ color:window.NIM_C.RED, marginLeft:'4px' }}>🔒</span>}
              </span>
            </div>
            <button onClick={e => e.stopPropagation()} style={NIM_S.convDel} title="Export as Markdown">⬇</button>
            <button onClick={e => e.stopPropagation()} style={NIM_S.convDel} title="Delete">✕</button>
          </div>
        ))}
        {shown.length === 0 && <p style={{ color:window.NIM_C.FG4, fontFamily:window.NIM_C.TERM, fontSize:'16px', textAlign:'center', padding:'1rem' }}>No sessions.</p>}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Header */
function ChatHeader({ activeConvId, ctxOn, toggleCtx, openMemory, openFiles, attachedCount,
                      usageOpen, toggleUsage, logOpen, toggleLog, insightsOpen, toggleInsights, lockedLabel, onLogout }) {
  const tog = (on, c, bd) => on ? { color: c, borderColor: bd } : {};
  return (
    <header style={NIM_S.header}>
      <span style={NIM_S.title}>
        NIM&nbsp;//&nbsp;GATEWAY
        {lockedLabel && <span style={{ fontFamily:window.NIM_C.TERM, fontSize:'14px', color:window.NIM_C.RED, marginLeft:'0.6rem', letterSpacing:0, textShadow:'none' }}>🔒 {lockedLabel}</span>}
      </span>
      <div style={NIM_S.headerRight}>
        {activeConvId && (
          <button onClick={toggleCtx} title={ctxOn ? 'Context ON' : 'Context OFF'}
            style={{ ...NIM_S.hdrBtn, color: ctxOn ? window.NIM_C.GRN : window.NIM_C.FG4, borderColor: ctxOn ? 'rgba(61,255,110,0.5)' : window.NIM_C.LINE2 }}>
            {ctxOn ? '◉' : '○'} Ctx
          </button>
        )}
        {activeConvId && <button style={NIM_S.hdrBtn} title="Conversation settings">⚙</button>}
        <button onClick={toggleUsage} style={{ ...NIM_S.hdrBtn, ...tog(usageOpen, window.NIM_C.GRN, 'rgba(61,255,110,0.5)') }} title="Token usage & cost">$ Usage</button>
        <button onClick={toggleLog} style={{ ...NIM_S.hdrBtn, ...tog(logOpen, window.NIM_C.CYN, 'rgba(39,216,255,0.5)') }} title="Tool call history">🔧 Log</button>
        <button onClick={openFiles} style={{ ...NIM_S.hdrBtn, ...(attachedCount > 0 ? { color:window.NIM_C.AMB, borderColor:'rgba(255,176,0,0.5)' } : {}) }}>
          {attachedCount > 0 ? `📎 ${attachedCount}` : '📎'} Files
        </button>
        <button onClick={openMemory} style={NIM_S.hdrBtn}><span style={NIM_S.memDot} />Memory</button>
        <button onClick={toggleInsights} style={{ ...NIM_S.hdrBtn, ...tog(insightsOpen, window.NIM_C.CYN, 'rgba(39,216,255,0.5)') }} title="AI insights about you">
          💡<span style={NIM_S.unreadBadge}>2</span>
        </button>
        <button onClick={onLogout} style={NIM_S.logout}>◄ Exit</button>
      </div>
    </header>
  );
}

Object.assign(window, { nimMd, NimMd, LoginScreen, Sidebar, ChatHeader });
