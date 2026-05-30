import { useState, useCallback, useEffect } from 'react'

export default function useGoals(token) {
  const [goalsOpen, setGoalsOpen]       = useState(false)
  const [goals, setGoals]               = useState([])
  const [goalsLoading, setGoalsLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [formOpen, setFormOpen]         = useState(false)
  const [editTarget, setEditTarget]     = useState(null)
  const [formTitle, setFormTitle]       = useState('')
  const [formDesc, setFormDesc]         = useState('')
  const [formStatus, setFormStatus]     = useState('active')
  const [formSaving, setFormSaving]     = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadGoals = useCallback(async (status = 'all') => {
    setGoalsLoading(true)
    try {
      const qs = status !== 'all' ? `?status=${encodeURIComponent(status)}` : ''
      const r = await fetch(`/api/goals${qs}`, { headers: authHeaders })
      if (r.ok) setGoals(await r.json())
    } catch { /* ignore */ } finally { setGoalsLoading(false) }
  }, [token])

  useEffect(() => { if (goalsOpen) loadGoals(statusFilter) }, [goalsOpen])

  async function saveGoal() {
    setFormSaving(true)
    try {
      const body = { title: formTitle, description: formDesc, status: formStatus }
      const url    = editTarget ? `/api/goals/${editTarget.id}` : '/api/goals'
      const method = editTarget ? 'PATCH' : 'POST'
      const r = await fetch(url, { method, headers: { ...authHeaders, 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (r.ok) { await loadGoals(statusFilter); setFormOpen(false) }
    } catch { /* ignore */ } finally { setFormSaving(false) }
  }

  async function deleteGoal(id) {
    try {
      await fetch(`/api/goals/${id}`, { method: 'DELETE', headers: authHeaders })
      setGoals(prev => prev.filter(g => g.id !== id))
    } catch { /* ignore */ }
  }

  async function toggleStatus(goal) {
    const next = goal.status === 'active' ? 'paused' : 'active'
    try {
      const r = await fetch(`/api/goals/${goal.id}`, {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      })
      if (r.ok) setGoals(prev => prev.map(g => g.id === goal.id ? { ...g, status: next } : g))
    } catch { /* ignore */ }
  }

  async function linkConversation(goalId, conversationId) {
    try {
      await fetch(`/api/goals/${goalId}/link/${encodeURIComponent(conversationId)}`, { method: 'POST', headers: authHeaders })
      setGoals(prev => prev.map(g => g.id === goalId
        ? { ...g, linked_conversation_ids: [...(g.linked_conversation_ids || []), conversationId] }
        : g))
    } catch { /* ignore */ }
  }

  function openCreate() {
    setEditTarget(null); setFormTitle(''); setFormDesc(''); setFormStatus('active')
    setFormOpen(true)
  }

  function openEdit(goal) {
    setEditTarget(goal); setFormTitle(goal.title); setFormDesc(goal.description || ''); setFormStatus(goal.status || 'active')
    setFormOpen(true)
  }

  function changeFilter(f) {
    setStatusFilter(f); loadGoals(f)
  }

  return {
    goalsOpen, setGoalsOpen,
    goals, goalsLoading,
    statusFilter, changeFilter,
    formOpen, setFormOpen,
    editTarget,
    formTitle, setFormTitle,
    formDesc, setFormDesc,
    formStatus, setFormStatus,
    formSaving,
    loadGoals,
    saveGoal,
    deleteGoal,
    toggleStatus,
    linkConversation,
    openCreate,
    openEdit,
  }
}
