import { useState, useRef, useEffect, useCallback } from 'react'

const MODEL_KEYS = {
  llama:     'meta/llama-3.1-8b-instruct',
  coder:     'deepseek-ai/deepseek-v4-flash',
  reasoning: 'meta/llama-3.3-70b-instruct',
}
const MODEL_LABELS = {
  [MODEL_KEYS.llama]:     'LLaMA 3.1 8B',
  [MODEL_KEYS.coder]:     'DeepSeek V4',
  [MODEL_KEYS.reasoning]: 'LLaMA 3.3 70B',
}
const MODEL_SUBLABELS = {
  [MODEL_KEYS.llama]:     'fast',
  [MODEL_KEYS.coder]:     'code',
  [MODEL_KEYS.reasoning]: 'reasoning',
}
const COMPARE_MODELS = Object.values(MODEL_KEYS)

const SECTION_COLORS = {
  USER:'#818cf8', STACK:'#34d399', PROJECT:'#fbbf24', CORRECTIONS:'#f87171', PATTERNS:'#a78bfa',
  GOALS:'#38bdf8', ARCH:'#fb923c', STATUS:'#4ade80', PENDING:'#f472b6',
}

const s = {
  root:        { display:'flex', height:'100vh', background:'#0f172a', color:'#f1f5f9', fontFamily:'system-ui,sans-serif', position:'relative', overflow:'hidden' },
  sidebar:     { width:'240px', display:'flex', flexDirection:'column', borderRight:'1px solid #1e293b', flexShrink:0 },
  sideTop:     { padding:'1rem', borderBottom:'1px solid #1e293b' },
  newBtn:      { width:'100%', padding:'0.6rem', borderRadius:'8px', background:'#6366f1', color:'#fff', border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.875rem' },
  convList:    { flex:1, overflowY:'auto', padding:'0.5rem' },
  convItem:    { padding:'0.6rem 0.75rem', borderRadius:'8px', cursor:'pointer', marginBottom:'2px', fontSize:'0.8rem', lineHeight:1.4, position:'relative', display:'flex', justifyContent:'space-between', alignItems:'flex-start' },
  convMeta:    { flex:1, minWidth:0 },
  convTitle:   { display:'block', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', color:'#cbd5e1' },
  convDate:    { display:'block', fontSize:'0.7rem', color:'#475569', marginTop:'2px' },
  convDel:     { flexShrink:0, marginLeft:'4px', marginTop:'1px', background:'none', border:'none', cursor:'pointer', color:'#475569', fontSize:'0.85rem', lineHeight:1, padding:'2px 4px', borderRadius:'4px' },

  chat:        { flex:1, display:'flex', flexDirection:'column', minWidth:0 },
  header:      { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.9rem 1.5rem', background:'#1e293b', borderBottom:'1px solid #334155' },
  title:       { fontWeight:700, fontSize:'1rem' },
  headerRight: { display:'flex', gap:'0.5rem', alignItems:'center' },
  hdrBtn:      { background:'none', border:'1px solid #334155', color:'#94a3b8', cursor:'pointer', padding:'0.3rem 0.75rem', borderRadius:'6px', fontSize:'0.8rem', display:'flex', alignItems:'center', gap:'0.35rem' },
  memDot:      { width:'6px', height:'6px', borderRadius:'50%', background:'#818cf8' },
  logout:      { background:'none', border:'1px solid #475569', color:'#94a3b8', cursor:'pointer', padding:'0.3rem 0.75rem', borderRadius:'6px', fontSize:'0.875rem' },

  feed:        { flex:1, overflowY:'auto', padding:'1.5rem', display:'flex', flexDirection:'column', gap:'1rem' },
  hint:        { color:'#475569', textAlign:'center', marginTop:'5rem', fontSize:'0.9rem' },
  bubble:      { maxWidth:'72%', padding:'0.75rem 1rem', borderRadius:'12px', lineHeight:1.55 },
  userBubble:  { alignSelf:'flex-end', background:'#6366f1' },
  aiBubble:    { alignSelf:'flex-start', background:'#1e293b', border:'1px solid #334155' },
  errBubble:   { alignSelf:'flex-start', background:'#450a0a', border:'1px solid #991b1b', color:'#fca5a5' },
  text:        { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' },
  cursor:      { display:'inline-block', width:'2px', height:'1em', background:'#94a3b8', marginLeft:'2px', verticalAlign:'text-bottom', animation:'blink 1s step-end infinite' },
  tag:         { display:'block', marginTop:'0.35rem', fontSize:'0.7rem', color:'#64748b' },

  // compare
  compareRow:  { display:'flex', gap:'0.75rem', alignSelf:'stretch' },
  compareCard: { flex:1, minWidth:0, background:'#1e293b', border:'1px solid #334155', borderRadius:'12px', padding:'0.75rem 1rem' },
  cardHeader:  { fontSize:'0.7rem', color:'#64748b', marginBottom:'0.5rem', fontWeight:600, letterSpacing:'0.04em' },
  cardModel:   { fontSize:'0.65rem', color:'#475569', marginTop:'0.35rem' },

  // toolbar
  toolbarWrap: { background:'#1e293b', borderTop:'1px solid #1e293b', padding:'0.5rem 1.5rem 0' },
  toolbar:     { display:'flex', justifyContent:'space-between', alignItems:'center', gap:'0.5rem' },
  modelPills:  { display:'flex', gap:'0.25rem', flexWrap:'wrap' },
  pill:        { padding:'0.25rem 0.65rem', borderRadius:'20px', border:'1px solid #334155', background:'none', color:'#64748b', cursor:'pointer', fontSize:'0.75rem', transition:'all 0.12s' },
  pillActive:  { background:'#6366f1', borderColor:'#6366f1', color:'#fff' },
  pillCompare: { background:'#0f4c3a', borderColor:'#34d399', color:'#34d399' },
  toolRight:   { display:'flex', gap:'0.25rem' },

  // params expander
  paramsBar:   { display:'flex', gap:'1.5rem', padding:'0.5rem 0', marginTop:'0.35rem', borderTop:'1px solid #1e293b' },
  paramItem:   { display:'flex', alignItems:'center', gap:'0.4rem', flex:1, minWidth:0 },
  paramLabel:  { fontSize:'0.7rem', minWidth:'34px', flexShrink:0 },
  paramVal:    { fontSize:'0.7rem', minWidth:'36px', textAlign:'right', flexShrink:0 },

  // input bar
  bar:         { display:'flex', gap:'0.6rem', padding:'0.75rem 1.5rem 1rem', background:'#1e293b' },
  input:       { flex:1, padding:'0.7rem 1rem', borderRadius:'8px', border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:'1rem', outline:'none' },
  send:        { padding:'0.7rem 1.2rem', borderRadius:'8px', background:'#6366f1', color:'#fff', border:'none', cursor:'pointer', fontWeight:600, fontSize:'0.95rem' },

  // overlay + panels
  overlay:     { position:'absolute', inset:0, background:'rgba(0,0,0,0.45)', zIndex:10 },
  memPanel:    { position:'absolute', top:0, right:0, bottom:0, width:'380px', maxWidth:'90vw', background:'#0f172a', borderLeft:'1px solid #1e293b', zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.28s cubic-bezier(.4,0,.2,1)' },
  memHeader:   { padding:'1rem 1.25rem 0.75rem', borderBottom:'1px solid #1e293b', flexShrink:0 },
  memTitleRow: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.25rem' },
  memTitle:    { fontWeight:700, fontSize:'0.95rem', color:'#e2e8f0', display:'flex', alignItems:'center', gap:'0.5rem' },
  memMeta:     { fontSize:'0.7rem', color:'#475569' },
  memHdrBtns:  { display:'flex', gap:'0.4rem', alignItems:'center' },
  refreshBtn:  { background:'none', border:'1px solid #1e293b', color:'#64748b', cursor:'pointer', fontSize:'0.75rem', padding:'0.2rem 0.5rem', borderRadius:'4px' },
  closeBtn:    { background:'none', border:'none', color:'#64748b', cursor:'pointer', fontSize:'1.1rem', padding:'0.25rem', lineHeight:1 },
  tabBar:      { display:'flex', borderBottom:'1px solid #1e293b', flexShrink:0 },
  tabBtn:      { flex:1, padding:'0.5rem', background:'none', border:'none', cursor:'pointer', fontSize:'0.78rem', color:'#475569', borderBottom:'2px solid transparent' },
  tabActive:   { color:'#818cf8', borderBottomColor:'#818cf8' },
  memBody:     { flex:1, overflowY:'auto', padding:'1rem 1.25rem' },
  emptyMem:    { color:'#475569', fontSize:'0.85rem', textAlign:'center', marginTop:'3rem' },
  section:     { marginBottom:'1.25rem' },
  secLabel:    { fontSize:'0.7rem', fontWeight:700, letterSpacing:'0.08em', marginBottom:'0.4rem', padding:'0.2rem 0.5rem', borderRadius:'4px', display:'inline-block' },
  kv:          { display:'flex', gap:'0.5rem', fontSize:'0.82rem', lineHeight:1.5, padding:'0.15rem 0', borderBottom:'1px solid #1e293b' },
  kvKey:       { color:'#64748b', minWidth:'90px', flexShrink:0 },
  kvVal:       { color:'#cbd5e1', wordBreak:'break-word', flex:1 },
  divider:     { borderTop:'1px solid #1e293b', margin:'1rem 0 0.75rem', display:'flex', alignItems:'center', gap:'0.5rem' },
  divLabel:    { fontSize:'0.65rem', fontWeight:700, letterSpacing:'0.1em', color:'#334155', whiteSpace:'nowrap' },
  memFooter:   { padding:'0.75rem 1.25rem', borderTop:'1px solid #1e293b', flexShrink:0, display:'flex', flexDirection:'column', gap:'0.5rem' },
  footerRow:   { display:'flex', justifyContent:'space-between', alignItems:'center' },
  footerActions: { display:'flex', gap:'0.4rem' },
  actionBtn:   { background:'none', border:'1px solid #1e293b', color:'#64748b', cursor:'pointer', fontSize:'0.72rem', padding:'0.2rem 0.5rem', borderRadius:'4px' },
  footerStats: { fontSize:'0.7rem', color:'#334155' },
  memToggleRow:   { display:'flex', alignItems:'center', justifyContent:'space-between', paddingTop:'0.35rem', borderTop:'1px solid #0f172a' },
  memToggleLabel: { fontSize:'0.72rem', color:'#475569' },
  togglePill:     { display:'flex', alignItems:'center', gap:'0.35rem', background:'none', border:'1px solid #334155', borderRadius:'12px', padding:'0.2rem 0.6rem', cursor:'pointer', fontSize:'0.72rem' },
  editArea:    { width:'100%', background:'#0a1220', border:'1px solid #1e293b', borderRadius:'6px', color:'#cbd5e1', fontSize:'0.8rem', lineHeight:1.6, padding:'0.6rem', resize:'vertical', outline:'none', fontFamily:'monospace', boxSizing:'border-box' },
  editLabel:   { fontSize:'0.7rem', color:'#475569', marginBottom:'0.3rem', marginTop:'0.75rem' },
  editBtns:    { display:'flex', gap:'0.5rem', marginTop:'1rem' },
  saveBtn:     { padding:'0.4rem 1rem', borderRadius:'6px', background:'#6366f1', color:'#fff', border:'none', cursor:'pointer', fontSize:'0.82rem', fontWeight:600 },
  cancelBtn:   { padding:'0.4rem 0.75rem', borderRadius:'6px', background:'none', color:'#64748b', border:'1px solid #334155', cursor:'pointer', fontSize:'0.82rem' },
  historyList: { display:'flex', flexDirection:'column', gap:'0.5rem' },
  historyItem: { padding:'0.5rem 0.75rem', borderRadius:'6px', border:'1px solid #1e293b', cursor:'pointer', fontSize:'0.8rem', background:'#0a1220' },
  historyMeta: { color:'#475569', fontSize:'0.7rem', marginTop:'0.2rem' },
  diffBox:     { marginTop:'1rem', padding:'0.75rem', background:'#0a1220', borderRadius:'6px', border:'1px solid #1e293b' },
  diffTitle:   { fontSize:'0.7rem', color:'#64748b', marginBottom:'0.5rem', fontWeight:600 },
  diffLine:    { fontSize:'0.78rem', lineHeight:1.6, padding:'0.05rem 0.4rem', borderRadius:'3px', marginBottom:'1px', fontFamily:'monospace', wordBreak:'break-word' },
  diffAdded:   { background:'rgba(52,211,153,0.12)', color:'#34d399' },
  diffRemoved: { background:'rgba(248,113,113,0.12)', color:'#f87171' },
  diffSame:    { color:'#475569' },
  updatingDot: { width:'6px', height:'6px', borderRadius:'50%', background:'#34d399', animation:'pulse 1s ease-in-out infinite' },
  flashBody:   { animation:'memFlash 1.5s ease-out' },

  // settings modal
  settingsModal:  { position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)', width:'440px', maxWidth:'92vw', background:'#0f172a', border:'1px solid #1e293b', borderRadius:'12px', zIndex:20, display:'flex', flexDirection:'column' },
  settingsHeader: { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'1rem 1.25rem', borderBottom:'1px solid #1e293b' },
  settingsTitle:  { fontWeight:700, fontSize:'0.9rem', color:'#e2e8f0' },
  settingsBody:   { padding:'1.25rem', overflowY:'auto' },
  settingsFooter: { display:'flex', justifyContent:'flex-end', gap:'0.5rem', padding:'0.75rem 1.25rem', borderTop:'1px solid #1e293b' },

  // files panel
  filePanel:     { position:'absolute', top:0, right:0, bottom:0, width:'400px', maxWidth:'92vw', background:'#0f172a', borderLeft:'1px solid #1e293b', zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.28s cubic-bezier(.4,0,.2,1)' },
  filePanelHdr:  { padding:'1rem 1.25rem 0.75rem', borderBottom:'1px solid #1e293b', flexShrink:0 },
  fileTitleRow:  { display:'flex', justifyContent:'space-between', alignItems:'center' },
  fileTitle:     { fontWeight:700, fontSize:'0.95rem', color:'#e2e8f0' },
  fileUploadRow: { display:'flex', gap:'0.4rem', padding:'0.75rem 1.25rem', borderBottom:'1px solid #1e293b', flexShrink:0, flexWrap:'wrap' },
  urlRow:        { display:'flex', gap:'0.4rem', padding:'0 1.25rem 0.75rem', borderBottom:'1px solid #1e293b', flexShrink:0 },
  urlInput:      { flex:1, padding:'0.3rem 0.6rem', borderRadius:'6px', border:'1px solid #334155', background:'#0f172a', color:'#f1f5f9', fontSize:'0.78rem', outline:'none' },
  ingestBtn:     { padding:'0.3rem 0.75rem', borderRadius:'6px', background:'#0f4c3a', color:'#34d399', border:'1px solid #1e4e3a', cursor:'pointer', fontSize:'0.75rem', fontWeight:600, whiteSpace:'nowrap' },
  wsRow:         { display:'flex', gap:'0.3rem', padding:'0.5rem 1.25rem', borderBottom:'1px solid #1e293b', flexShrink:0, flexWrap:'wrap', alignItems:'center' },
  wsLabel:       { fontSize:'0.7rem', color:'#475569', marginRight:'0.15rem' },
  wsPill:        { padding:'0.15rem 0.5rem', borderRadius:'12px', border:'1px solid #334155', background:'none', color:'#64748b', cursor:'pointer', fontSize:'0.7rem' },
  wsPillActive:  { background:'#1e293b', borderColor:'#6366f1', color:'#818cf8' },
  fileList:      { flex:1, overflowY:'auto', padding:'0.5rem 1.25rem' },
  fileItem:      { display:'flex', alignItems:'center', gap:'0.5rem', padding:'0.5rem 0.6rem', borderRadius:'6px', marginBottom:'4px', border:'1px solid #1e293b', background:'#0a1220' },
  fileName:      { flex:1, minWidth:0, fontSize:'0.78rem', color:'#cbd5e1', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' },
  fileMeta:      { fontSize:'0.65rem', color:'#475569', whiteSpace:'nowrap' },
  statusBadge:   { fontSize:'0.62rem', padding:'0.1rem 0.35rem', borderRadius:'4px', fontWeight:600, whiteSpace:'nowrap' },
  attachBtn:     { padding:'0.15rem 0.4rem', borderRadius:'4px', border:'1px solid #334155', background:'none', cursor:'pointer', fontSize:'0.7rem', color:'#64748b', whiteSpace:'nowrap' },
  attachedBtn:   { background:'#1e293b', borderColor:'#6366f1', color:'#818cf8' },
  delBtn:        { padding:'0.15rem 0.3rem', borderRadius:'4px', border:'1px solid #334155', background:'none', cursor:'pointer', fontSize:'0.7rem', color:'#ef4444' },
  fileChipsRow:  { display:'flex', gap:'0.35rem', padding:'0 1.5rem 0.35rem', flexWrap:'wrap' },
  fileChip:      { display:'flex', alignItems:'center', gap:'0.3rem', padding:'0.2rem 0.5rem', borderRadius:'12px', background:'#1e293b', border:'1px solid #334155', fontSize:'0.72rem', color:'#818cf8' },
  chipX:         { cursor:'pointer', color:'#475569', fontSize:'0.8rem', lineHeight:1 },
}

function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso), now = new Date(), diffH = (now - d) / 3600000
  if (diffH < 24)  return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
  if (diffH < 168) return d.toLocaleDateString([], { weekday:'short', hour:'2-digit', minute:'2-digit' })
  return d.toLocaleDateString([], { month:'short', day:'numeric' })
}

function parseMemory(content) {
  if (!content) return []
  const sections = []; let current = null
  for (const raw of content.split('\n')) {
    const line = raw.trim(); if (!line) continue
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
  const ol = (oldText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const nl = (newText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const os = new Set(ol), ns = new Set(nl), result = []
  for (const l of nl) result.push({ type: os.has(l) ? 'same' : 'added',   line: l })
  for (const l of ol) if (!ns.has(l)) result.push({ type: 'removed', line: l })
  return result
}

function ParamSlider({ label, enabled, onToggle, value, onChange, min, max, step, fmt }) {
  return (
    <div style={s.paramItem}>
      <input type="checkbox" checked={enabled} onChange={e => onToggle(e.target.checked)} style={{ accentColor:'#6366f1', cursor:'pointer' }} />
      <span style={{ ...s.paramLabel, color: enabled ? '#94a3b8' : '#475569' }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={!enabled}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex:1, accentColor:'#6366f1', cursor: enabled ? 'pointer' : 'default' }} />
      <span style={{ ...s.paramVal, color: enabled ? '#94a3b8' : '#334155' }}>
        {fmt ? fmt(value) : value}
      </span>
    </div>
  )
}

export default function Chat({ token, onLogout }) {
  const [conversations,  setConversations]  = useState([])
  const [activeConvId,   setActiveConvId]   = useState(null)
  const [messages,       setMessages]       = useState([])
  const [input,          setInput]          = useState('')
  const [loading,        setLoading]        = useState(false)

  // memory panel
  const [memOpen,        setMemOpen]        = useState(false)
  const [memTab,         setMemTab]         = useState('view')
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

  // conversation settings
  const [convMemEnabled, setConvMemEnabled] = useState(true)
  const [memToggling,    setMemToggling]    = useState(false)
  const [settingsOpen,   setSettingsOpen]   = useState(false)
  const [editSysPrompt,  setEditSysPrompt]  = useState('')
  const [editLockModel,  setEditLockModel]  = useState('')
  const [convSysPrompt,  setConvSysPrompt]  = useState('')
  const [convLockModel,  setConvLockModel]  = useState('')
  const [settingsSaving, setSettingsSaving] = useState(false)

  // model control toolbar
  const [selectedModel,  setSelectedModel]  = useState('auto')
  const [compareMode,    setCompareMode]    = useState(false)
  const [paramsOpen,     setParamsOpen]     = useState(false)
  const [tempEnabled,    setTempEnabled]    = useState(false)
  const [temperature,    setTemperature]    = useState(0.7)
  const [tokensEnabled,  setTokensEnabled]  = useState(false)
  const [maxTokens,      setMaxTokens]      = useState(1024)
  const [topPEnabled,    setTopPEnabled]    = useState(false)
  const [topP,           setTopP]           = useState(0.9)

  // files panel
  const [filesOpen,      setFilesOpen]      = useState(false)
  const [filesTab,       setFilesTab]       = useState('library')
  const [libFiles,       setLibFiles]       = useState([])
  const [attachedFiles,  setAttachedFiles]  = useState([])
  const [workspaces,     setWorkspaces]     = useState([])
  const [wsFilter,       setWsFilter]       = useState('')
  const [fileUploading,  setFileUploading]  = useState(false)
  const [urlIngest,      setUrlIngest]      = useState('')
  const [urlIngesting,   setUrlIngesting]   = useState(false)
  const fileInputRef = useRef(null)

  const bottomRef  = useRef(null)
  const nextId     = useRef(0)
  const prevMemSig = useRef('')
  const importRef  = useRef(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    fetch('/api/conversations', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(setConversations).catch(() => {})
  }, [])

  useEffect(() => {
    if (!activeConvId) return
    fetch(`/api/conversations/${activeConvId}/messages`, { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(msgs => setMessages(msgs.map(m => ({ id: nextId.current++, role: m.role === 'assistant' ? 'ai' : 'user', text: m.content, model: m.model, streaming: false }))))
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
        prevMemSig.current = sig; setMemData(data); setMemFlashed(true)
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
    setMemPending(true); let count = 0
    const id = setInterval(() => { pollMemory(); if (++count >= 15) { clearInterval(id); setMemPending(false) } }, 2000)
    return () => { clearInterval(id); setMemPending(false) }
  }, [memTick])

  useEffect(() => {
    if (memTab !== 'history') return
    setHistLoading(true)
    fetch('/api/memory/history', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(h => { setMemHistory(h); setDiffIdx(null) }).catch(() => {})
      .finally(() => setHistLoading(false))
  }, [memTab])

  function newChat() { setActiveConvId(null); setMessages([]); setInput(''); setConvMemEnabled(true); setConvSysPrompt(''); setConvLockModel('') }

  async function deleteConv(e, id) {
    e.stopPropagation()
    if (!window.confirm('Delete this conversation?')) return
    await fetch(`/api/conversations/${id}`, { method:'DELETE', headers: authHeaders })
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConvId === id) newChat()
  }

  function selectConv(id) {
    if (id === activeConvId) return
    setActiveConvId(id); setMessages([])
    const c = conversations.find(x => x.id === id)
    setConvMemEnabled(c?.memory_enabled !== false)
    setConvSysPrompt(c?.system_prompt || ''); setEditSysPrompt(c?.system_prompt || '')
    setConvLockModel(c?.locked_model  || ''); setEditLockModel(c?.locked_model  || '')
  }

  async function toggleConvMemory() {
    if (!activeConvId || memToggling) return
    const next = !convMemEnabled; setMemToggling(true)
    try {
      await fetch(`/api/conversations/${activeConvId}`, { method:'PATCH', headers:{...authHeaders,'Content-Type':'application/json'}, body: JSON.stringify({ memory_enabled: next }) })
      setConvMemEnabled(next)
      setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, memory_enabled: next } : c))
    } catch { /* ignore */ } finally { setMemToggling(false) }
  }

  async function saveSettings() {
    if (!activeConvId) return; setSettingsSaving(true)
    try {
      const r = await fetch(`/api/conversations/${activeConvId}`, {
        method: 'PATCH', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: editSysPrompt || null, locked_model: editLockModel || null }),
      })
      if (!r.ok) return
      const data = await r.json()
      setConvSysPrompt(data.system_prompt); setConvLockModel(data.locked_model)
      setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, system_prompt: data.system_prompt, locked_model: data.locked_model } : c))
      setSettingsOpen(false)
    } catch { /* ignore */ } finally { setSettingsSaving(false) }
  }

  // memory panel
  function openEdit() { setEditContent(memData?.content || ''); setEditProj(memData?.project_summary || ''); setMemTab('edit') }
  function cancelEdit() { setMemTab('view') }
  async function saveEdit() {
    setMemSaving(true)
    try {
      const r = await fetch('/api/memory', { method:'PUT', headers:{...authHeaders,'Content-Type':'application/json'}, body: JSON.stringify({ content: editContent, project_summary: editProj }) })
      if (!r.ok) return
      const data = await r.json(); setMemData(data); prevMemSig.current = (data.content||'')+'|'+(data.project_summary||''); setMemFlashed(true); setTimeout(()=>setMemFlashed(false),1800); setMemTab('view')
    } catch { /* ignore */ } finally { setMemSaving(false) }
  }
  async function exportMemory() {
    try { const r = await fetch('/api/memory/export',{headers:authHeaders}); if(!r.ok) return; const blob=await r.blob(); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download='memory.json'; a.click(); URL.revokeObjectURL(url) } catch{/* ignore */}
  }
  async function handleImport(e) {
    const file=e.target.files?.[0]; if(!file) return
    try { const json=JSON.parse(await file.text()); const r=await fetch('/api/memory/import',{method:'POST',headers:{...authHeaders,'Content-Type':'application/json'},body:JSON.stringify({content:json.content||'',project_summary:json.project_summary||''})}); if(!r.ok) return; const data=await r.json(); setMemData(data); prevMemSig.current=(data.content||'')+'|'+(data.project_summary||''); setMemFlashed(true); setTimeout(()=>setMemFlashed(false),1800) } catch{/* ignore */}
    e.target.value=''
  }

  // files
  const loadLibFiles = useCallback(async () => {
    const qs = wsFilter ? `?workspace_id=${encodeURIComponent(wsFilter)}` : ''
    try {
      const r = await fetch(`/api/files${qs}`, { headers: authHeaders })
      if (r.ok) setLibFiles(await r.json())
    } catch { /* ignore */ }
  }, [token, wsFilter])

  const loadWorkspaces = useCallback(async () => {
    try {
      const r = await fetch('/api/files/workspaces', { headers: authHeaders })
      if (r.ok) { const d = await r.json(); setWorkspaces(d.workspaces || []) }
    } catch { /* ignore */ }
  }, [token])

  const loadAttachedFiles = useCallback(async () => {
    if (!activeConvId) { setAttachedFiles([]); return }
    try {
      const r = await fetch(`/api/conversations/${activeConvId}/files`, { headers: authHeaders })
      if (r.ok) setAttachedFiles(await r.json())
    } catch { /* ignore */ }
  }, [token, activeConvId])

  useEffect(() => {
    if (!filesOpen) return
    loadLibFiles(); loadWorkspaces(); loadAttachedFiles()
  }, [filesOpen, wsFilter])

  useEffect(() => { if (activeConvId) loadAttachedFiles() }, [activeConvId])

  async function uploadFile(e) {
    const file = e.target.files?.[0]; if (!file) return
    setFileUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await fetch('/api/files/upload', { method:'POST', headers: authHeaders, body: fd })
      if (r.ok) { await loadLibFiles(); await loadWorkspaces() }
    } catch { /* ignore */ } finally { setFileUploading(false); e.target.value = '' }
  }

  async function ingestUrl() {
    const url = urlIngest.trim(); if (!url) return
    setUrlIngesting(true)
    try {
      const r = await fetch('/api/files/ingest-url', { method:'POST', headers:{...authHeaders,'Content-Type':'application/json'}, body:JSON.stringify({url}) })
      if (r.ok) { setUrlIngest(''); await loadLibFiles() }
    } catch { /* ignore */ } finally { setUrlIngesting(false) }
  }

  async function attachFile(fileId) {
    if (!activeConvId) return
    try {
      await fetch(`/api/conversations/${activeConvId}/files`, { method:'POST', headers:{...authHeaders,'Content-Type':'application/json'}, body:JSON.stringify({file_id:fileId}) })
      await loadAttachedFiles()
    } catch { /* ignore */ }
  }

  async function detachFile(fileId) {
    if (!activeConvId) return
    try {
      await fetch(`/api/conversations/${activeConvId}/files/${fileId}`, { method:'DELETE', headers: authHeaders })
      await loadAttachedFiles()
    } catch { /* ignore */ }
  }

  async function deleteFile(fileId) {
    try {
      await fetch(`/api/files/${fileId}`, { method:'DELETE', headers: authHeaders })
      setAttachedFiles(prev => prev.filter(f => f.id !== fileId))
      await loadLibFiles()
    } catch { /* ignore */ }
  }

  const attachedIds = new Set(attachedFiles.map(f => f.id))

  function statusColor(s) {
    if (s === 'ready')      return { bg:'rgba(52,211,153,0.15)', color:'#34d399' }
    if (s === 'processing') return { bg:'rgba(251,191,36,0.15)',  color:'#fbbf24' }
    if (s === 'error')      return { bg:'rgba(248,113,113,0.15)', color:'#f87171' }
    return { bg:'rgba(100,116,139,0.15)', color:'#64748b' }
  }

  // build request body
  function buildBody(text) {
    const body = { message: text, conversation_id: activeConvId }
    if (selectedModel !== 'auto') body.model_override = selectedModel  // short key
    if (compareMode) body.compare = true
    if (tempEnabled)   body.temperature = temperature
    if (tokensEnabled) body.max_tokens  = maxTokens
    if (topPEnabled)   body.top_p       = topP
    return body
  }

  async function send(e) {
    e.preventDefault()
    const text = input.trim(); if (!text || loading) return
    const isCompare = compareMode
    const userId = nextId.current++, aiId = nextId.current++
    setInput(''); setLoading(true)

    if (isCompare) {
      setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'compare', responses: Object.fromEntries(COMPARE_MODELS.map(m => [m, { text: '', streaming: true }])) },
      ])
    } else {
      setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'ai', text: '', model: null, streaming: true },
      ])
    }

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(text)),
      })
      if (res.status === 401) { onLogout(); return }
      if (!res.ok) {
        setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: 'Request failed', streaming: false } : m))
        return
      }

      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n'); buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim(); if (!raw) continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              if (isCompare) {
                const model = event.model
                setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: { ...m.responses, [model]: { ...m.responses[model], text: (m.responses[model]?.text||'') + event.content } } }
                  : m))
              } else {
                setMessages(prev => prev.map(m => m.id === aiId ? { ...m, text: m.text + event.content } : m))
              }
            } else if (event.type === 'done') {
              if (isCompare) {
                setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: Object.fromEntries(Object.entries(m.responses).map(([k,v]) => [k, { ...v, streaming: false }])) }
                  : m))
              } else {
                setMessages(prev => prev.map(m => m.id === aiId ? { ...m, model: event.model, streaming: false } : m))
                setMemTick(t => t + 1)
              }
              const cid = event.conversation_id
              if (cid) {
                setActiveConvId(cid)
                setConversations(prev => {
                  const exists = prev.find(c => c.id === cid)
                  if (exists) return [{ ...exists, updated_at: new Date().toISOString() }, ...prev.filter(c => c.id !== cid)]
                  return [{ id: cid, title: text.slice(0, 60), updated_at: new Date().toISOString(), memory_enabled: true, system_prompt: '', locked_model: '' }, ...prev]
                })
              }
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: event.message || 'Error', streaming: false } : m))
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err) {
      setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: `Network error: ${err.message}`, streaming: false } : m))
    } finally { setLoading(false) }
  }

  // memory panel derived
  const sections        = parseMemory(memData?.content)
  const projectSections = parseMemory(memData?.project_summary)
  const hasMemory       = memData?.content?.trim() || memData?.project_summary?.trim()
  const panelSlide      = memOpen ? 'translateX(0)' : 'translateX(100%)'
  const wordCount       = hasMemory ? ((memData.content||'')+' '+(memData.project_summary||'')).split(/\s+/).filter(Boolean).length : 0
  const diffTarget      = diffIdx !== null ? memHistory[diffIdx] : null
  const diffLines       = diffTarget ? computeDiff((diffTarget.content||'')+'\n'+(diffTarget.project_summary||''), (memData?.content||'')+'\n'+(memData?.project_summary||'')) : []

  const lockedModelLabel = convLockModel
    ? (MODEL_LABELS[convLockModel] || convLockModel)
    : null

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
        input[type=range] { height:4px }
      `}</style>

      {/* sidebar */}
      <div style={s.sidebar}>
        <div style={s.sideTop}><button onClick={newChat} style={s.newBtn}>+ New Chat</button></div>
        <div style={s.convList}>
          {conversations.map(c => (
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
              <button onClick={e => deleteConv(e, c.id)} style={s.convDel} title="Delete conversation">✕</button>
            </div>
          ))}
        </div>
      </div>

      {/* chat */}
      <div style={s.chat}>
        <header style={s.header}>
          <span style={s.title}>
            NIM AI Gateway
            {lockedModelLabel && <span style={{ fontSize:'0.72rem', color:'#6366f1', marginLeft:'0.5rem', fontWeight:400 }}>🔒 {lockedModelLabel}</span>}
          </span>
          <div style={s.headerRight}>
            {activeConvId && (
              <button onClick={toggleConvMemory} disabled={memToggling} title={convMemEnabled ? 'Context ON' : 'Context OFF'}
                style={{ ...s.hdrBtn, color: convMemEnabled ? '#34d399' : '#475569', borderColor: convMemEnabled ? '#1e4e3a' : '#334155' }}>
                {convMemEnabled ? '◉' : '○'} Ctx
              </button>
            )}
            {activeConvId && (
              <button onClick={() => setSettingsOpen(true)} style={s.hdrBtn} title="Conversation settings">⚙</button>
            )}
            <button onClick={() => { setFilesOpen(true); setMemOpen(false) }} style={{ ...s.hdrBtn, ...(attachedFiles.length > 0 ? { color:'#fbbf24', borderColor:'#78350f' } : {}) }}>
              {attachedFiles.length > 0 ? `📎 ${attachedFiles.length}` : '📎'} Files
            </button>
            <button onClick={() => { setMemOpen(true); setFilesOpen(false) }} style={s.hdrBtn}>
              {memPending ? <span style={s.updatingDot} /> : hasMemory && <span style={s.memDot} />}
              Memory
            </button>
            <button onClick={onLogout} style={s.logout}>Logout</button>
          </div>
        </header>

        <div style={s.feed}>
          {messages.length === 0 && <p style={s.hint}>{activeConvId ? 'Loading…' : 'Send a message to start.'}</p>}
          {messages.map(m => {
            if (m.role === 'compare') {
              return (
                <div key={m.id} style={s.compareRow}>
                  {COMPARE_MODELS.map(model => {
                    const resp = m.responses[model] || { text: '', streaming: false }
                    return (
                      <div key={model} style={s.compareCard}>
                        <div style={s.cardHeader}>{MODEL_LABELS[model]}</div>
                        <p style={s.text}>
                          {resp.text || <span style={{ color:'#334155' }}>…</span>}
                          {resp.streaming && <span style={s.cursor} />}
                        </p>
                        <span style={s.cardModel}>{MODEL_SUBLABELS[model]}</span>
                      </div>
                    )
                  })}
                </div>
              )
            }
            return (
              <div key={m.id} style={{ ...s.bubble, ...(m.role === 'user' ? s.userBubble : m.role === 'err' ? s.errBubble : s.aiBubble) }}>
                <p style={s.text}>{m.text}{m.streaming && <span style={s.cursor} />}</p>
                {m.model && !m.streaming && <span style={s.tag}>{MODEL_LABELS[m.model] || m.model} · {MODEL_SUBLABELS[m.model] || ''}</span>}
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        {/* model toolbar */}
        <div style={s.toolbarWrap}>
          <div style={s.toolbar}>
            <div style={s.modelPills}>
              {[['auto', 'Auto'], ['llama', 'LLaMA 8B'], ['coder', 'DeepSeek'], ['reasoning', '70B']].map(([key, label]) => (
                <button key={key} onClick={() => setSelectedModel(key)}
                  style={{ ...s.pill, ...(selectedModel === key ? s.pillActive : {}) }}>
                  {label}
                </button>
              ))}
            </div>
            <div style={s.toolRight}>
              <button onClick={() => setCompareMode(!compareMode)}
                style={{ ...s.pill, ...(compareMode ? s.pillCompare : {}) }}
                title="Run same prompt on all 3 models side by side">
                ⊞ Compare
              </button>
              <button onClick={() => setParamsOpen(!paramsOpen)}
                style={{ ...s.pill, ...(paramsOpen ? s.pillActive : {}) }}
                title="Temperature / max tokens / top-p">
                ⚙
              </button>
            </div>
          </div>

          {paramsOpen && (
            <div style={s.paramsBar}>
              <ParamSlider label="Temp" enabled={tempEnabled} onToggle={setTempEnabled}
                value={temperature} onChange={setTemperature} min={0} max={2} step={0.05}
                fmt={v => v.toFixed(2)} />
              <ParamSlider label="Tokens" enabled={tokensEnabled} onToggle={setTokensEnabled}
                value={maxTokens} onChange={setMaxTokens} min={256} max={4096} step={256}
                fmt={v => v} />
              <ParamSlider label="Top-p" enabled={topPEnabled} onToggle={setTopPEnabled}
                value={topP} onChange={setTopP} min={0} max={1} step={0.05}
                fmt={v => v.toFixed(2)} />
            </div>
          )}
        </div>

        {attachedFiles.length > 0 && (
          <div style={s.fileChipsRow}>
            {attachedFiles.map(f => (
              <span key={f.id} style={s.fileChip}>
                📄 {f.filename.length > 24 ? f.filename.slice(0,22)+'…' : f.filename}
                <span style={s.chipX} onClick={() => detachFile(f.id)} title="Detach">✕</span>
              </span>
            ))}
          </div>
        )}

        <form onSubmit={send} style={s.bar}>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder={compareMode ? 'Compare prompt across all models…' : 'Ask anything…'} disabled={loading} style={s.input} />
          <button type="submit" disabled={loading || !input.trim()} style={{ ...s.send, ...(compareMode ? { background:'#065f46' } : {}) }}>
            {loading ? '…' : compareMode ? '⊞' : 'Send'}
          </button>
        </form>
      </div>

      {/* overlays */}
      {(memOpen || filesOpen || settingsOpen) && (
        <div style={{ ...s.overlay, zIndex: settingsOpen ? 19 : 10 }}
          onClick={() => { if (settingsOpen) setSettingsOpen(false); else { setMemOpen(false); setFilesOpen(false) } }} />
      )}

      {/* settings modal */}
      {settingsOpen && (
        <div style={s.settingsModal} onClick={e => e.stopPropagation()}>
          <div style={s.settingsHeader}>
            <span style={s.settingsTitle}>⚙ Conversation Settings</span>
            <button onClick={() => setSettingsOpen(false)} style={s.closeBtn}>✕</button>
          </div>
          <div style={s.settingsBody}>
            <div style={{ ...s.editLabel, marginTop:0 }}>System Prompt</div>
            <textarea value={editSysPrompt} onChange={e => setEditSysPrompt(e.target.value)}
              rows={5} style={s.editArea} placeholder="You are a helpful assistant specializing in…" />
            <div style={{ ...s.editLabel, marginTop:'1rem' }}>Model Lock</div>
            <div style={{ ...s.modelPills, marginTop:'0.4rem', flexWrap:'wrap' }}>
              {[['', 'Auto (route)'], ['llama', 'LLaMA 8B'], ['coder', 'DeepSeek'], ['reasoning', '70B Reasoning']].map(([key, label]) => (
                <button key={key} onClick={() => setEditLockModel(key)}
                  style={{ ...s.pill, ...(editLockModel === key ? s.pillActive : {}) }}>
                  {label}
                </button>
              ))}
            </div>
            {editLockModel && <div style={{ fontSize:'0.7rem', color:'#475569', marginTop:'0.4rem' }}>All messages in this conversation will use {MODEL_LABELS[MODEL_KEYS[editLockModel]] || editLockModel}.</div>}
          </div>
          <div style={s.settingsFooter}>
            <button onClick={() => setSettingsOpen(false)} style={s.cancelBtn}>Cancel</button>
            <button onClick={saveSettings} disabled={settingsSaving} style={s.saveBtn}>
              {settingsSaving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {/* files panel */}
      <div style={{ ...s.filePanel, transform: filesOpen ? 'translateX(0)' : 'translateX(100%)' }}>
        <div style={s.filePanelHdr}>
          <div style={s.fileTitleRow}>
            <span style={s.fileTitle}>📎 Files & Knowledge</span>
            <button onClick={() => setFilesOpen(false)} style={s.closeBtn}>✕</button>
          </div>
        </div>

        <div style={s.tabBar}>
          {['library','attached'].map(tab => (
            <button key={tab} onClick={() => setFilesTab(tab)}
              style={{ ...s.tabBtn, ...(filesTab === tab ? s.tabActive : {}) }}>
              {tab === 'library' ? 'Library' : `Attached${attachedFiles.length ? ` (${attachedFiles.length})` : ''}`}
            </button>
          ))}
        </div>

        <div style={s.fileUploadRow}>
          <button onClick={() => fileInputRef.current?.click()} disabled={fileUploading}
            style={{ ...s.ingestBtn, background:'#1e1b4b', color:'#818cf8', borderColor:'#312e81' }}>
            {fileUploading ? 'Uploading…' : '⬆ Upload'}
          </button>
          <input ref={fileInputRef} type="file" style={{ display:'none' }} onChange={uploadFile} />
        </div>

        <div style={s.urlRow}>
          <input value={urlIngest} onChange={e => setUrlIngest(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && ingestUrl()}
            placeholder="https://… ingest URL" style={s.urlInput} />
          <button onClick={ingestUrl} disabled={urlIngesting || !urlIngest.trim()} style={s.ingestBtn}>
            {urlIngesting ? '…' : '⬇ Fetch'}
          </button>
        </div>

        {workspaces.length > 0 && (
          <div style={s.wsRow}>
            <span style={s.wsLabel}>WS:</span>
            <button onClick={() => setWsFilter('')} style={{ ...s.wsPill, ...(wsFilter === '' ? s.wsPillActive : {}) }}>All</button>
            {workspaces.map(ws => (
              <button key={ws} onClick={() => setWsFilter(ws === wsFilter ? '' : ws)}
                style={{ ...s.wsPill, ...(wsFilter === ws ? s.wsPillActive : {}) }}>
                {ws}
              </button>
            ))}
          </div>
        )}

        <div style={s.fileList}>
          {filesTab === 'library' && (
            libFiles.length === 0
              ? <p style={s.emptyMem}>No files yet.<br /><span style={{ fontSize:'0.75rem' }}>Upload files or ingest a URL above.</span></p>
              : libFiles.map(f => {
                  const sc = statusColor(f.status)
                  const isAttached = attachedIds.has(f.id)
                  return (
                    <div key={f.id} style={s.fileItem}>
                      <span style={{ ...s.statusBadge, background:sc.bg, color:sc.color }}>{f.status}</span>
                      <span style={s.fileName} title={f.filename}>{f.filename}</span>
                      {activeConvId && (
                        <button onClick={() => isAttached ? detachFile(f.id) : attachFile(f.id)}
                          style={{ ...s.attachBtn, ...(isAttached ? s.attachedBtn : {}) }}
                          title={isAttached ? 'Detach from conversation' : 'Attach to conversation'}>
                          {isAttached ? '✓' : '+'}
                        </button>
                      )}
                      <button onClick={() => deleteFile(f.id)} style={s.delBtn} title="Delete file">🗑</button>
                    </div>
                  )
                })
          )}
          {filesTab === 'attached' && (
            !activeConvId
              ? <p style={s.emptyMem}>Open a conversation to attach files.</p>
              : attachedFiles.length === 0
                ? <p style={s.emptyMem}>No files attached.<br /><span style={{ fontSize:'0.75rem' }}>Switch to Library tab to attach files.</span></p>
                : attachedFiles.map(f => {
                    const sc = statusColor(f.status)
                    return (
                      <div key={f.id} style={s.fileItem}>
                        <span style={{ ...s.statusBadge, background:sc.bg, color:sc.color }}>{f.status}</span>
                        <span style={s.fileName} title={f.filename}>{f.filename}</span>
                        <button onClick={() => detachFile(f.id)} style={s.attachBtn} title="Detach">✕</button>
                      </div>
                    )
                  })
          )}
        </div>
      </div>

      {/* memory panel */}
      <div style={{ ...s.memPanel, transform: panelSlide }}>
        <div style={s.memHeader}>
          <div style={s.memTitleRow}>
            <div style={s.memTitle}>
              <span>⬡</span> Memory Sheet
              {memData?.version > 0 && <span style={{ fontSize:'0.7rem', color:'#475569', fontWeight:400 }}>v{memData.version}</span>}
            </div>
            <div style={s.memHdrBtns}>
              <button onClick={() => pollMemory(true)} style={s.refreshBtn} disabled={memLoading}>{memLoading ? '…' : '↻'}</button>
              <button onClick={() => setMemOpen(false)} style={s.closeBtn}>✕</button>
            </div>
          </div>
          <div style={s.memMeta}>
            {memPending ? <span style={{ color:'#34d399' }}>updating…</span>
              : memData?.updated_at ? `Updated ${fmtDate(memData.updated_at)}` : 'No memory yet'}
          </div>
        </div>

        <div style={s.tabBar}>
          {['view','edit','history'].map(tab => (
            <button key={tab} onClick={() => tab === 'edit' ? openEdit() : setMemTab(tab)}
              style={{ ...s.tabBtn, ...(memTab === tab ? s.tabActive : {}) }}>
              {tab === 'view' ? 'View' : tab === 'edit' ? 'Edit' : 'History'}
            </button>
          ))}
        </div>

        <div style={{ ...s.memBody, ...(memFlashed && memTab === 'view' ? s.flashBody : {}) }}>
          {memTab === 'view' && (
            <>
              {memLoading && !memData && <p style={s.emptyMem}>Loading…</p>}
              {!memLoading && !hasMemory && <p style={s.emptyMem}>No memory yet.<br /><span style={{ fontSize:'0.75rem' }}>Updates after a few exchanges.</span></p>}
              {sections.map(sec => (
                <div key={sec.name} style={s.section}>
                  <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#94a3b8', background: (SECTION_COLORS[sec.name]||'#94a3b8')+'18' }}>{sec.name}</span>
                  {sec.pairs.map((p, i) => (
                    <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                  ))}
                </div>
              ))}
              {projectSections.length > 0 && (
                <>
                  <div style={s.divider}><span style={s.divLabel}>PROJECT STATE</span><div style={{ flex:1, borderTop:'1px solid #1e293b' }} /></div>
                  {projectSections.map(sec => (
                    <div key={sec.name} style={s.section}>
                      <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#94a3b8', background: (SECTION_COLORS[sec.name]||'#94a3b8')+'18' }}>{sec.name}</span>
                      {sec.pairs.map((p, i) => (
                        <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                      ))}
                    </div>
                  ))}
                </>
              )}
            </>
          )}
          {memTab === 'edit' && (
            <div>
              <div style={{ ...s.editLabel, marginTop:0 }}>USER STATE (key: value per line, headers as [SECTION])</div>
              <textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={10} style={s.editArea} placeholder="[USER]&#10;name: Alice" />
              <div style={s.editLabel}>PROJECT STATE</div>
              <textarea value={editProj} onChange={e => setEditProj(e.target.value)} rows={7} style={s.editArea} placeholder="[GOALS]&#10;goal: Build AI gateway" />
              <div style={s.editBtns}>
                <button onClick={saveEdit} disabled={memSaving} style={s.saveBtn}>{memSaving ? 'Saving…' : 'Save'}</button>
                <button onClick={cancelEdit} style={s.cancelBtn}>Cancel</button>
              </div>
            </div>
          )}
          {memTab === 'history' && (
            <div>
              {histLoading && <p style={s.emptyMem}>Loading…</p>}
              {!histLoading && memHistory.length === 0 && <p style={s.emptyMem}>No history yet.</p>}
              {!histLoading && memHistory.length > 0 && (
                <>
                  <div style={{ fontSize:'0.7rem', color:'#475569', marginBottom:'0.75rem' }}>Select a version to diff against current</div>
                  <div style={s.historyList}>
                    {memHistory.map((v, i) => (
                      <div key={i} onClick={() => setDiffIdx(diffIdx === i ? null : i)}
                        style={{ ...s.historyItem, borderColor: diffIdx === i ? '#6366f1' : '#1e293b' }}>
                        <span style={{ color:'#cbd5e1' }}>v{v.version}</span>
                        <div style={s.historyMeta}>{fmtDate(v.created_at)}</div>
                      </div>
                    ))}
                  </div>
                  {diffTarget && (
                    <div style={s.diffBox}>
                      <div style={s.diffTitle}>v{diffTarget.version} → current (v{memData?.version})</div>
                      {diffLines.length === 0 || diffLines.every(d => d.type === 'same')
                        ? <div style={{ ...s.diffLine, ...s.diffSame }}>No changes</div>
                        : diffLines.map((d, i) => (
                          <div key={i} style={{ ...s.diffLine, ...(d.type==='added' ? s.diffAdded : d.type==='removed' ? s.diffRemoved : s.diffSame) }}>
                            {d.type==='added' ? '+ ' : d.type==='removed' ? '− ' : '  '}{d.line}
                          </div>
                        ))
                      }
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div style={s.memFooter}>
          <div style={s.footerRow}>
            <div style={s.footerActions}>
              <button onClick={exportMemory} style={s.actionBtn}>⬇ Export</button>
              <button onClick={() => importRef.current?.click()} style={s.actionBtn}>⬆ Import</button>
              <input ref={importRef} type="file" accept=".json" style={{ display:'none' }} onChange={handleImport} />
            </div>
            <span style={s.footerStats}>{hasMemory ? `${sections.length+projectSections.length} sec · ${wordCount}w` : 'Empty'}</span>
          </div>
          {activeConvId && (
            <div style={s.memToggleRow}>
              <span style={s.memToggleLabel}>Memory in this conversation</span>
              <button onClick={toggleConvMemory} disabled={memToggling}
                style={{ ...s.togglePill, color: convMemEnabled ? '#34d399' : '#475569', borderColor: convMemEnabled ? '#1e4e3a' : '#334155' }}>
                <span style={{ width:'7px', height:'7px', borderRadius:'50%', background: convMemEnabled ? '#34d399' : '#475569' }} />
                {convMemEnabled ? 'Enabled' : 'Disabled'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
