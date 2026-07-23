import { useState, useCallback, useEffect, useMemo } from 'react'

const CONNECTOR_LABELS = {
  google_drive: 'Google Drive',
  google_calendar: 'Google Calendar',
  gmail: 'Gmail',
  notion: 'Notion',
  github: 'GitHub',
}

const CONNECTOR_TYPES = ['google_drive', 'google_calendar', 'gmail', 'notion', 'github']

// Which connector types get an OAuth button is now a RUNTIME backend setting
// (config.ENABLED_CONNECTOR_TYPES, served by GET /api/integrations/available — QUEUE
// Q0.6, 2026-07-23), not a source constant here. A Vite import.meta.env var would be
// inlined at BUILD time and couldn't flip live via /admin/env/reload, so this fetches
// on mount instead. Initial state stays [] so a failed/slow fetch degrades to
// *stubbed* (every connector shows "Soon"), never to *exposed*.
//
// Google connectors were re-enabled 2026-06-29 for connector-intent latch data collection, then
// RE-STUBBED 2026-07-02 once enough latch_score data was collected and the tuning closed (fork-B:
// floor 0.70 + clarify fallback; see plans/connector-latch-data-plan.md → Phase 4 DECIDED). The
// backend connector code + latch stay intact — an empty list just removes the OAuth button so NO
// NEW users can connect. It does NOT deactivate connectors already OAuth'd: admin's ExternalSource
// rows from the data-collection window stay `active` in the DB, so the backend still sees
// drive/calendar/gmail as active for admin and the latch KEEPS firing on admin turns (tools still
// work for admin). To fully deactivate (latch never fires for anyone), delete/pause those rows
// (DELETE /api/integrations/{id} or PATCH status=paused). To re-expose, set ENABLED_CONNECTOR_TYPES
// on the backend + POST /admin/env/reload — no frontend rebuild needed.

export default function useIntegrations(token) {
  const [integOpen, setIntegOpen] = useState(false)
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(new Set())
  const [errorMsg, setErrorMsg] = useState('')
  const [popupBlocked, setPopupBlocked] = useState(false)
  const [enabledConnectorTypes, setEnabledConnectorTypes] = useState([])

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => {
    if (!token) return
    let cancelled = false
    fetch('/api/integrations/available', { headers: authHeaders })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!cancelled && data && Array.isArray(data.types)) setEnabledConnectorTypes(data.types)
      })
      .catch(() => {})   // failed fetch → stays [], degrades to stubbed
    return () => { cancelled = true }
  }, [token])

  const loadSources = useCallback(async () => {
    setLoading(true)
    setErrorMsg('')
    try {
      const r = await fetch('/api/integrations', { headers: authHeaders })
      if (r.ok) setSources(await r.json())
    } catch {
      setErrorMsg('Failed to load integrations')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (integOpen) loadSources()
  }, [integOpen])

  async function deleteSource(id) {
    const prev = sources
    setSources(prev => prev.filter(s => s.id !== id))
    try {
      const r = await fetch(`/api/integrations/${id}`, { method: 'DELETE', headers: authHeaders })
      if (!r.ok) { setSources(() => prev); setErrorMsg('Failed to delete source') }
    } catch {
      setSources(() => prev)
      setErrorMsg('Failed to delete source')
    }
  }

  async function syncSource(id) {
    setSyncing(prev => new Set(prev).add(id))
    setErrorMsg('')
    try {
      await fetch(`/api/integrations/${id}/sync`, { method: 'POST', headers: authHeaders })
      setTimeout(() => loadSources(), 3000)
    } catch {
      setErrorMsg('Failed to trigger sync')
    } finally {
      setSyncing(prev => { const n = new Set(prev); n.delete(id); return n })
    }
  }

  function startOAuth(type) {
    setErrorMsg('')
    setPopupBlocked(false)
    fetch(`/api/integrations/oauth/start?connector_type=${type}`, { headers: authHeaders })
      .then(r => r.ok ? r.json() : r.json().then(e => Promise.reject(e?.detail || 'Failed to start OAuth')))
      .then(data => {
        const popup = window.open(data.url, 'oauth_popup', 'width=600,height=700')
        if (!popup) { setPopupBlocked(true); return }
        const timer = setInterval(() => {
          if (popup.closed) {
            clearInterval(timer)
            loadSources()
          }
        }, 500)
      })
      .catch(msg => setErrorMsg(typeof msg === 'string' ? msg : 'Failed to start OAuth'))
  }

  const connectedTypes = useMemo(() => new Set(sources.map(s => s.connector_type)), [sources])

  function statusLabel(status) {
    switch (status) {
      case 'active':    return { text: 'Connected', color: '#55d67c' }
      case 'syncing':   return { text: 'Syncing…',  color: '#f2a33c' }
      case 'error':     return { text: 'Error',     color: '#e5534b' }
      default:          return { text: status,      color: '#8ba3bd' }
    }
  }

  return {
    integOpen, setIntegOpen,
    sources, loading, syncing, errorMsg, popupBlocked,
    connectedTypes,
    CONNECTOR_LABELS, CONNECTOR_TYPES, ENABLED_CONNECTOR_TYPES: enabledConnectorTypes,
    loadSources, deleteSource, syncSource, startOAuth, statusLabel,
  }
}
