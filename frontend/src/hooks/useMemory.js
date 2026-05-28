import { useState, useRef, useEffect, useCallback } from 'react'

export default function useMemory(token, sidebarWsId) {
  const [memOpen, setMemOpen] = useState(false)
  const [memTab, setMemTab] = useState('view')
  const [memData, setMemData] = useState(null)
  const [memLoading, setMemLoading] = useState(false)
  const [memFlashed, setMemFlashed] = useState(false)
  const [memTick, setMemTick] = useState(0)
  const [memPending, setMemPending] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [editProj, setEditProj] = useState('')
  const [memSaving, setMemSaving] = useState(false)
  const [memHistory, setMemHistory] = useState([])
  const [histLoading, setHistLoading] = useState(false)
  const [diffIdx, setDiffIdx] = useState(null)
  const [wsMemData, setWsMemData] = useState(null)
  const [wsMemLoading, setWsMemLoading] = useState(false)
  const [wsMemEditing, setWsMemEditing] = useState(false)
  const [wsMemContent, setWsMemContent] = useState('')
  const [wsMemSaving, setWsMemSaving] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }
  const prevMemSig = useRef('')

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

  const loadWsMemory = useCallback(async (wsId) => {
    setWsMemLoading(true)
    try {
      const r = await fetch(`/api/workspaces/${wsId}/memory`, { headers: authHeaders })
      if (r.ok) setWsMemData(await r.json())
    } catch { /* ignore */ } finally { setWsMemLoading(false) }
  }, [token])

  useEffect(() => {
    if (!memOpen || memTab !== 'workspace' || !sidebarWsId) return
    loadWsMemory(sidebarWsId)
  }, [memOpen, memTab, sidebarWsId])

  async function saveWsMemory() {
    if (!sidebarWsId) return
    setWsMemSaving(true)
    try {
      const r = await fetch(`/api/workspaces/${sidebarWsId}/memory`, {
        method: 'PUT', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: wsMemContent }),
      })
      if (r.ok) { setWsMemData(await r.json()); setWsMemEditing(false) }
    } catch { /* ignore */ } finally { setWsMemSaving(false) }
  }

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

  return {
    memOpen, setMemOpen,
    memTab, setMemTab,
    memData, setMemData,
    memLoading,
    memFlashed,
    memTick, setMemTick,
    memPending,
    editContent, setEditContent,
    editProj, setEditProj,
    memSaving,
    memHistory,
    histLoading,
    diffIdx, setDiffIdx,
    wsMemData,
    wsMemLoading,
    wsMemEditing, setWsMemEditing,
    wsMemContent, setWsMemContent,
    wsMemSaving,
    prevMemSig,
    pollMemory,
    loadWsMemory,
    saveWsMemory,
    openEdit,
    cancelEdit,
    saveEdit,
    exportMemory,
    handleImport,
  }
}
