import { useState } from 'react'

export default function useSettings(token, activeConvId, setConversations) {
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [editSysPrompt, setEditSysPrompt] = useState('')
  const [editLockModel, setEditLockModel] = useState('')
  const [convSysPrompt, setConvSysPrompt] = useState('')
  const [convLockModel, setConvLockModel] = useState('')
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [editWsId, setEditWsId] = useState('')

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  async function saveSettings() {
    if (!activeConvId) return; setSettingsSaving(true)
    try {
      const r = await fetch(`/api/conversations/${activeConvId}`, {
        method: 'PATCH', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_prompt: editSysPrompt || null, locked_model: editLockModel || null, workspace_id: editWsId || null }),
      })
      if (!r.ok) return
      const data = await r.json()
      setConvSysPrompt(data.system_prompt); setConvLockModel(data.locked_model)
      setConversations(prev => prev.map(c => c.id === activeConvId ? { ...c, system_prompt: data.system_prompt, locked_model: data.locked_model, workspace_id: data.workspace_id } : c))
      setSettingsOpen(false)
    } catch { /* ignore */ } finally { setSettingsSaving(false) }
  }

  return {
    settingsOpen, setSettingsOpen,
    editSysPrompt, setEditSysPrompt,
    editLockModel, setEditLockModel,
    convSysPrompt,
    convLockModel,
    settingsSaving,
    editWsId, setEditWsId,
    saveSettings,
  }
}
