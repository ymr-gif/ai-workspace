import { useState, useRef, useEffect } from 'react'

const MODEL_LABELS = {
  'meta/llama-3.1-8b-instruct':    'Llama 3.1 8B · fast',
  'deepseek-ai/deepseek-v4-flash': 'DeepSeek V4 Flash · code',
  'meta/llama-3.3-70b-instruct':   'Llama 3.3 70B · reasoning',
}

const s = {
  page:    { display:'flex', flexDirection:'column', height:'100vh' },
  header:  { display:'flex', justifyContent:'space-between', alignItems:'center',
             padding:'0.9rem 1.5rem', background:'#1e293b', borderBottom:'1px solid #334155' },
  title:   { fontWeight:700, fontSize:'1rem' },
  logout:  { background:'none', border:'1px solid #475569', color:'#94a3b8',
             cursor:'pointer', padding:'0.3rem 0.75rem', borderRadius:'6px', fontSize:'0.875rem' },
  feed:    { flex:1, overflowY:'auto', padding:'1.5rem', display:'flex', flexDirection:'column', gap:'1rem' },
  hint:    { color:'#475569', textAlign:'center', marginTop:'5rem', fontSize:'0.9rem' },
  bubble:  { maxWidth:'72%', padding:'0.75rem 1rem', borderRadius:'12px', lineHeight:1.55 },
  user:    { alignSelf:'flex-end', background:'#6366f1' },
  ai:      { alignSelf:'flex-start', background:'#1e293b', border:'1px solid #334155' },
  err:     { alignSelf:'flex-start', background:'#450a0a', border:'1px solid #991b1b', color:'#fca5a5' },
  text:    { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' },
  tag:     { display:'block', marginTop:'0.35rem', fontSize:'0.7rem', color:'#64748b' },
  bar:     { display:'flex', gap:'0.6rem', padding:'1rem 1.5rem',
             borderTop:'1px solid #334155', background:'#1e293b' },
  input:   { flex:1, padding:'0.7rem 1rem', borderRadius:'8px', border:'1px solid #334155',
             background:'#0f172a', color:'#f1f5f9', fontSize:'1rem', outline:'none' },
  send:    { padding:'0.7rem 1.2rem', borderRadius:'8px', background:'#6366f1', color:'#fff',
             border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.95rem' },
}

export default function Chat({ token, onLogout }) {
  const [messages, setMessages] = useState([])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const bottomRef               = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }) }, [messages])

  async function send(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev => [...prev, { role:'user', text }])
    setLoading(true)

    try {
      const res  = await fetch('/api/chat', {
        method:'POST',
        headers:{ 'Content-Type':'application/json', 'Authorization':`Bearer ${token}` },
        body: JSON.stringify({ message: text }),
      })
      const data = await res.json()

      if (res.ok && data.success) {
        setMessages(prev => [...prev, { role:'ai', text:data.data.response, model:data.data.model }])
      } else if (res.status === 401) {
        onLogout()
      } else {
        setMessages(prev => [...prev, { role:'err', text: data.error?.message || 'Request failed' }])
      }
    } catch (err) {
      setMessages(prev => [...prev, { role:'err', text:`Network error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <header style={s.header}>
        <span style={s.title}>NIM AI Gateway</span>
        <button onClick={onLogout} style={s.logout}>Logout</button>
      </header>

      <div style={s.feed}>
        {messages.length === 0 && (
          <p style={s.hint}>Send a message — models route automatically based on your query.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} style={{ ...s.bubble, ...(m.role==='user' ? s.user : m.role==='err' ? s.err : s.ai) }}>
            <p style={s.text}>{m.text}</p>
            {m.model && <span style={s.tag}>{MODEL_LABELS[m.model] || m.model}</span>}
          </div>
        ))}
        {loading && <div style={{ ...s.bubble, ...s.ai }}><p style={s.text}>…</p></div>}
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
          Send
        </button>
      </form>
    </div>
  )
}
