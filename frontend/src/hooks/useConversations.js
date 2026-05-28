import { useState, useRef, useEffect } from 'react'

export default function useConversations(token, sidebarWsId) {
  const [conversations, setConversations] = useState([])
  const [activeConvId, setActiveConvId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  // conversation settings
  const [convMemEnabled, setConvMemEnabled] = useState(true)
  const [memToggling, setMemToggling] = useState(false)
  const [convSysPrompt, setConvSysPrompt] = useState('')
  const [convLockModel, setConvLockModel] = useState('')

  // sidebar conversation search
  const [convSearch, setConvSearch] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searchLoading, setSearchLoading] = useState(false)

  // proactive suggestion
  const [proactive, setProactive] = useState(null)

  // memory write confirmation
  const [pendingWriteFact, setPendingWriteFact] = useState(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }
  const nextId = useRef(0)
  const bottomRef = useRef(null)

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
      .then(msgs => setMessages(msgs.map(m => ({ id: nextId.current++, role: m.role === 'assistant' ? 'ai' : 'user', text: m.content, model: m.model, streaming: false, promptTokens: m.prompt_tokens, completionTokens: m.completion_tokens, totalTokens: m.total_tokens, costUsd: m.cost_usd }))))
      .catch(() => {})
  }, [activeConvId])

  useEffect(() => {
    if (!convSearch.trim()) { setSearchResults(null); return }
    const tid = setTimeout(async () => {
      setSearchLoading(true)
      try {
        const qs = new URLSearchParams({ q: convSearch.trim() })
        if (sidebarWsId) qs.set('workspace_id', sidebarWsId)
        const r = await fetch(`/api/conversations?${qs}`, { headers: authHeaders })
        if (r.ok) setSearchResults(await r.json())
      } catch { /* ignore */ } finally { setSearchLoading(false) }
    }, 350)
    return () => clearTimeout(tid)
  }, [convSearch, sidebarWsId])

  function newChat() { setActiveConvId(null); setMessages([]); setInput(''); setConvMemEnabled(true); setConvSysPrompt(''); setConvLockModel('') }

  function selectConv(id) {
    if (id === activeConvId) return
    setActiveConvId(id); setMessages([])
    const c = conversations.find(x => x.id === id)
    if (c) {
      setConvMemEnabled(c.memory_enabled !== false)
      setConvSysPrompt(c.system_prompt || '')
      setConvLockModel(c.locked_model || '')
    }
    return c
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

  async function deleteConv(e, id) {
    e.stopPropagation()
    if (!window.confirm('Delete this conversation?')) return
    await fetch(`/api/conversations/${id}`, { method:'DELETE', headers: authHeaders })
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConvId === id) newChat()
  }

  async function exportConv(convId, title, format = 'markdown') {
    try {
      const r = await fetch(`/api/conversations/${convId}/export?format=${format}`, { headers: authHeaders })
      if (!r.ok) return
      const blob = await r.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = `${(title || 'conversation').slice(0,40).replace(/[^a-z0-9 _-]/gi, '_')}.${format === 'json' ? 'json' : 'md'}`
      a.click(); URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  return {
    conversations, setConversations,
    activeConvId, setActiveConvId,
    messages, setMessages,
    input, setInput,
    loading, setLoading,
    convMemEnabled, setConvMemEnabled,
    memToggling,
    convSysPrompt,
    convLockModel,
    convSearch, setConvSearch,
    searchResults, setSearchResults,
    searchLoading,
    proactive, setProactive,
    pendingWriteFact, setPendingWriteFact,
    nextId,
    bottomRef,
    newChat,
    selectConv,
    toggleConvMemory,
    deleteConv,
    exportConv,
  }
}
