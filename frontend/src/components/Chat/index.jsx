import { useEffect, useMemo, useRef, useState } from 'react'
import s, { LAYERS, RED, GRN, CYN, AMB, FG4, LINE2, DISP, TERM } from '../../lib/chatStyles.js'
import { MODEL_LABELS, MODEL_SUBLABELS } from '../../lib/chatConstants.js'
import { fmtDate, parseMemory, computeDiff } from '../../lib/chatUtils.js'

import useConversations from '../../hooks/useConversations.js'
import useMemory from '../../hooks/useMemory.js'
import useWorkspace from '../../hooks/useWorkspace.js'
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
import useStreamChat from '../../hooks/useStreamChat.js'
import { PanelPropsCtx } from './PanelPropsContext'

import Sidebar from './Sidebar'
import MessageList from './MessageList'
import ModelToolbar from './ModelToolbar'
import SettingsModal from './SettingsModal'
import WorkspaceModal from './WorkspaceModal'
import FilesPanel from './FilesPanel'
import FileViewer from './FileViewer'
import ToolLogPanel from './ToolLogPanel'
import UsagePanel from './UsagePanel'
import InsightsPanel from './InsightsPanel'
import InvitePanel from './InvitePanel'
import MemoryPanel from './MemoryPanel'
import SearchPanel from './SearchPanel'
import AutomationsPanel from './AutomationsPanel'
import GoalsPanel from './GoalsPanel'

export default function Chat({ token, onLogout }) {
  const ws = useWorkspace(token)
  const conv = useConversations(token, ws.sidebarWsId)
  const mem = useMemory(token, ws.sidebarWsId)
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

  const [userRole, setUserRole] = useState(null)

  const importRef = useRef(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const { send } = useStreamChat({ token, conv, modelParams, ws, mem, insights, onLogout })

  function closeAllExcept(...keep) {
    const map = [
      ['mem', mem], ['files', files], ['toolLog', toolLog],
      ['usage', usage], ['insights', insights], ['admin', admin],
      ['search', search], ['auto', auto], ['goals', goals],
    ]
    for (const [key, h] of map) {
      const s = key === 'mem' ? 'setMemOpen' : key === 'files' ? 'setFilesOpen'
        : key === 'toolLog' ? 'setToolLogOpen' : key === 'usage' ? 'setUsageOpen'
        : key === 'insights' ? 'setInsightsOpen' : key === 'admin' ? 'setInviteOpen'
        : key === 'search' ? 'setSearchOpen' : key === 'auto' ? 'setAutoOpen'
        : 'setGoalsOpen'
      if (!keep.includes(key)) h[s](false)
    }
  }

  // cross-hook: sidebarWsId reset
  useEffect(() => {
    if (!ws.sidebarWsId && mem.memTab === 'workspace') mem.setMemTab('view')
  }, [ws.sidebarWsId])

  // cross-hook: selectConv → settings
  function selectConv(id) {
    const c = conv.selectConv(id)
    if (c) {
      settings.setEditSysPrompt(c.system_prompt || '')
      settings.setEditLockModel(c.locked_model || '')
      settings.setEditWsId(c.workspace_id || '')
    }
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

  // memory panel derived
  const sections        = useMemo(() => parseMemory(mem.memData?.content), [mem.memData?.content])
  const projectSections = useMemo(() => parseMemory(mem.memData?.project_summary), [mem.memData?.project_summary])
  const hasMemory       = useMemo(() => mem.memData?.content?.trim() || mem.memData?.project_summary?.trim(), [mem.memData])
  const panelSlide      = mem.memOpen ? 'translateX(0)' : 'translateX(100%)'
  const wordCount       = useMemo(() => hasMemory ? ((mem.memData.content||'')+' '+(mem.memData.project_summary||'')).split(/\s+/).filter(Boolean).length : 0, [hasMemory, mem.memData])
  const diffTarget      = useMemo(() => mem.diffIdx !== null ? mem.memHistory[mem.diffIdx] : null, [mem.diffIdx, mem.memHistory])
  const diffLines       = useMemo(() => diffTarget ? computeDiff((diffTarget.content||'')+'\n'+(diffTarget.project_summary||''), (mem.memData?.content||'')+'\n'+(mem.memData?.project_summary||'')) : [], [diffTarget, mem.memData])

  const ctx = { token, conv, mem, ws, settings, files, toolLog, usage, admin, insights, modelParams, search, auto, goals, hasMemory, sections, projectSections, wordCount, panelSlide, diffTarget, diffLines, importRef, selectConv, handleAcceptWrite, handleDismissWrite, fmtDate }

  const lockedModelLabel = conv.convLockModel
    ? (MODEL_LABELS[conv.convLockModel] || conv.convLockModel)
    : null

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

  const anyOpen = mem.memOpen || files.filesOpen || settings.settingsOpen || toolLog.toolLogOpen || usage.usageOpen || admin.inviteOpen || insights.insightsOpen || ws.wsModalOpen || search.searchOpen || auto.autoOpen || goals.goalsOpen

  return (
    <div style={s.root}>
      {/* CSS is now in index.html <style> block */}

      <Sidebar
        conversations={conv.conversations}
        activeConvId={conv.activeConvId}
        selectConv={selectConv}
        sidebarWsList={ws.sidebarWsList}
        sidebarWsId={ws.sidebarWsId}
        setSidebarWsId={ws.setSidebarWsId}
        convSearch={conv.convSearch}
        setConvSearch={conv.setConvSearch}
        searchResults={conv.searchResults}
        searchLoading={conv.searchLoading}
        newChat={conv.newChat}
        deleteConv={conv.deleteConv}
        exportConv={conv.exportConv}
        openCreateWs={ws.openCreateWs}
        openEditWs={ws.openEditWs}
      />

      <div style={s.chat}>
        <header style={s.header}>
          <span style={s.title}>
            NIM // GATEWAY
            {lockedModelLabel && <span style={{ fontSize:'14px', color:RED, marginLeft:'0.5rem', fontFamily:DISP }}>🔒 {lockedModelLabel}</span>}
          </span>
          <div style={s.headerRight}>
            {conv.activeConvId && (
              <button onClick={() => settings.setSettingsOpen(true)} style={s.hdrBtn} title="Conversation settings">⚙</button>
            )}
            <button onClick={() => { closeAllExcept(); usage.setUsageOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(usage.usageOpen ? { color:GRN, borderColor:GRN } : {}) }}
              title="Token usage & cost">
              $ Usage
            </button>
            <button onClick={() => { closeAllExcept(); toolLog.setToolLogOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(toolLog.toolLogOpen ? { color:CYN, borderColor:CYN } : {}) }}
              title="AI tool call history">
              🔧 Log
            </button>
            <button onClick={() => { closeAllExcept(); files.setFilesOpen(true) }} style={{ ...s.hdrBtn, ...(files.attachedFiles.length > 0 ? { color:AMB, borderColor:AMB } : {}) }}>
              {files.attachedFiles.length > 0 ? `📎 ${files.attachedFiles.length}` : '📎'} Files
            </button>
            <button onClick={() => { closeAllExcept(); search.setSearchOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(search.searchOpen ? { color:CYN, borderColor:CYN } : {}) }}
              title="Unified search">
              🔍
            </button>
            <button onClick={() => { closeAllExcept(); auto.setAutoOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(auto.autoOpen ? { color:CYN, borderColor:CYN } : {}) }}
              title="Scheduled automations">
              ⏱ Auto
            </button>
            <button onClick={() => { closeAllExcept(); goals.setGoalsOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(goals.goalsOpen ? { color:GRN, borderColor:GRN } : {}) }}
              title="Goals & tasks">
              🎯 Goals
            </button>
            <button onClick={() => { closeAllExcept('mem'); mem.setMemOpen(true) }} style={s.hdrBtn}>
              {mem.memPending ? <span style={s.updatingDot} /> : hasMemory && <span style={s.memDot} />}
              Memory
            </button>
            <button onClick={() => { closeAllExcept(); insights.setInsightsOpen(o => !o) }}
              style={{ ...s.hdrBtn, ...(insights.insightsOpen ? { color:CYN, borderColor:CYN } : {}) }}
              title="AI insights about you">
              💡{insights.unreadCount > 0 && <span style={s.unreadBadge}>{insights.unreadCount}</span>}
            </button>
            {userRole === 'admin' && (
              <button onClick={() => { closeAllExcept(); admin.setInviteOpen(o => !o) }}
                style={{ ...s.hdrBtn, ...(admin.inviteOpen ? { color:CYN, borderColor:CYN } : {}) }}
                title="Manage invite tokens">
                ⚡ Invites
              </button>
            )}
            <button onClick={onLogout} style={s.logout}>Logout</button>
          </div>
        </header>

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
        />
      </div>

      {anyOpen && (
        <div style={{ ...s.overlay, zIndex: (settings.settingsOpen || ws.wsModalOpen) ? LAYERS.wsModal - 1 : LAYERS.overlay }}
          onClick={() => {
            if (ws.wsModalOpen) ws.setWsModalOpen(false)
            else if (settings.settingsOpen) settings.setSettingsOpen(false)
            else closeAllExcept()
          }} />
      )}

      <PanelPropsCtx.Provider value={ctx}>
        <SettingsModal />
        <WorkspaceModal />
        <FilesPanel />
        <FileViewer />
        <ToolLogPanel />
        <UsagePanel />
        <InsightsPanel />
        <InvitePanel />
        <SearchPanel />
        <GoalsPanel />
        <AutomationsPanel />
        <MemoryPanel />
      </PanelPropsCtx.Provider>
    </div>
  )
}
