import { useState, useCallback, useEffect, useMemo } from 'react'

const CONNECTOR_LABELS = {
  google_drive: 'Google Drive',
  google_calendar: 'Google Calendar',
  gmail: 'Gmail',
  notion: 'Notion',
  github: 'GitHub',
}

const CONNECTOR_TYPES = ['google_drive', 'google_calendar', 'gmail', 'notion', 'github']

// Add connector types here to expose OAuth flow in the UI.
// All five are backend-complete; none currently exposed.
// Note: existing ExternalSource rows for previously-connected users remain visible
// (Connected card, no reconnect button). Clean up manually if needed.
const ENABLED_CONNECTOR_TYPES = []

export default function useIntegrations(token) {
  const [integOpen, setIntegOpen] = useState(false)
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(new Set())
  const [errorMsg, setErrorMsg] = useState('')
  const [popupBlocked, setPopupBlocked] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

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
      case 'active':    return { text: 'Connected', color: '#3dff6e' }
      case 'syncing':   return { text: 'Syncing…',  color: '#ffb000' }
      case 'error':     return { text: 'Error',     color: '#ff2222' }
      default:          return { text: status,      color: '#5a5a5a' }
    }
  }

  return {
    integOpen, setIntegOpen,
    sources, loading, syncing, errorMsg, popupBlocked,
    connectedTypes,
    CONNECTOR_LABELS, CONNECTOR_TYPES, ENABLED_CONNECTOR_TYPES,
    loadSources, deleteSource, syncSource, startOAuth, statusLabel,
  }
}
