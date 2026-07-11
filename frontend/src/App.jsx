import { useState } from 'react'
import Chat from './components/Chat'

const s = {
  page:  { display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' },
  box:   { background:'#0d131d', padding:'2rem', width:'340px', border:'1px solid #1d2a3a', borderRadius:'6px' },
  h2:    { marginBottom:'0.3rem', fontFamily:"'IBM Plex Mono',ui-monospace,monospace", fontWeight:600, fontSize:'13px', color:'#e9f1f9', letterSpacing:'0.16em', textTransform:'uppercase' },
  sub:   { marginBottom:'1.4rem', fontFamily:"'IBM Plex Mono',ui-monospace,monospace", fontSize:'9px', color:'#4d647e', letterSpacing:'0.12em', textTransform:'uppercase' },
  form:  { display:'flex', flexDirection:'column', gap:'0.8rem' },
  input: { padding:'0.6rem 0.85rem', border:'1px solid #2a4160', borderRadius:'3px', background:'#0a0f16', color:'#e9f1f9', fontSize:'14px', fontFamily:"'IBM Plex Sans',sans-serif", outline:'none' },
  btn:   { padding:'0.65rem', background:'rgba(242,163,60,0.12)', color:'#f2a33c', border:'1px solid #f2a33c', borderRadius:'3px', cursor:'pointer', fontWeight:600, fontSize:'11px', fontFamily:"'IBM Plex Mono',ui-monospace,monospace", letterSpacing:'0.12em', textTransform:'uppercase' },
  err:   { color:'#e5534b', fontSize:'13px' },
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
          <h2 style={s.h2}>NIM · Flight Ops</h2>
          <div style={s.sub}>AI gateway · routing console</div>
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
