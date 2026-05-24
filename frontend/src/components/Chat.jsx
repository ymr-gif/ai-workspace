import { useState, useRef, useEffect, useCallback } from 'react'

const MODEL_LABELS = {
  'meta/llama-3.1-8b-instruct':    'Llama 3.1 8B · fast',
  'deepseek-ai/deepseek-v4-flash': 'DeepSeek V4 Flash · code',
  'meta/llama-3.3-70b-instruct':   'Llama 3.3 70B · reasoning',
}

const s = {
  root:      { display:'flex', height:'100vh', background:'#0f172a', color:'#f1f5f9', fontFamily:'system-ui,sans-serif' },

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
}

function fmtDate(iso) {
  const d = new Date(iso)
  const now = new Date()
  const diffH = (now - d) / 3600000
  if (diffH < 24) return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
  if (diffH < 168) return d.toLocaleDateString([], { weekday:'short' })
  return d.toLocaleDateString([], { month:'short', day:'numeric' })
}

export default function Chat({ token, onLogout }) {
  const [conversations, setConversations] = useState([])
  const [activeConvId,  setActiveConvId]  = useState(null)
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState('')
  const [loading,       setLoading]       = useState(false)
  const bottomRef = useRef(null)
  const nextId    = useRef(0)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  // load conversation list on mount
  useEffect(() => {
    fetch('/api/conversations', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(setConversations)
      .catch(() => {})
  }, [])

  // load messages when conversation changes
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

              // update conversation state
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

  return (
    <div style={s.root}>
      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>

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
          <button onClick={onLogout} style={s.logout}>Logout</button>
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
    </div>
  )
}
