import { useState, useCallback, useEffect } from 'react'

export default function useInsights(token) {
  const [insightsOpen, setInsightsOpen] = useState(false)
  const [insights, setInsights] = useState([])
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [graphStats, setGraphStats] = useState(null)
  const [graphLoading, setGraphLoading] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadInsights = useCallback(async (all = false) => {
    setInsightsLoading(true)
    try {
      const r = await fetch(`/api/insights${all ? '?all=true' : ''}`, { headers: authHeaders })
      if (r.ok) {
        const data = await r.json()
        setInsights(data)
        if (!all) setUnreadCount(data.length)
      }
    } catch { /* ignore */ } finally { setInsightsLoading(false) }
  }, [token])

  useEffect(() => { loadInsights() }, [])

  useEffect(() => {
    if (!insightsOpen) return
    loadInsights(true)
  }, [insightsOpen])

  async function markInsightRead(id) {
    try {
      const r = await fetch(`/api/insights/${id}/read`, { method: 'PATCH', headers: authHeaders })
      if (r.ok) {
        setInsights(prev => prev.map(i => i.id === id ? { ...i, is_read: true } : i))
        setUnreadCount(prev => Math.max(0, prev - 1))
      }
    } catch { /* ignore */ }
  }

  async function deleteInsight(id) {
    const wasUnread = insights.find(i => i.id === id && !i.is_read)
    try {
      await fetch(`/api/insights/${id}`, { method: 'DELETE', headers: authHeaders })
      setInsights(prev => prev.filter(i => i.id !== id))
      if (wasUnread) setUnreadCount(prev => Math.max(0, prev - 1))
    } catch { /* ignore */ }
  }

  const loadGraphStats = useCallback(async () => {
    setGraphLoading(true)
    try {
      const r = await fetch('/api/graph/stats', { headers: authHeaders })
      if (r.ok) setGraphStats(await r.json())
    } catch { /* ignore */ } finally { setGraphLoading(false) }
  }, [token])

  return {
    insightsOpen, setInsightsOpen,
    insights,
    insightsLoading,
    unreadCount,
    graphStats,
    graphLoading,
    loadInsights,
    markInsightRead,
    deleteInsight,
    loadGraphStats,
  }
}
