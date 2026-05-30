import { useState, useRef, useEffect, useCallback } from 'react'

export default function useToolLogs(token, activeConvId) {
  const [toolLogOpen, setToolLogOpen] = useState(false)
  const [toolLogs, setToolLogs] = useState([])
  const [toolLogsLoading, setToolLogsLoading] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadToolLogs = useCallback(async (convId) => {
    setToolLogsLoading(true)
    try {
      const qs = convId ? `?conversation_id=${encodeURIComponent(convId)}&limit=100` : '?limit=100'
      const r = await fetch(`/api/tool-calls${qs}`, { headers: authHeaders })
      if (r.ok) setToolLogs(await r.json())
    } catch { /* ignore */ } finally { setToolLogsLoading(false) }
  }, [token])

  useEffect(() => {
    if (!toolLogOpen) return
    loadToolLogs(activeConvId)
  }, [toolLogOpen, activeConvId])

  return {
    toolLogOpen, setToolLogOpen,
    toolLogs, setToolLogs,
    toolLogsLoading,
    loadToolLogs,
  }
}
