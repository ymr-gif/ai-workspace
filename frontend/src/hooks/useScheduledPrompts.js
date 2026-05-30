import { useState, useCallback, useEffect } from 'react'

export default function useScheduledPrompts(token) {
  const [autoOpen, setAutoOpen]               = useState(false)
  const [schedules, setSchedules]             = useState([])
  const [schedulesLoading, setSchedulesLoading] = useState(false)
  const [formOpen, setFormOpen]               = useState(false)
  const [editTarget, setEditTarget]           = useState(null)
  const [formName, setFormName]               = useState('')
  const [formPrompt, setFormPrompt]           = useState('')
  const [formSchedule, setFormSchedule]       = useState('daily')
  const [formModel, setFormModel]             = useState('')
  const [formWsId, setFormWsId]               = useState('')
  const [formSaving, setFormSaving]           = useState(false)
  const [runsMap, setRunsMap]                 = useState({})
  const [runsLoading, setRunsLoading]         = useState({})
  const [expandedId, setExpandedId]           = useState(null)
  const [triggeringId, setTriggeringId]       = useState(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadSchedules = useCallback(async () => {
    setSchedulesLoading(true)
    try {
      const r = await fetch('/api/scheduled-prompts', { headers: authHeaders })
      if (r.ok) setSchedules(await r.json())
    } catch { /* ignore */ } finally { setSchedulesLoading(false) }
  }, [token])

  useEffect(() => { if (autoOpen) loadSchedules() }, [autoOpen])

  async function saveSchedule() {
    setFormSaving(true)
    try {
      const body = { name: formName, prompt: formPrompt, schedule: formSchedule }
      if (formModel) body.model_override = formModel
      if (formWsId)  body.workspace_id   = formWsId
      const url    = editTarget ? `/api/scheduled-prompts/${editTarget.id}` : '/api/scheduled-prompts'
      const method = editTarget ? 'PATCH' : 'POST'
      const r = await fetch(url, { method, headers: { ...authHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (r.ok) { await loadSchedules(); setFormOpen(false) }
    } catch { /* ignore */ } finally { setFormSaving(false) }
  }

  async function deleteSchedule(id) {
    try {
      await fetch(`/api/scheduled-prompts/${id}`, { method: 'DELETE', headers: authHeaders })
      setSchedules(prev => prev.filter(s => s.id !== id))
      if (expandedId === id) setExpandedId(null)
    } catch { /* ignore */ }
  }

  async function toggleActive(sc) {
    try {
      const r = await fetch(`/api/scheduled-prompts/${sc.id}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !sc.is_active }),
      })
      if (r.ok) setSchedules(prev => prev.map(s => s.id === sc.id ? { ...s, is_active: !sc.is_active } : s))
    } catch { /* ignore */ }
  }

  async function triggerRun(id) {
    setTriggeringId(id)
    try {
      await fetch(`/api/scheduled-prompts/${id}/run`, { method: 'POST', headers: authHeaders })
      if (expandedId === id) loadRuns(id)
    } catch { /* ignore */ } finally { setTriggeringId(null) }
  }

  async function loadRuns(id) {
    setRunsLoading(prev => ({ ...prev, [id]: true }))
    try {
      const r = await fetch(`/api/scheduled-prompts/${id}/runs`, { headers: authHeaders })
      if (r.ok) setRunsMap(prev => ({ ...prev, [id]: await r.json() }))
    } catch { /* ignore */ } finally { setRunsLoading(prev => ({ ...prev, [id]: false })) }
  }

  function openCreate() {
    setEditTarget(null)
    setFormName(''); setFormPrompt(''); setFormSchedule('daily'); setFormModel(''); setFormWsId('')
    setFormOpen(true)
  }

  function openEdit(sc) {
    setEditTarget(sc)
    setFormName(sc.name); setFormPrompt(sc.prompt || ''); setFormSchedule(sc.schedule || 'daily')
    setFormModel(sc.model_override || ''); setFormWsId(sc.workspace_id || '')
    setFormOpen(true)
  }

  function toggleExpanded(id) {
    if (expandedId === id) { setExpandedId(null); return }
    setExpandedId(id)
    if (!runsMap[id]) loadRuns(id)
  }

  return {
    autoOpen, setAutoOpen,
    schedules, schedulesLoading,
    formOpen, setFormOpen,
    editTarget,
    formName, setFormName,
    formPrompt, setFormPrompt,
    formSchedule, setFormSchedule,
    formModel, setFormModel,
    formWsId, setFormWsId,
    formSaving,
    runsMap, runsLoading,
    expandedId, triggeringId,
    loadSchedules,
    saveSchedule,
    deleteSchedule,
    toggleActive,
    triggerRun,
    openCreate,
    openEdit,
    toggleExpanded,
  }
}
