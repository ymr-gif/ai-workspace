import { useState } from 'react'
import Chat from './components/Chat'

const s = {
  page:  { display:'flex', alignItems:'center', justifyContent:'center', height:'100vh' },
  box:   { background:'#0a0a0a', padding:'2rem', width:'340px', border:'1px solid #262626' },
  h2:    { marginBottom:'1.5rem', fontFamily:"'Silkscreen',monospace", fontWeight:700, fontSize:'16px', color:'#ffffff', letterSpacing:'0.08em', textTransform:'uppercase', textShadow:'2px 2px 0 #b81818' },
  form:  { display:'flex', flexDirection:'column', gap:'0.8rem' },
  input: { padding:'0.65rem 0.9rem', border:'1px solid #4a4a4a', background:'#000', color:'#ffffff', fontSize:'18px', fontFamily:"'VT323',monospace", outline:'none' },
  btn:   { padding:'0.75rem', background:'#ff2222', color:'#000', border:'none', cursor:'pointer', fontWeight:700, fontSize:'14px', fontFamily:"'Silkscreen',monospace", letterSpacing:'0.1em', textTransform:'uppercase' },
  err:   { color:'#ff2222', fontSize:'16px', fontFamily:"'VT323',monospace" },
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
          <h2 style={s.h2}>NIM // GATEWAY</h2>
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
