import { useState } from 'react'
import Chat from './components/Chat.jsx'

const s = {
  page:  { display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' },
  box:   { background:'#1e293b', padding:'2rem', borderRadius:'12px', width:'340px' },
  h2:    { marginBottom:'1.5rem', fontWeight:700, fontSize:'1.2rem', color:'#f1f5f9' },
  form:  { display:'flex', flexDirection:'column', gap:'0.8rem' },
  input: { padding:'0.65rem 0.9rem', borderRadius:'8px', border:'1px solid #334155',
           background:'#0f172a', color:'#f1f5f9', fontSize:'1rem', outline:'none' },
  btn:   { padding:'0.75rem', borderRadius:'8px', background:'#6366f1', color:'#fff',
           border:'none', cursor:'pointer', fontWeight:600, fontSize:'1rem' },
  err:   { color:'#f87171', fontSize:'0.875rem' },
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('nim_token') || '')
  const [error, setError] = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        body: new URLSearchParams({ username: fd.get('username'), password: fd.get('password') }),
      })
      if (!res.ok) { setError('Invalid credentials'); return }
      const { access_token } = await res.json()
      localStorage.setItem('nim_token', access_token)
      setToken(access_token)
      setError('')
    } catch {
      setError('Could not reach the server')
    }
  }

  function handleLogout() {
    localStorage.removeItem('nim_token')
    setToken('')
  }

  if (!token) {
    return (
      <div style={s.page}>
        <div style={s.box}>
          <h2 style={s.h2}>NIM AI Gateway</h2>
          <form onSubmit={handleLogin} style={s.form}>
            <input name="username" placeholder="Username" required style={s.input} />
            <input name="password" type="password" placeholder="Password" required style={s.input} />
            {error && <p style={s.err}>{error}</p>}
            <button type="submit" style={s.btn}>Sign in</button>
          </form>
        </div>
      </div>
    )
  }

  return <Chat token={token} onLogout={handleLogout} />
}
