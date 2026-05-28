import { useState, useCallback, useEffect } from 'react'

export default function useAdmin(token) {
  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteList, setInviteList] = useState([])
  const [inviteLoading, setInviteLoading] = useState(false)
  const [newToken, setNewToken] = useState('')
  const [tokenGenerating, setTokenGenerating] = useState(false)
  const [reEmbedding, setReEmbedding] = useState(false)
  const [reEmbedMsg, setReEmbedMsg] = useState('')

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadInvites = useCallback(async () => {
    setInviteLoading(true)
    try {
      const r = await fetch('/api/auth/invites', { headers: authHeaders })
      if (r.ok) setInviteList(await r.json())
    } catch { /* ignore */ } finally { setInviteLoading(false) }
  }, [token])

  useEffect(() => {
    if (!inviteOpen) return
    loadInvites()
  }, [inviteOpen])

  async function generateInvite() {
    setTokenGenerating(true)
    try {
      const r = await fetch('/api/auth/invite', { method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' }, body: '{}' })
      if (r.ok) { const d = await r.json(); setNewToken(d.token); await loadInvites() }
    } catch { /* ignore */ } finally { setTokenGenerating(false) }
  }

  async function triggerReEmbed() {
    setReEmbedding(true)
    setReEmbedMsg('')
    try {
      const r = await fetch('/api/admin/re-embed', { method: 'POST', headers: authHeaders })
      if (r.ok) { const d = await r.json(); setReEmbedMsg(`Queued ${d.queued} chunks`) }
      else setReEmbedMsg('Error: ' + r.status)
    } catch { setReEmbedMsg('Request failed') } finally { setReEmbedding(false) }
  }

  return {
    inviteOpen, setInviteOpen,
    inviteList,
    inviteLoading,
    newToken,
    tokenGenerating,
    reEmbedding,
    reEmbedMsg,
    loadInvites,
    generateInvite,
    triggerReEmbed,
  }
}
