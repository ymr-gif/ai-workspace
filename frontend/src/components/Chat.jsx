import { useState, useRef, useEffect, useCallback } from 'react'

const MODEL_LABELS = {
  'meta/llama-3.1-8b-instruct':    'Llama 3.1 8B · fast',
  'deepseek-ai/deepseek-v4-flash': 'DeepSeek V4 Flash · code',
  'meta/llama-3.3-70b-instruct':   'Llama 3.3 70B · reasoning',
}

const SECTION_COLORS = {
  // memory sheet
  USER:        '#818cf8',
  STACK:       '#34d399',
  PROJECT:     '#fbbf24',
  CORRECTIONS: '#f87171',
  PATTERNS:    '#a78bfa',
  // project summary
  GOALS:       '#38bdf8',
  ARCH:        '#fb923c',
  STATUS:      '#4ade80',
  PENDING:     '#f472b6',
}

const s = {
  root:      { display:'flex', height:'100vh', background:'#0f172a', color:'#f1f5f9', fontFamily:'system-ui,sans-serif', position:'relative', overflow:'hidden' },

  // sidebar
  sidebar:   { width:'240px', display:'flex', flexDirection:'column', borderRight:'1px solid #1e293b', flexShrink:0 },
  sideTop:   { padding:'1rem', borderBottom:'1px solid #1e293b' },
  newBtn:    { width:'100%', padding:'0.6rem', borderRadius:'8px', background:'#6366f1',
               color:'#fff', border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.875rem' },
  convList:  { flex:1, overflowY:'auto', padding:'0.5rem' },
  convItem:  { padding:'0.6rem 0.75rem', borderRadius:'8px', cursor:'pointer', marginBottom:'2px',
               fontSize:'0.8rem', lineHeight:1.4 },
  convTitle: { display:'block', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', color:'#cbd5e1' },
  convDate:  { display:'block', fontSize:'0.7rem', color:'#475569', marginTop:'2px' },

  // chat area
  chat:      { flex:1, display:'flex', flexDirection:'column', minWidth:0 },
  header:    { display:'flex', justifyContent:'space-between', alignItems:'center',
               padding:'0.9rem 1.5rem', background:'#1e293b', borderBottom:'1px solid #334155' },
  title:     { fontWeight:700, fontSize:'1rem' },
  headerRight: { display:'flex', gap:'0.5rem', alignItems:'center' },
  memBtn:    { background:'none', border:'1px solid #334155', color:'#94a3b8',
               cursor:'pointer', padding:'0.3rem 0.75rem', borderRadius:'6px', fontSize:'0.8rem',
               display:'flex', alignItems:'center', gap:'0.35rem' },
  memDot:    { width:'6px', height:'6px', borderRadius:'50%', background:'#818cf8' },
  logout:    { background:'none', border:'1px solid #475569', color:'#94a3b8',
               cursor:'pointer', padding:'0.3rem 0.75rem', borderRadius:'6px', fontSize:'0.875rem' },
  feed:      { flex:1, overflowY:'auto', padding:'1.5rem', display:'flex', flexDirection:'column', gap:'1rem' },
  hint:      { color:'#475569', textAlign:'center', marginTop:'5rem', fontSize:'0.9rem' },
  bubble:    { maxWidth:'72%', padding:'0.75rem 1rem', borderRadius:'12px', lineHeight:1.55 },
  user:      { alignSelf:'flex-end', background:'#6366f1' },
  ai:        { alignSelf:'flex-start', background:'#1e293b', border:'1px solid #334155' },
  err:       { alignSelf:'flex-start', background:'#450a0a', border:'1px solid #991b1b', color:'#fca5a5' },
  text:      { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' },
  cursor:    { display:'inline-block', width:'2px', height:'1em', background:'#94a3b8',
               marginLeft:'2px', verticalAlign:'text-bottom', animation:'blink 1s step-end infinite' },
  tag:       { display:'block', marginTop:'0.35rem', fontSize:'0.7rem', color:'#64748b' },
  bar:       { display:'flex', gap:'0.6rem', padding:'1rem 1.5rem',
               borderTop:'1px solid #334155', background:'#1e293b' },
  input:     { flex:1, padding:'0.7rem 1rem', borderRadius:'8px', border:'1px solid #334155',
               background:'#0f172a', color:'#f1f5f9', fontSize:'1rem', outline:'none' },
  send:      { padding:'0.7rem 1.2rem', borderRadius:'8px', background:'#6366f1', color:'#fff',
               border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.95rem' },

  // memory panel overlay
  overlay:   { position:'absolute', inset:0, background:'rgba(0,0,0,0.45)', zIndex:10,
               transition:'opacity 0.25s' },

  // memory panel
  memPanel:  { position:'absolute', top:0, right:0, bottom:0, width:'360px', maxWidth:'90vw',
               background:'#0f172a', borderLeft:'1px solid #1e293b', zIndex:11,
               display:'flex', flexDirection:'column', transition:'transform 0.28s cubic-bezier(.4,0,.2,1)' },
  memHeader: { display:'flex', justifyContent:'space-between', alignItems:'center',
               padding:'1rem 1.25rem', borderBottom:'1px solid #1e293b', flexShrink:0 },
  memTitle:  { fontWeight:700, fontSize:'0.95rem', color:'#e2e8f0',
               display:'flex', alignItems:'center', gap:'0.5rem' },
  memMeta:   { fontSize:'0.7rem', color:'#475569', marginTop:'1px' },
  closeBtn:  { background:'none', border:'none', color:'#64748b', cursor:'pointer',
               fontSize:'1.1rem', padding:'0.25rem', lineHeight:1 },
  refreshBtn:{ background:'none', border:'1px solid #1e293b', color:'#64748b', cursor:'pointer',
               fontSize:'0.75rem', padding:'0.2rem 0.5rem', borderRadius:'4px' },
  memBody:   { flex:1, overflowY:'auto', padding:'1rem 1.25rem' },
  emptyMem:  { color:'#475569', fontSize:'0.85rem', textAlign:'center', marginTop:'3rem' },
  section:   { marginBottom:'1.25rem' },
  secLabel:  { fontSize:'0.7rem', fontWeight:700, letterSpacing:'0.08em',
               marginBottom:'0.4rem', padding:'0.2rem 0.5rem', borderRadius:'4px',
               display:'inline-block' },
  kv:        { display:'flex', gap:'0.5rem', fontSize:'0.82rem', lineHeight:1.5,
               padding:'0.15rem 0', borderBottom:'1px solid #1e293b' },
  kvKey:     { color:'#64748b', minWidth:'90px', flexShrink:0 },
  kvVal:     { color:'#cbd5e1', wordBreak:'break-word' },
  divider:   { borderTop:'1px solid #1e293b', margin:'1rem 0 0.75rem', display:'flex',
               alignItems:'center', gap:'0.5rem' },
  divLabel:  { fontSize:'0.65rem', fontWeight:700, letterSpacing:'0.1em', color:'#334155',
               whiteSpace:'nowrap' },
  memFooter: { padding:'0.75rem 1.25rem', borderTop:'1px solid #1e293b', flexShrink:0,
               fontSize:'0.7rem', color:'#334155', textAlign:'right' },
}

function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffH = (now - d) / 3600000
  if (diffH < 24) return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
  if (diffH < 168) return d.toLocaleDateString([], { weekday:'short', hour:'2-digit', minute:'2-digit' })
  return d.toLocaleDateString([], { month:'short', day:'numeric' })
}

function parseMemory(content) {
  if (!content) return []
  const sections = []
  let current = null

  for (const raw of content.split('\n')) {
    const line = raw.trim()
    if (!line) continue

    const headerMatch = line.match(/^\[([A-Z]+)\]$/)
    if (headerMatch) {
      current = { name: headerMatch[1], pairs: [] }
      sections.push(current)
      continue
    }

    if (current) {
      const colonIdx = line.indexOf(':')
      if (colonIdx > 0) {
        current.pairs.push({
          key: line.slice(0, colonIdx).trim(),
          val: line.slice(colonIdx + 1).trim(),
        })
      }
    }
  }

  return sections
}

export default function Chat({ token, onLogout }) {
  const [conversations, setConversations] = useState([])
  const [activeConvId,  setActiveConvId]  = useState(null)
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState('')
  const [loading,       setLoading]       = useState(false)

  const [memOpen,    setMemOpen]    = useState(false)
  const [memData,    setMemData]    = useState(null)   // { content, version, updated_at }
  const [memLoading, setMemLoading] = useState(false)

  const bottomRef = useRef(null)
  const nextId    = useRef(0)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    fetch('/api/conversations', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(setConversations)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!activeConvId) return
    fetch(`/api/conversations/${activeConvId}/messages`, { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(msgs => {
        setMessages(msgs.map(m => ({
          id:        nextId.current++,
          role:      m.role === 'assistant' ? 'ai' : 'user',
          text:      m.content,
          model:     m.model,
          streaming: false,
        })))
      })
      .catch(() => {})
  }, [activeConvId])

  async function fetchMemory() {
    setMemLoading(true)
    try {
      const r = await fetch('/api/memory', { headers: authHeaders })
      if (r.ok) setMemData(await r.json())
    } catch { /* ignore */ }
    finally { setMemLoading(false) }
  }

  function openMemory() {
    setMemOpen(true)
    fetchMemory()
  }

  function closeMemory() { setMemOpen(false) }

  function newChat() {
    setActiveConvId(null)
    setMessages([])
    setInput('')
  }

  function selectConv(id) {
    if (id === activeConvId) return
    setActiveConvId(id)
    setMessages([])
  }

  async function send(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    const userId = nextId.current++
    const aiId   = nextId.current++

    setInput('')
    setMessages(prev => [
      ...prev,
      { id: userId, role: 'user', text,  streaming: false },
      { id: aiId,   role: 'ai',   text: '', model: null, streaming: true },
    ])
    setLoading(true)

    try {
      const res = await fetch('/api/chat/stream', {
        method:  'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: text, conversation_id: activeConvId }),
      })

      if (res.status === 401) { onLogout(); return }

      if (!res.ok) {
        setMessages(prev => prev.map(m =>
          m.id === aiId ? { ...m, role: 'err', text: 'Request failed', streaming: false } : m
        ))
        return
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)

            if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === aiId ? { ...m, text: m.text + event.content } : m
              ))

            } else if (event.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === aiId ? { ...m, model: event.model, streaming: false } : m
              ))

              const cid = event.conversation_id
              if (cid) {
                setActiveConvId(cid)
                setConversations(prev => {
                  const exists = prev.find(c => c.id === cid)
                  if (exists) {
                    return [{ ...exists, updated_at: new Date().toISOString() },
                            ...prev.filter(c => c.id !== cid)]
                  }
                  return [{ id: cid, title: text.slice(0, 60), updated_at: new Date().toISOString() },
                          ...prev]
                })
              }

            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === aiId ? { ...m, role: 'err', text: event.message || 'Error', streaming: false } : m
              ))
            }
          } catch { /* ignore malformed chunks */ }
        }
      }

    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === aiId ? { ...m, role: 'err', text: `Network error: ${err.message}`, streaming: false } : m
      ))
    } finally {
      setLoading(false)
    }
  }

  const sections        = parseMemory(memData?.content)
  const projectSections = parseMemory(memData?.project_summary)
  const hasMemory       = memData?.content?.trim() || memData?.project_summary?.trim()
  const panelSlide      = memOpen ? 'translateX(0)' : 'translateX(100%)'

  return (
    <div style={s.root}>
      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        ::-webkit-scrollbar { width:4px }
        ::-webkit-scrollbar-track { background:transparent }
        ::-webkit-scrollbar-thumb { background:#1e293b; border-radius:2px }
      `}</style>

      {/* sidebar */}
      <div style={s.sidebar}>
        <div style={s.sideTop}>
          <button onClick={newChat} style={s.newBtn}>+ New Chat</button>
        </div>
        <div style={s.convList}>
          {conversations.map(c => (
            <div
              key={c.id}
              onClick={() => selectConv(c.id)}
              style={{
                ...s.convItem,
                background: c.id === activeConvId ? '#1e293b' : 'transparent',
              }}
            >
              <span style={s.convTitle}>{c.title}</span>
              <span style={s.convDate}>{fmtDate(c.updated_at)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* chat area */}
      <div style={s.chat}>
        <header style={s.header}>
          <span style={s.title}>NIM AI Gateway</span>
          <div style={s.headerRight}>
            <button onClick={openMemory} style={s.memBtn}>
              {hasMemory && <span style={s.memDot} />}
              Memory
            </button>
            <button onClick={onLogout} style={s.logout}>Logout</button>
          </div>
        </header>

        <div style={s.feed}>
          {messages.length === 0 && (
            <p style={s.hint}>
              {activeConvId ? 'Loading…' : 'Send a message to start a conversation.'}
            </p>
          )}
          {messages.map(m => (
            <div key={m.id} style={{ ...s.bubble, ...(m.role === 'user' ? s.user : m.role === 'err' ? s.err : s.ai) }}>
              <p style={s.text}>
                {m.text}
                {m.streaming && <span style={s.cursor} />}
              </p>
              {m.model && !m.streaming && (
                <span style={s.tag}>{MODEL_LABELS[m.model] || m.model}</span>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={send} style={s.bar}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ask anything…"
            disabled={loading}
            style={s.input}
          />
          <button type="submit" disabled={loading || !input.trim()} style={s.send}>
            {loading ? '…' : 'Send'}
          </button>
        </form>
      </div>

      {/* overlay */}
      {memOpen && (
        <div
          style={{ ...s.overlay, opacity: memOpen ? 1 : 0 }}
          onClick={closeMemory}
        />
      )}

      {/* memory panel */}
      <div style={{ ...s.memPanel, transform: panelSlide }}>
        <div style={s.memHeader}>
          <div>
            <div style={s.memTitle}>
              <span>⬡</span>
              Memory Sheet
              {memData?.version > 0 && (
                <span style={{ fontSize:'0.7rem', color:'#475569', fontWeight:400 }}>
                  v{memData.version}
                </span>
              )}
            </div>
            {memData?.updated_at && (
              <div style={s.memMeta}>Updated {fmtDate(memData.updated_at)}</div>
            )}
          </div>
          <div style={{ display:'flex', gap:'0.5rem', alignItems:'center' }}>
            <button onClick={fetchMemory} style={s.refreshBtn} disabled={memLoading}>
              {memLoading ? '…' : '↻'}
            </button>
            <button onClick={closeMemory} style={s.closeBtn}>✕</button>
          </div>
        </div>

        <div style={s.memBody}>
          {memLoading && !memData && (
            <p style={s.emptyMem}>Loading…</p>
          )}
          {!memLoading && !hasMemory && (
            <p style={s.emptyMem}>
              No memory yet.<br />
              <span style={{ fontSize:'0.75rem' }}>
                Updates after every 5 exchanges.
              </span>
            </p>
          )}
          {sections.length > 0 && sections.map(sec => (
            <div key={sec.name} style={s.section}>
              <span style={{
                ...s.secLabel,
                color: SECTION_COLORS[sec.name] || '#94a3b8',
                background: (SECTION_COLORS[sec.name] || '#94a3b8') + '18',
              }}>
                {sec.name}
              </span>
              {sec.pairs.map((p, i) => (
                <div key={i} style={s.kv}>
                  <span style={s.kvKey}>{p.key}</span>
                  <span style={s.kvVal}>{p.val}</span>
                </div>
              ))}
            </div>
          ))}

          {projectSections.length > 0 && (
            <>
              <div style={s.divider}>
                <span style={s.divLabel}>PROJECT STATE</span>
                <div style={{ flex:1, borderTop:'1px solid #1e293b' }} />
              </div>
              {projectSections.map(sec => (
                <div key={sec.name} style={s.section}>
                  <span style={{
                    ...s.secLabel,
                    color: SECTION_COLORS[sec.name] || '#94a3b8',
                    background: (SECTION_COLORS[sec.name] || '#94a3b8') + '18',
                  }}>
                    {sec.name}
                  </span>
                  {sec.pairs.map((p, i) => (
                    <div key={i} style={s.kv}>
                      <span style={s.kvKey}>{p.key}</span>
                      <span style={s.kvVal}>{p.val}</span>
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}
        </div>

        <div style={s.memFooter}>
          {hasMemory
            ? `${sections.length + projectSections.length} sections · ${
                ((memData.content || '') + ' ' + (memData.project_summary || ''))
                  .split(/\s+/).filter(Boolean).length
              } words`
            : 'Empty'}
        </div>
      </div>
    </div>
  )
}
