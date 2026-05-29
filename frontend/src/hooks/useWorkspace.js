import { useState, useEffect } from 'react'

const LS_KEY = 'nim_sidebar_ws_id'

export default function useWorkspace(token) {
  const [sidebarWsList, setSidebarWsList] = useState([])
  const [sidebarWsId, setSidebarWsId] = useState(() => localStorage.getItem(LS_KEY) || null)

  function persistWsId(id) {
    setSidebarWsId(id)
    if (id) localStorage.setItem(LS_KEY, id)
    else localStorage.removeItem(LS_KEY)
  }

  // workspace modal (create / edit)
  const [wsModalOpen, setWsModalOpen] = useState(false)
  const [wsModalTarget, setWsModalTarget] = useState(null)
  const [wsFieldName, setWsFieldName] = useState('')
  const [wsFieldDesc, setWsFieldDesc] = useState('')
  const [wsFieldSys, setWsFieldSys] = useState('')
  const [wsSaving, setWsSaving] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => {
    fetch('/api/workspaces', { headers: authHeaders })
      .then(r => r.ok ? r.json() : [])
      .then(list => {
        setSidebarWsList(list)
        const stored = localStorage.getItem(LS_KEY)
        if (stored && !list.find(w => w.id === stored)) persistWsId(null)
      }).catch(() => {})
  }, [])

  function openCreateWs() { setWsModalTarget(null); setWsFieldName(''); setWsFieldDesc(''); setWsFieldSys(''); setWsModalOpen(true) }
  function openEditWs(ws, e) { e.stopPropagation(); setWsModalTarget(ws); setWsFieldName(ws.name); setWsFieldDesc(ws.description || ''); setWsFieldSys(ws.system_prompt || ''); setWsModalOpen(true) }

  async function saveWsModal() {
    if (!wsFieldName.trim()) return
    setWsSaving(true)
    try {
      const isEdit = !!wsModalTarget
      const r = await fetch(isEdit ? `/api/workspaces/${wsModalTarget.id}` : '/api/workspaces', {
        method: isEdit ? 'PATCH' : 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: wsFieldName.trim(), description: wsFieldDesc || null, system_prompt: wsFieldSys || null }),
      })
      if (!r.ok) return
      const d = await r.json()
      setSidebarWsList(prev => isEdit ? prev.map(w => w.id === d.id ? { ...w, ...d } : w) : [...prev, d])
      setWsModalOpen(false)
    } catch { /* ignore */ } finally { setWsSaving(false) }
  }

  async function deleteWs() {
    if (!wsModalTarget) return
    if (!window.confirm(`Delete workspace "${wsModalTarget.name}"? Conversations and files will become unorganized.`)) return
    try {
      await fetch(`/api/workspaces/${wsModalTarget.id}`, { method: 'DELETE', headers: authHeaders })
      setSidebarWsList(prev => prev.filter(w => w.id !== wsModalTarget.id))
      if (sidebarWsId === wsModalTarget.id) persistWsId(null)
      setWsModalOpen(false)
    } catch { /* ignore */ }
  }

  return {
    sidebarWsList, setSidebarWsList,
    sidebarWsId, setSidebarWsId: persistWsId,
    wsModalOpen, setWsModalOpen,
    wsModalTarget,
    wsFieldName, setWsFieldName,
    wsFieldDesc, setWsFieldDesc,
    wsFieldSys, setWsFieldSys,
    wsSaving,
    openCreateWs,
    openEditWs,
    saveWsModal,
    deleteWs,
  }
}
