import { useEffect, useMemo, useRef, useState } from 'react'
import s, { LAYERS } from '../../lib/chatStyles.js'
import { fmtDate, parseMemory, computeDiff } from '../../lib/chatUtils.js'

import useConversations from '../../hooks/useConversations.js'
import useMemory from '../../hooks/useMemory.js'
import useFiles from '../../hooks/useFiles.js'
import useModelParams from '../../hooks/useModelParams.js'
import useSettings from '../../hooks/useSettings.js'
import useToolLogs from '../../hooks/useToolLogs.js'
import useUsage from '../../hooks/useUsage.js'
import useAdmin from '../../hooks/useAdmin.js'
import useInsights from '../../hooks/useInsights.js'
import useSearch from '../../hooks/useSearch.js'
import useScheduledPrompts from '../../hooks/useScheduledPrompts.js'
import useGoals from '../../hooks/useGoals.js'
import useIntegrations from '../../hooks/useIntegrations.js'
import useOnboarding from '../../hooks/useOnboarding.js'
import useVoice from '../../hooks/useVoice.js'
import useNotificationPrefs from '../../hooks/useNotificationPrefs.js'
import useStreamChat from '../../hooks/useStreamChat.js'
import { PanelPropsCtx } from './PanelPropsContext'

import Sidebar from './Sidebar'
import MessageList from './MessageList'
import ModelToolbar from './ModelToolbar'
import SettingsModal from './SettingsModal'
import FileViewer from './FileViewer'
import OnboardingModal from './OnboardingModal'
import TelemetryStrip from './TelemetryStrip'
import Dock, { DOCK_GROUPS } from './Dock'
import CommandPalette from './CommandPalette'

export default function Chat({ token, onLogout }) {
  const conv = useConversations(token)
  const mem = useMemory(token)
  const settings = useSettings(token, conv.activeConvId, conv.setConversations)
  const files = useFiles(token, conv.activeConvId)
  const toolLog = useToolLogs(token, conv.activeConvId)
  const usage = useUsage(token)
  const admin = useAdmin(token)
  const insights = useInsights(token)
  const modelParams = useModelParams()
  const search = useSearch(token)
  const auto   = useScheduledPrompts(token)
  const goals  = useGoals(token)
  const integ  = useIntegrations(token)
  const onboarding = useOnboarding(token)
  const notificationPrefs = useNotificationPrefs(token)
  const voice  = useVoice(token, (text) => conv.setInput(text))

  const [userRole, setUserRole] = useState(null)
  const [pendingCalendarWrite, setPendingCalendarWrite] = useState(null)
  const [toastMsg, setToastMsg] = useState(null)

  // new-shell state: dock, palette, telemetry, narrow-screen drawers
  const [dockTab, setDockTab] = useState(null)
  const [dockSub, setDockSub] = useState(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [lastTtft, setLastTtft] = useState(null)
  const [linkFault, setLinkFault] = useState(false)
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 900px)').matches)
  const [railOpen, setRailOpen] = useState(false)

  const importRef = useRef(null)
  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const { send } = useStreamChat({
    token, conv, modelParams, mem, insights, onLogout,
    onCalendarWrite: setPendingCalendarWrite,
    onTtft: setLastTtft, onLinkState: setLinkFault,
  })

  function openDock(tab, sub) {
    setDockTab(tab)
    setDockSub(sub || DOCK_GROUPS[tab]?.[0]?.[0] || null)
  }

  function setDockTabAndDefault(tab) {
    if (tab === null) { setDockTab(null); return }
    openDock(tab)
  }

  // cross-hook: selectConv → settings
  function selectConv(id) {
    const c = conv.selectConv(id)
    if (c) {
      settings.setEditSysPrompt(c.system_prompt || '')
      settings.setEditLockModel(c.locked_model || '')
    }
    if (narrow) setRailOpen(false)
  }

  async function handleAcceptWrite(fact) {
    try {
      const r = await fetch('/api/memory/write', { method:'POST', headers:{...authHeaders,'Content-Type':'application/json'}, body:JSON.stringify({ fact }) })
      if (r.ok) conv.setPendingWriteFact(null)
    } catch { /* ignore */ }
  }

  function handleDismissWrite() {
    conv.setPendingWriteFact(null)
  }

  async function handleAcceptCalendarWrite(calData) {
    try {
      const r = await fetch('/api/integrations/calendar/execute', {
        method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ op: calData.op, args: calData.args })
      })
      if (r.ok) {
        const data = await r.json()
        setPendingCalendarWrite(null)
        setToastMsg(data.summary || 'Calendar event created')
      } else {
        const err = await r.json().catch(() => ({ detail: 'Request failed' }))
        setToastMsg(err.detail || 'Calendar write failed')
      }
    } catch (err) {
      setToastMsg(`Network error: ${err.message}`)
    }
    setTimeout(() => setToastMsg(null), 5000)
  }

  function handleDismissCalendarWrite() {
    setPendingCalendarWrite(null)
  }

  // memory panel derived
  const sections        = useMemo(() => parseMemory(mem.memData?.content), [mem.memData?.content])
  const projectSections = useMemo(() => parseMemory(mem.memData?.project_summary), [mem.memData?.project_summary])
  const hasMemory       = useMemo(() => mem.memData?.content?.trim() || mem.memData?.project_summary?.trim(), [mem.memData])
  const panelSlide      = 'translateX(0)' // legacy; panels render inside the dock now
  const wordCount       = useMemo(() => hasMemory ? ((mem.memData.content||'')+' '+(mem.memData.project_summary||'')).split(/\s+/).filter(Boolean).length : 0, [hasMemory, mem.memData])
  const diffTarget      = useMemo(() => mem.diffIdx !== null ? mem.memHistory[mem.diffIdx] : null, [mem.diffIdx, mem.memHistory])
  const diffLines       = useMemo(() => diffTarget ? computeDiff((diffTarget.content||'')+'\n'+(diffTarget.project_summary||''), (mem.memData?.content||'')+'\n'+(mem.memData?.project_summary||'')) : [], [diffTarget, mem.memData])

  const ctx = { token, conv, mem, settings, files, toolLog, usage, admin, insights, modelParams, search, auto, goals, integ, onboarding, notificationPrefs, voice, hasMemory, sections, projectSections, wordCount, panelSlide, diffTarget, diffLines, importRef, selectConv, handleAcceptWrite, handleDismissWrite, fmtDate }

  // fetch user role on mount
  useEffect(() => {
    fetch('/api/auth/me', { headers: authHeaders })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setUserRole(d.role) }).catch(() => {})
  }, [])

  // auto-dismiss last session banner after 8s
  useEffect(() => {
    if (!conv.lastSession) return
    const tid = setTimeout(() => conv.setLastSession(''), 8000)
    return () => clearTimeout(tid)
  }, [conv.lastSession])

  // Ctrl+K / ⌘K opens the command palette
  useEffect(() => {
    function onKey(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(o => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // narrow-screen tracking (rail/dock collapse to drawers)
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 900px)')
    const onChange = e => setNarrow(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const railStyle = narrow
    ? { position:'absolute', top:0, bottom:0, left:0, zIndex:LAYERS.panel, transform: railOpen ? 'translateX(0)' : 'translateX(-100%)', transition:'transform 0.15s ease-out' }
    : {}
  const dockStyle = narrow
    ? { position:'absolute', top:'34px', bottom:0, right:0, zIndex:LAYERS.panel, maxWidth:'85vw' }
    : {}

  return (
    <PanelPropsCtx.Provider value={ctx}>
      <div style={s.root}>
        <div style={{ display:'flex', flexDirection:'column', flex:1, minWidth:0 }}>
          <TelemetryStrip
            lastTtft={lastTtft} linkFault={linkFault}
            dockTab={dockTab} setDockTab={setDockTabAndDefault}
            onOpenPalette={() => setPaletteOpen(true)}
            onLogout={onLogout} userRole={userRole}
            narrow={narrow} onToggleRail={() => setRailOpen(o => !o)}
          />
          <div style={s.shellBody}>
            <div style={railStyle}>
              {(!narrow || railOpen) && (
                <Sidebar
                  conversations={conv.conversations}
                  activeConvId={conv.activeConvId}
                  selectConv={selectConv}
                  convSearch={conv.convSearch}
                  setConvSearch={conv.setConvSearch}
                  searchResults={conv.searchResults}
                  searchLoading={conv.searchLoading}
                  newChat={conv.newChat}
                  deleteConv={conv.deleteConv}
                  exportConv={conv.exportConv}
                />
              )}
            </div>

            <div style={s.chat}>
              <MessageList
                messages={conv.messages}
                activeConvId={conv.activeConvId}
                bottomRef={conv.bottomRef}
                proactive={conv.proactive}
                setProactive={conv.setProactive}
                setMessages={conv.setMessages}
                pendingWriteFact={conv.pendingWriteFact}
                onAcceptWrite={handleAcceptWrite}
                onDismissWrite={handleDismissWrite}
                lastSession={conv.lastSession}
                pendingCalendarWrite={pendingCalendarWrite}
                onAcceptCalendarWrite={handleAcceptCalendarWrite}
                onDismissCalendarWrite={handleDismissCalendarWrite}
                toastMsg={toastMsg}
                onOpenMemory={() => openDock('mind', 'memory')}
              />

              <ModelToolbar
                selectedModel={modelParams.selectedModel}
                setSelectedModel={modelParams.setSelectedModel}
                compareMode={modelParams.compareMode}
                setCompareMode={modelParams.setCompareMode}
                paramsOpen={modelParams.paramsOpen}
                setParamsOpen={modelParams.setParamsOpen}
                tempEnabled={modelParams.tempEnabled}
                setTempEnabled={modelParams.setTempEnabled}
                temperature={modelParams.temperature}
                setTemperature={modelParams.setTemperature}
                tokensEnabled={modelParams.tokensEnabled}
                setTokensEnabled={modelParams.setTokensEnabled}
                maxTokens={modelParams.maxTokens}
                setMaxTokens={modelParams.setMaxTokens}
                topPEnabled={modelParams.topPEnabled}
                setTopPEnabled={modelParams.setTopPEnabled}
                topP={modelParams.topP}
                setTopP={modelParams.setTopP}
                attachedFiles={files.attachedFiles}
                detachFile={files.detachFile}
                input={conv.input}
                setInput={conv.setInput}
                loading={conv.loading}
                send={send}
                voice={voice}
              />
            </div>

            <div style={dockStyle}>
              <Dock tab={dockTab} sub={dockSub} setTab={setDockTabAndDefault} setSub={setDockSub} userRole={userRole} />
            </div>
          </div>
        </div>

        {settings.settingsOpen && (
          <div style={{ position:'absolute', inset:0, background:'rgba(4,8,14,0.6)', zIndex:LAYERS.settingsModal - 1 }}
            onClick={() => settings.setSettingsOpen(false)} />
        )}

        <SettingsModal />
        <FileViewer />
        <OnboardingModal />
        <CommandPalette
          open={paletteOpen}
          onClose={() => setPaletteOpen(false)}
          openDock={openDock}
          onLogout={onLogout}
        />
      </div>
    </PanelPropsCtx.Provider>
  )
}
