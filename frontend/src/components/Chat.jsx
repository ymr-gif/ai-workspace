import { useState, useRef, useEffect, useCallback } from 'react'

const MODEL_LABELS = {
  'meta/llama-3.1-8b-instruct':    'Llama 3.1 8B · fast',
  'deepseek-ai/deepseek-v4-flash': 'DeepSeek V4 Flash · code',
  'meta/llama-3.3-70b-instruct':   'Llama 3.3 70B · reasoning',
}

const SECTION_COLORS = {
  USER:        '#818cf8',
  STACK:       '#34d399',
  PROJECT:     '#fbbf24',
  CORRECTIONS: '#f87171',
  PATTERNS:    '#a78bfa',
  GOALS:       '#38bdf8',
  ARCH:        '#fb923c',
  STATUS:      '#4ade80',
  PENDING:     '#f472b6',
}

const s = {
  root:      { display:'flex', height:'100vh', background:'#0f172a', color:'#f1f5f9', fontFamily:'system-ui,sans-serif', position:'relative', overflow:'hidden' },

  sidebar:   { width:'240px', display:'flex', flexDirection:'column', borderRight:'1px solid #1e293b', flexShrink:0 },
  sideTop:   { padding:'1rem', borderBottom:'1px solid #1e293b' },
  newBtn:    { width:'100%', padding:'0.6rem', borderRadius:'8px', background:'#6366f1',
               color:'#fff', border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.875rem' },
  convList:  { flex:1, overflowY:'auto', padding:'0.5rem' },
  convItem:  { padding:'0.6rem 0.75rem', borderRadius:'8px', cursor:'pointer', marginBottom:'2px',
               fontSize:'0.8rem', lineHeight:1.4 },
  convTitle: { display:'block', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', color:'#cbd5e1' },
  convDate:  { display:'block', fontSize:'0.7rem', color:'#475569', marginTop:'2px' },

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

  overlay:   { position:'absolute', inset:0, background:'rgba(0,0,0,0.45)', zIndex:10,
               transition:'opacity 0.25s' },

  memPanel:  { position:'absolute', top:0, right:0, bottom:0, width:'380px', maxWidth:'90vw',
               background:'#0f172a', borderLeft:'1px solid #1e293b', zIndex:11,
               display:'flex', flexDirection:'column', transition:'transform 0.28s cubic-bezier(.4,0,.2,1)' },
  memHeader: { padding:'1rem 1.25rem 0.75rem', borderBottom:'1px solid #1e293b', flexShrink:0 },
  memTitleRow: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.25rem' },
  memTitle:  { fontWeight:700, fontSize:'0.95rem', color:'#e2e8f0',
               display:'flex', alignItems:'center', gap:'0.5rem' },
  memMeta:   { fontSize:'0.7rem', color:'#475569' },
  memHdrBtns: { display:'flex', gap:'0.4rem', alignItems:'center' },
  refreshBtn:{ background:'none', border:'1px solid #1e293b', color:'#64748b', cursor:'pointer',
               fontSize:'0.75rem', padding:'0.2rem 0.5rem', borderRadius:'4px' },
  closeBtn:  { background:'none', border:'none', color:'#64748b', cursor:'pointer',
               fontSize:'1.1rem', padding:'0.25rem', lineHeight:1 },

  tabBar:    { display:'flex', gap:'0', borderBottom:'1px solid #1e293b', flexShrink:0 },
  tabBtn:    { flex:1, padding:'0.5rem', background:'none', border:'none', cursor:'pointer',
               fontSize:'0.78rem', color:'#475569', borderBottom:'2px solid transparent',
               transition:'color 0.15s' },
  tabActive: { color:'#818cf8', borderBottomColor:'#818cf8' },

  memBody:   { flex:1, overflowY:'auto', padding:'1rem 1.25rem' },
  emptyMem:  { color:'#475569', fontSize:'0.85rem', textAlign:'center', marginTop:'3rem' },
  section:   { marginBottom:'1.25rem' },
  secLabel:  { fontSize:'0.7rem', fontWeight:700, letterSpacing:'0.08em',
               marginBottom:'0.4rem', padding:'0.2rem 0.5rem', borderRadius:'4px',
               display:'inline-block' },
  kv:        { display:'flex', gap:'0.5rem', fontSize:'0.82rem', lineHeight:1.5,
               padding:'0.15rem 0', borderBottom:'1px solid #1e293b' },
  kvKey:     { color:'#64748b', minWidth:'90px', flexShrink:0 },
  kvVal:     { color:'#cbd5e1', wordBreak:'break-word', flex:1 },
  divider:   { borderTop:'1px solid #1e293b', margin:'1rem 0 0.75rem', display:'flex',
               alignItems:'center', gap:'0.5rem' },
  divLabel:  { fontSize:'0.65rem', fontWeight:700, letterSpacing:'0.1em', color:'#334155',
               whiteSpace:'nowrap' },

  memFooter: { padding:'0.75rem 1.25rem', borderTop:'1px solid #1e293b', flexShrink:0,
               display:'flex', flexDirection:'column', gap:'0.5rem' },
  footerRow: { display:'flex', justifyContent:'space-between', alignItems:'center' },
  footerActions: { display:'flex', gap:'0.4rem' },
  actionBtn: { background:'none', border:'1px solid #1e293b', color:'#64748b', cursor:'pointer',
               fontSize:'0.72rem', padding:'0.2rem 0.5rem', borderRadius:'4px',
               display:'flex', alignItems:'center', gap:'0.25rem' },
  footerStats: { fontSize:'0.7rem', color:'#334155' },

  memToggleRow: { display:'flex', alignItems:'center', justifyContent:'space-between',
                  padding:'0.4rem 0', borderTop:'1px solid #0f172a' },
  memToggleLabel: { fontSize:'0.72rem', color:'#475569' },
  togglePill: { display:'flex', alignItems:'center', gap:'0.35rem', background:'none',
                border:'1px solid #334155', borderRadius:'12px', padding:'0.2rem 0.6rem',
                cursor:'pointer', fontSize:'0.72rem', transition:'all 0.15s' },

  updatingDot: { width:'6px', height:'6px', borderRadius:'50%', background:'#34d399',
                 animation:'pulse 1s ease-in-out infinite' },
  flashBody:   { animation:'memFlash 1.5s ease-out' },

  editArea:  { width:'100%', background:'#0a1220', border:'1px solid #1e293b',
               borderRadius:'6px', color:'#cbd5e1', fontSize:'0.8rem', lineHeight:1.6,
               padding:'0.6rem', resize:'vertical', outline:'none', fontFamily:'monospace',
               boxSizing:'border-box' },
  editLabel: { fontSize:'0.7rem', color:'#475569', marginBottom:'0.3rem', marginTop:'0.75rem' },
  editBtns:  { display:'flex', gap:'0.5rem', marginTop:'1rem' },
  saveBtn:   { padding:'0.4rem 1rem', borderRadius:'6px', background:'#6366f1', color:'#fff',
               border:'none', cursor:'pointer', fontSize:'0.82rem', fontWeight:600 },
  cancelBtn: { padding:'0.4rem 0.75rem', borderRadius:'6px', background:'none',
               color:'#64748b', border:'1px solid #334155', cursor:'pointer', fontSize:'0.82rem' },

  historyList: { display:'flex', flexDirection:'column', gap:'0.5rem' },
  historyItem: { padding:'0.5rem 0.75rem', borderRadius:'6px', border:'1px solid #1e293b',
                 cursor:'pointer', fontSize:'0.8rem', background:'#0a1220',
                 transition:'border-color 0.15s' },
  historyMeta: { color:'#475569', fontSize:'0.7rem', marginTop:'0.2rem' },
  diffBox:     { marginTop:'1rem', padding:'0.75rem', background:'#0a1220',
                 borderRadius:'6px', border:'1px solid #1e293b' },
  diffTitle:   { fontSize:'0.7rem', color:'#64748b', marginBottom:'0.5rem', fontWeight:600 },
  diffLine:    { fontSize:'0.78rem', lineHeight:1.6, padding:'0.05rem 0.4rem',
                 borderRadius:'3px', marginBottom:'1px', fontFamily:'monospace',
                 wordBreak:'break-word' },
  diffAdded:   { background:'rgba(52,211,153,0.12)', color:'#34d399' },
  diffRemoved: { background:'rgba(248,113,113,0.12)', color:'#f87171' },
  diffSame:    { color:'#475569' },
}

function fmtDate(iso) {
  if (!iso) return ''
  const d   = new Date(iso)
  const now = new Date()
  const diffH = (now - d) / 3600000
  if (diffH < 24)  return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
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
    const hm = line.match(/^\[([A-Z]+)\]$/)
    if (hm) { current = { name: hm[1], pairs: [] }; sections.push(current); continue }
    if (current) {
      const ci = line.indexOf(':')
      if (ci > 0) current.pairs.push({ key: line.slice(0, ci).trim(), val: line.slice(ci + 1).trim() })
    }
  }
  return sections
}

function computeDiff(oldText, newText) {
  const oldLines = (oldText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const newLines = (newText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const oldSet   = new Set(oldLines)
  const newSet   = new Set(newLines)
  const result   = []
  for (const l of newLines) result.push({ type: oldSet.has(l) ? 'same' : 'added',   line: l })
  for (const l of oldLines) if (!newSet.has(l)) result.push({ type: 'removed', line: l })
  return result
}

export default function Chat({ token, onLogout }) {
  const [conversations,  setConversations]  = useState([])
  const [activeConvId,   setActiveConvId]   = useState(null)
  const [messages,       setMessages]       = useState([])
  const [input,          setInput]          = useState('')
  const [loading,        setLoading]        = useState(false)

  const [memOpen,        setMemOpen]        = useState(false)
  const [memTab,         setMemTab]         = useState('view')  // 'view' | 'edit' | 'history'
  const [memData,        setMemData]        = useState(null)
  const [memLoading,     setMemLoading]     = useState(false)
  const [memFlashed,     setMemFlashed]     = useState(false)
  const [memTick,        setMemTick]        = useState(0)
  const [memPending,     setMemPending]     = useState(false)

  const [editContent,    setEditContent]    = useState('')
  const [editProj,       setEditProj]       = useState('')
  const [memSaving,      setMemSaving]      = useState(false)

  const [memHistory,     setMemHistory]     = useState([])
  const [histLoading,    setHistLoading]    = useState(false)
  const [diffIdx,        setDiffIdx]        = useState(null)

  const [convMemEnabled, setConvMemEnabled] = useState(true)
  const [memToggling,    setMemToggling]    = useState(false)

  const bottomRef   = useRef(null)
  const nextId      = useRef(0)
  const prevMemSig  = useRef('')
  const importRef   = useRef(null)

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
          id: nextId.current++, role: m.role === 'assistant' ? 'ai' : 'user',
          text: m.content, model: m.model, streaming: false,
        })))
      })
      .catch(() => {})
  }, [activeConvId])

  const pollMemory = useCallback(async (showSpinner = false) => {
    if (showSpinner) setMemLoading(true)
    try {
      const r = await fetch('/api/memory', { headers: authHeaders })
      if (!r.ok) return
      const data = await r.json()
      const sig  = (data.content || '') + '|' + (data.project_summary || '')
      if (sig !== prevMemSig.current) {
        prevMemSig.current = sig
        setMemData(data)
        setMemFlashed(true)
        setTimeout(() => setMemFlashed(false), 1800)
      }
    } catch { /* ignore */ }
    finally { if (showSpinner) setMemLoading(false) }
  }, [token])

  useEffect(() => {
    if (!memOpen) return
    pollMemory(true)
    const id = setInterval(() => pollMemory(), 20000)
    return () => clearInterval(id)
  }, [memOpen])

  useEffect(() => {
    if (memTick === 0) return
    setMemPending(true)
    let count = 0
    const id = setInterval(() => {
      pollMemory()
      if (++count >= 15) { clearInterval(id); setMemPending(false) }
    }, 2000)
    return () => { clearInterval(id); setMemPending(false) }
  }, [memTick])

  useEffect(() => {
    if (memTab !== 'history') return
    setHistLoading(true)
    fetch('/api/memory/history', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(h => { setMemHistory(h); setDiffIdx(null) })
      .catch(() => {})
      .finally(() => setHistLoading(false))
  }, [memTab])

  function openMemory()  { setMemOpen(true);  setMemTab('view') }
  function closeMemory() { setMemOpen(false) }

  function newChat() {
    setActiveConvId(null); setMessages([]); setInput(''); setConvMemEnabled(true)
  }

  function selectConv(id) {
    if (id === activeConvId) return
    setActiveConvId(id)
    setMessages([])
    const conv = conversations.find(c => c.id === id)
    setConvMemEnabled(conv?.memory_enabled !== false)
  }

  function openEdit() {
    setEditContent(memData?.content || '')
    setEditProj(memData?.project_summary || '')
    setMemTab('edit')
  }

  function cancelEdit() { setMemTab('view') }

  async function saveEdit() {
    setMemSaving(true)
    try {
      const r = await fetch('/api/memory', {
        method:  'PUT',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ content: editContent, project_summary: editProj }),
      })
      if (!r.ok) return
      const data = await r.json()
      setMemData(data)
      prevMemSig.current = (data.content || '') + '|' + (data.project_summary || '')
      setMemFlashed(true)
      setTimeout(() => setMemFlashed(false), 1800)
      setMemTab('view')
    } catch { /* ignore */ }
    finally { setMemSaving(false) }
  }

  async function exportMemory() {
    try {
      const r = await fetch('/api/memory/export', { headers: authHeaders })
      if (!r.ok) return
      const blob = await r.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = 'memory.json'; a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  async function handleImport(e) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const json = JSON.parse(await file.text())
      const r    = await fetch('/api/memory/import', {
        method:  'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ content: json.content || '', project_summary: json.project_summary || '' }),
      })
      if (!r.ok) return
      const data = await r.json()
      setMemData(data)
      prevMemSig.current = (data.content || '') + '|' + (data.project_summary || '')
      setMemFlashed(true)
      setTimeout(() => setMemFlashed(false), 1800)
    } catch { /* ignore */ }
    e.target.value = ''
  }

  async function toggleConvMemory() {
    if (!activeConvId || memToggling) return
    const next = !convMemEnabled
    setMemToggling(true)
    try {
      await fetch(`/api/conversations/${activeConvId}`, {
        method:  'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body:    JSON.stringify({ memory_enabled: next }),
      })
      setConvMemEnabled(next)
      setConversations(prev => prev.map(c =>
        c.id === activeConvId ? { ...c, memory_enabled: next } : c
      ))
    } catch { /* ignore */ }
    finally { setMemToggling(false) }
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
              setMemTick(t => t + 1)
              const cid = event.conversation_id
              if (cid) {
                setActiveConvId(cid)
                setConversations(prev => {
                  const exists = prev.find(c => c.id === cid)
                  if (exists) return [{ ...exists, updated_at: new Date().toISOString() }, ...prev.filter(c => c.id !== cid)]
                  return [{ id: cid, title: text.slice(0, 60), updated_at: new Date().toISOString(), memory_enabled: true }, ...prev]
                })
              }
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === aiId ? { ...m, role: 'err', text: event.message || 'Error', streaming: false } : m
              ))
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === aiId ? { ...m, role: 'err', text: `Network error: ${err.message}`, streaming: false } : m
      ))
    } finally { setLoading(false) }
  }

  const sections        = parseMemory(memData?.content)
  const projectSections = parseMemory(memData?.project_summary)
  const hasMemory       = memData?.content?.trim() || memData?.project_summary?.trim()
  const panelSlide      = memOpen ? 'translateX(0)' : 'translateX(100%)'

  const wordCount = hasMemory
    ? ((memData.content || '') + ' ' + (memData.project_summary || '')).split(/\s+/).filter(Boolean).length
    : 0

  // diff view
  const diffTarget = diffIdx !== null ? memHistory[diffIdx] : null
  const diffLines  = diffTarget
    ? computeDiff(
        (diffTarget.content || '') + '\n' + (diffTarget.project_summary || ''),
        (memData?.content  || '') + '\n' + (memData?.project_summary  || ''),
      )
    : []

  return (
    <div style={s.root}>
      <style>{`
        @keyframes blink    { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes pulse    { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes memFlash { 0%{background:rgba(52,211,153,0.08)} 100%{background:transparent} }
        ::-webkit-scrollbar       { width:4px }
        ::-webkit-scrollbar-track { background:transparent }
        ::-webkit-scrollbar-thumb { background:#1e293b; border-radius:2px }
        textarea:focus { border-color:#6366f1 !important }
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
              style={{ ...s.convItem, background: c.id === activeConvId ? '#1e293b' : 'transparent' }}
            >
              <span style={s.convTitle}>{c.title}</span>
              <span style={s.convDate}>
                {fmtDate(c.updated_at)}
                {c.memory_enabled === false && <span style={{ color:'#475569', marginLeft:'4px' }}>⊘mem</span>}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* chat area */}
      <div style={s.chat}>
        <header style={s.header}>
          <span style={s.title}>NIM AI Gateway</span>
          <div style={s.headerRight}>
            {activeConvId && (
              <button
                onClick={toggleConvMemory}
                disabled={memToggling}
                title={convMemEnabled ? 'Memory injection ON — click to disable' : 'Memory injection OFF — click to enable'}
                style={{
                  ...s.memBtn,
                  color:       convMemEnabled ? '#34d399' : '#475569',
                  borderColor: convMemEnabled ? '#1e4e3a' : '#334155',
                  opacity:     memToggling ? 0.5 : 1,
                }}
              >
                {convMemEnabled ? '◉' : '○'} Ctx
              </button>
            )}
            <button onClick={openMemory} style={s.memBtn}>
              {memPending
                ? <span style={s.updatingDot} title="Memory updating…" />
                : hasMemory && <span style={s.memDot} />
              }
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

      {memOpen && <div style={{ ...s.overlay, opacity: 1 }} onClick={closeMemory} />}

      {/* memory panel */}
      <div style={{ ...s.memPanel, transform: panelSlide }}>

        {/* header */}
        <div style={s.memHeader}>
          <div style={s.memTitleRow}>
            <div style={s.memTitle}>
              <span>⬡</span>
              Memory Sheet
              {memData?.version > 0 && (
                <span style={{ fontSize:'0.7rem', color:'#475569', fontWeight:400 }}>v{memData.version}</span>
              )}
            </div>
            <div style={s.memHdrBtns}>
              <button onClick={() => pollMemory(true)} style={s.refreshBtn} disabled={memLoading}>
                {memLoading ? '…' : '↻'}
              </button>
              <button onClick={closeMemory} style={s.closeBtn}>✕</button>
            </div>
          </div>
          <div style={s.memMeta}>
            {memPending
              ? <span style={{ color:'#34d399' }}>updating…</span>
              : memData?.updated_at
                ? `Updated ${fmtDate(memData.updated_at)}`
                : 'No memory yet'
            }
          </div>
        </div>

        {/* tab bar */}
        <div style={s.tabBar}>
          {['view', 'edit', 'history'].map(tab => (
            <button
              key={tab}
              onClick={() => tab === 'edit' ? openEdit() : setMemTab(tab)}
              style={{ ...s.tabBtn, ...(memTab === tab ? s.tabActive : {}) }}
            >
              {tab === 'view' ? 'View' : tab === 'edit' ? 'Edit' : 'History'}
            </button>
          ))}
        </div>

        {/* body */}
        <div style={{ ...s.memBody, ...(memFlashed && memTab === 'view' ? s.flashBody : {}) }}>

          {/* ── VIEW tab ── */}
          {memTab === 'view' && (
            <>
              {memLoading && !memData && <p style={s.emptyMem}>Loading…</p>}
              {!memLoading && !hasMemory && (
                <p style={s.emptyMem}>
                  No memory yet.<br />
                  <span style={{ fontSize:'0.75rem' }}>Updates after every few exchanges.</span>
                </p>
              )}
              {sections.length > 0 && sections.map(sec => (
                <div key={sec.name} style={s.section}>
                  <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name] || '#94a3b8', background: (SECTION_COLORS[sec.name] || '#94a3b8') + '18' }}>
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
                      <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name] || '#94a3b8', background: (SECTION_COLORS[sec.name] || '#94a3b8') + '18' }}>
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
            </>
          )}

          {/* ── EDIT tab ── */}
          {memTab === 'edit' && (
            <div>
              <div style={s.editLabel}>USER STATE (key: value per line, headers as [SECTION])</div>
              <textarea
                value={editContent}
                onChange={e => setEditContent(e.target.value)}
                rows={10}
                style={s.editArea}
                placeholder="[USER]&#10;name: Alice&#10;role: developer"
              />
              <div style={s.editLabel}>PROJECT STATE</div>
              <textarea
                value={editProj}
                onChange={e => setEditProj(e.target.value)}
                rows={7}
                style={s.editArea}
                placeholder="[GOALS]&#10;goal: Build AI gateway"
              />
              <div style={s.editBtns}>
                <button onClick={saveEdit} disabled={memSaving} style={s.saveBtn}>
                  {memSaving ? 'Saving…' : 'Save'}
                </button>
                <button onClick={cancelEdit} style={s.cancelBtn}>Cancel</button>
              </div>
            </div>
          )}

          {/* ── HISTORY tab ── */}
          {memTab === 'history' && (
            <div>
              {histLoading && <p style={s.emptyMem}>Loading…</p>}
              {!histLoading && memHistory.length === 0 && (
                <p style={s.emptyMem}>No history yet.</p>
              )}
              {!histLoading && memHistory.length > 0 && (
                <>
                  <div style={{ fontSize:'0.7rem', color:'#475569', marginBottom:'0.75rem' }}>
                    Select a version to diff against current
                  </div>
                  <div style={s.historyList}>
                    {memHistory.map((v, i) => (
                      <div
                        key={i}
                        onClick={() => setDiffIdx(diffIdx === i ? null : i)}
                        style={{
                          ...s.historyItem,
                          borderColor: diffIdx === i ? '#6366f1' : '#1e293b',
                        }}
                      >
                        <span style={{ color:'#cbd5e1' }}>v{v.version}</span>
                        <div style={s.historyMeta}>{fmtDate(v.created_at)}</div>
                      </div>
                    ))}
                  </div>

                  {diffTarget && diffLines.length > 0 && (
                    <div style={s.diffBox}>
                      <div style={s.diffTitle}>v{diffTarget.version} → current (v{memData?.version})</div>
                      {diffLines.map((d, i) => (
                        <div
                          key={i}
                          style={{
                            ...s.diffLine,
                            ...(d.type === 'added'   ? s.diffAdded   :
                                d.type === 'removed' ? s.diffRemoved : s.diffSame),
                          }}
                        >
                          {d.type === 'added' ? '+ ' : d.type === 'removed' ? '− ' : '  '}
                          {d.line}
                        </div>
                      ))}
                      {diffLines.every(d => d.type === 'same') && (
                        <div style={{ ...s.diffLine, ...s.diffSame }}>No changes</div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* footer */}
        <div style={s.memFooter}>
          <div style={s.footerRow}>
            <div style={s.footerActions}>
              <button onClick={exportMemory} style={s.actionBtn} title="Download memory as JSON">
                ⬇ Export
              </button>
              <button onClick={() => importRef.current?.click()} style={s.actionBtn} title="Import memory from JSON">
                ⬆ Import
              </button>
              <input ref={importRef} type="file" accept=".json" style={{ display:'none' }} onChange={handleImport} />
            </div>
            <span style={s.footerStats}>
              {hasMemory ? `${sections.length + projectSections.length} sec · ${wordCount}w` : 'Empty'}
            </span>
          </div>
          {activeConvId && (
            <div style={s.memToggleRow}>
              <span style={s.memToggleLabel}>Memory in this conversation</span>
              <button
                onClick={toggleConvMemory}
                disabled={memToggling}
                style={{
                  ...s.togglePill,
                  color:       convMemEnabled ? '#34d399' : '#475569',
                  borderColor: convMemEnabled ? '#1e4e3a' : '#334155',
                  opacity:     memToggling ? 0.5 : 1,
                }}
              >
                <span style={{ width:'7px', height:'7px', borderRadius:'50%',
                               background: convMemEnabled ? '#34d399' : '#475569', flexShrink:0 }} />
                {convMemEnabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
