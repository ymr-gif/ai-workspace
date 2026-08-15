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
  pwWrap:{ position:'relative', display:'flex', alignItems:'center' },
  eye:   { position:'absolute', right:'0.55rem', background:'none', border:'none', color:'#8ba3bd', cursor:'pointer', padding:'0.2rem', display:'flex', alignItems:'center', lineHeight:0 },
}

const nf = {
  page:   { display:'flex', alignItems:'center', justifyContent:'center', minHeight:'100vh', background:'#0a0b0d', padding:'24px', fontFamily:'ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo, Consolas, monospace' },
  card:   { maxWidth:'560px', width:'100%', background:'#121417', border:'1px solid #23262b', borderRadius:'8px', padding:'32px' },
  badge:  { display:'inline-block', fontSize:'12px', letterSpacing:'0.08em', textTransform:'uppercase', color:'#e0a640', border:'1px solid #e0a640', borderRadius:'3px', padding:'2px 8px', marginBottom:'20px' },
  h1:     { fontSize:'20px', lineHeight:1.5, fontWeight:500, margin:'0 0 8px', color:'#e6e8eb' },
  p:      { fontSize:'14px', lineHeight:1.6, color:'#8b9099', margin:'0 0 4px' },
  footer: { marginTop:'24px', paddingTop:'20px', borderTop:'1px solid #23262b', fontSize:'13px' },
  link:   { color:'#e0a640', textDecoration:'none' },
}

function NotFound() {
  return (
    <div style={nf.page}>
      <div style={nf.card}>
        <span style={nf.badge}>not found</span>
        <h1 style={nf.h1}>There&rsquo;s no page at this address.</h1>
        <p style={nf.p}>Eidetic is up and running &mdash; this path just doesn&rsquo;t lead anywhere.
          Check the link, or head back and start over.</p>
        <div style={nf.footer}>
          <a href="/" style={nf.link}>Back to Eidetic</a>
        </div>
      </div>
    </div>
  )
}

function EyeIcon({ off }) {
  return off ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  )
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('nim_token') || '')
  const [error, setError] = useState('')
  const [showPw, setShowPw] = useState(false)

  if (window.location.pathname !== '/') {
    return <NotFound />
  }

  async function handleLogin(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        body: new URLSearchParams({ username: fd.get('username'), password: fd.get('password') }),
      })
      if (!res.ok) {
        let detail = ''
        try { detail = (await res.json())?.detail || '' } catch { /* no JSON body */ }
        setError(res.status === 401 ? 'Invalid credentials' : (detail || 'Invalid credentials'))
        return
      }
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
          <h2 style={s.h2}>Eidetic</h2>
          <div style={s.sub}>AI memory platform · routing console</div>
          <form onSubmit={handleLogin} style={s.form}>
            <input name="username" placeholder="Username" required style={s.input}
                   autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="username" />
            <div style={s.pwWrap}>
              <input name="password" type={showPw ? 'text' : 'password'} placeholder="Password" required
                     autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="current-password"
                     style={{ ...s.input, width:'100%', boxSizing:'border-box', paddingRight:'2.4rem' }} />
              <button type="button" onClick={() => setShowPw(v => !v)} style={s.eye}
                      aria-label={showPw ? 'Hide password' : 'Show password'}
                      title={showPw ? 'Hide password' : 'Show password'}>
                <EyeIcon off={showPw} />
              </button>
            </div>
            {error && <p style={s.err}>{error}</p>}
            <button type="submit" style={s.btn}>Sign in</button>
          </form>
        </div>
      </div>
    )
  }

  return <Chat token={token} onLogout={handleLogout} />
}
