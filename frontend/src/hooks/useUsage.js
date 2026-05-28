import { useState, useCallback, useEffect } from 'react'

export default function useUsage(token) {
  const [usageOpen, setUsageOpen] = useState(false)
  const [usageData, setUsageData] = useState(null)
  const [usageLoading, setUsageLoading] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadUsage = useCallback(async () => {
    setUsageLoading(true)
    try {
      const r = await fetch('/api/usage', { headers: authHeaders })
      if (r.ok) setUsageData(await r.json())
    } catch { /* ignore */ }
    finally { setUsageLoading(false) }
  }, [token])

  useEffect(() => {
    if (!usageOpen) return
    loadUsage()
  }, [usageOpen])

  return {
    usageOpen, setUsageOpen,
    usageData,
    usageLoading,
    loadUsage,
  }
}
