import { useState, useEffect, useCallback } from 'react'

function urlBase64ToUint8Array(base64) {
  const padded = base64.replace(/[-_]/g, c => (c === '-' ? '+' : '/')) + '='.repeat((4 - base64.length % 4) % 4)
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0))
}

export default function useNotificationPrefs(token) {
  const [prefs, setPrefs] = useState(null)
  const [prefsLoading, setPrefsLoading] = useState(true)
  const [vapidPublicKey, setVapidPublicKey] = useState(null)
  const [pushSupported, setPushSupported] = useState(false)
  const [pushSubscribed, setPushSubscribed] = useState(false)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  // detect push support + register SW
  useEffect(() => {
    if (!('PushManager' in window) || !('serviceWorker' in navigator)) {
      setPushSupported(false)
      return
    }
    setPushSupported(true)
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  }, [])

  // fetch prefs + vapid key on mount
  const load = useCallback(async () => {
    setPrefsLoading(true)
    try {
      const r = await fetch('/api/notifications/preferences', { headers: authHeaders })
      if (r.ok) {
        const d = await r.json()
        setPrefs(d)
        setPushSubscribed(d.push_enabled === true)
      }
    } catch { /* ignore */ }

    try {
      const r = await fetch('/api/notifications/vapid-public-key')
      if (r.ok) {
        const d = await r.json()
        setVapidPublicKey(d.public_key || null)
      }
    } catch { /* ignore */ }

    setPrefsLoading(false)
  }, [token])

  useEffect(() => { load() }, [load])

  async function updatePrefs(partial) {
    setPrefs(p => p ? { ...p, ...partial } : p)
    try {
      await fetch('/api/notifications/preferences', {
        method: 'PATCH',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(partial),
      })
    } catch { /* ignore */ }
  }

  async function subscribePush() {
    if (!vapidPublicKey || !pushSupported) return
    try {
      const reg = await navigator.serviceWorker.ready
      let sub = await reg.pushManager.getSubscription()
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
        })
      }
      const body = sub.toJSON()
      const r = await fetch('/api/notifications/push/subscribe', {
        method: 'POST',
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint: body.endpoint, p256dh: body.keys.p256dh, auth: body.keys.auth }),
      })
      if (r.ok) {
        setPushSubscribed(true)
        await updatePrefs({ push_enabled: true })
      }
    } catch { /* ignore */ }
  }

  async function unsubscribePush() {
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      if (sub) await sub.unsubscribe()
    } catch { /* ignore */ }
    setPushSubscribed(false)
    await updatePrefs({ push_enabled: false })
  }

  async function togglePref(key) {
    if (key === 'push_enabled') {
      if (pushSubscribed) {
        await unsubscribePush()
      } else {
        if (Notification.permission === 'denied') return
        if (Notification.permission === 'default') {
          const result = await Notification.requestPermission()
          if (result !== 'granted') return
        }
        await subscribePush()
      }
      return
    }
    const current = prefs?.[key]
    if (current === undefined) return
    await updatePrefs({ [key]: !current })
  }

  return {
    prefs, prefsLoading, vapidPublicKey, pushSupported, pushSubscribed,
    togglePref, updatePrefs,
  }
}
