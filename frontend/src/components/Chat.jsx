import { useEffect, useRef, useState } from 'react'
import s from '../lib/chatStyles.js'
import { MODEL_KEYS, MODEL_LABELS, MODEL_SUBLABELS } from '../lib/chatConstants.js'
import { fmtDate, parseMemory, computeDiff } from '../lib/chatUtils.js'

import useConversations from '../hooks/useConversations.js'
import useMemory from '../hooks/useMemory.js'
import useWorkspace from '../hooks/useWorkspace.js'
import useFiles from '../hooks/useFiles.js'
import useModelParams from '../hooks/useModelParams.js'
import useSettings from '../hooks/useSettings.js'
import useToolLogs from '../hooks/useToolLogs.js'
import useUsage from '../hooks/useUsage.js'
import useAdmin from '../hooks/useAdmin.js'
import useInsights from '../hooks/useInsights.js'

import Sidebar from './chat/Sidebar.jsx'
import MessageList from './chat/MessageList.jsx'
import ModelToolbar from './chat/ModelToolbar.jsx'
import SettingsModal from './chat/SettingsModal.jsx'
import WorkspaceModal from './chat/WorkspaceModal.jsx'
import FilesPanel from './chat/FilesPanel.jsx'
import FileViewer from './chat/FileViewer.jsx'
import ToolLogPanel from './chat/ToolLogPanel.jsx'
import UsagePanel from './chat/UsagePanel.jsx'
import InsightsPanel from './chat/InsightsPanel.jsx'
import InvitePanel from './chat/InvitePanel.jsx'
import MemoryPanel from './chat/MemoryPanel.jsx'

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

  const [userRole, setUserRole] = useState(null)

  const importRef = useRef(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

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

  // build request body
  function buildBody(text) {
    const body = { message: text, conversation_id: conv.activeConvId, workspace_id: ws.sidebarWsId }
    if (modelParams.selectedModel !== 'auto') body.model_override = modelParams.selectedModel
    if (modelParams.compareMode) body.compare = true
    if (modelParams.tempEnabled)   body.temperature = modelParams.temperature
    if (modelParams.tokensEnabled) body.max_tokens  = modelParams.maxTokens
    if (modelParams.topPEnabled)   body.top_p       = modelParams.topP
    return body
  }

  async function send(e) {
    e.preventDefault()
    const text = conv.input.trim(); if (!text || conv.loading) return
    const isCompare = modelParams.compareMode
    const userId = conv.nextId.current++, aiId = conv.nextId.current++
    conv.setInput(''); conv.setLoading(true); conv.setProactive(null); conv.setPendingWriteFact(null)

    if (isCompare) {
      conv.setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'compare', responses: Object.fromEntries(Object.values(MODEL_KEYS).map(m => [m, { text: '', streaming: true }])) },
      ])
    } else {
      conv.setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'ai', text: '', model: null, streaming: true },
      ])
    }

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(text)),
      })
      if (res.status === 401) { onLogout(); return }
      if (!res.ok) {
        conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: 'Request failed', streaming: false } : m))
        return
      }

      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n'); buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim(); if (!raw) continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              if (isCompare) {
                const model = event.model
                conv.setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: { ...m.responses, [model]: { ...m.responses[model], text: (m.responses[model]?.text||'') + event.content } } }
                  : m))
              } else {
                conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, text: m.text + event.content } : m))
              }
            } else if (event.type === 'done') {
              if (isCompare) {
                conv.setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: Object.fromEntries(Object.entries(m.responses).map(([k,v]) => [k, { ...v, streaming: false }])) }
                  : m))
              } else {
                conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, model: event.model, streaming: false, promptTokens: event.prompt_tokens, completionTokens: event.completion_tokens, totalTokens: event.total_tokens, costUsd: event.cost_usd } : m))
                mem.setMemTick(t => t + 1)
                setTimeout(() => { if (mem.memTab === 'graph') insights.loadGraphStats() }, 2000)
              }
              const cid = event.conversation_id
              if (cid) {
                conv.setActiveConvId(cid)
                conv.setConversations(prev => {
                  const exists = prev.find(c => c.id === cid)
                  if (exists) return [{ ...exists, updated_at: new Date().toISOString() }, ...prev.filter(c => c.id !== cid)]
                  return [{ id: cid, title: text.slice(0, 60), updated_at: new Date().toISOString(), memory_enabled: true, system_prompt: '', locked_model: '', workspace_id: ws.sidebarWsId }, ...prev]
                })
              }
            } else if (event.type === 'tool_call') {
              conv.setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, toolCalls: [...(m.toolCalls || []), { name: event.name, args: event.args, result: null }] }
                : m))
            } else if (event.type === 'tool_result') {
              conv.setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, toolCalls: (m.toolCalls || []).map((tc, i) =>
                    i === (m.toolCalls.length - 1) ? { ...tc, result: event.content } : tc
                  )}
                : m))
            } else if (event.type === 'ask_user') {
              conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, askUser: event.question } : m))
            } else if (event.type === 'confirm_write_memory') {
              conv.setPendingWriteFact(event.fact)
            } else if (event.type === 'proactive') {
              conv.setProactive(event.content)
            } else if (event.type === 'error') {
              conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: event.message || 'Error', streaming: false } : m))
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err) {
      conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: `Network error: ${err.message}`, streaming: false } : m))
    } finally { conv.setLoading(false) }
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
  const sections        = parseMemory(mem.memData?.content)
  const projectSections = parseMemory(mem.memData?.project_summary)
  const hasMemory       = mem.memData?.content?.trim() || mem.memData?.project_summary?.trim()
  const panelSlide      = mem.memOpen ? 'translateX(0)' : 'translateX(100%)'
  const wordCount       = hasMemory ? ((mem.memData.content||'')+' '+(mem.memData.project_summary||'')).split(/\s+/).filter(Boolean).length : 0
  const diffTarget      = mem.diffIdx !== null ? mem.memHistory[mem.diffIdx] : null
  const diffLines       = diffTarget ? computeDiff((diffTarget.content||'')+'\n'+(diffTarget.project_summary||''), (mem.memData?.content||'')+'\n'+(mem.memData?.project_summary||'')) : []

  const lockedModelLabel = conv.convLockModel
    ? (MODEL_LABELS[conv.convLockModel] || conv.convLockModel)
    : null

  // fetch user role on mount
  useEffect(() => {
    fetch('/api/auth/me', { headers: authHeaders })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setUserRole(d.role) }).catch(() => {})
  }, [])

  const anyOpen = mem.memOpen || files.filesOpen || settings.settingsOpen || toolLog.toolLogOpen || usage.usageOpen || admin.inviteOpen || insights.insightsOpen || ws.wsModalOpen

  return (
    <div style={s.root}>
      <style>{`
        @keyframes blink    { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes pulse    { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes memFlash { 0%{background:rgba(52,211,153,0.08)} 100%{background:transparent} }
        ::-webkit-scrollbar       { width:4px }
        ::-webkit-scrollbar-track { background:transparent }
        ::-webkit-scrollbar-thumb { background:#1e293b; border-radius:2px }
        textarea:focus { border-color:#6366f1 !important }
        input[type=range] { height:4px }
        .md-body { font-size:inherit; line-height:1.6; color:inherit; word-break:break-word }
        .md-body p { margin:0 0 0.6em }
        .md-body p:last-child { margin-bottom:0 }
        .md-body h1,.md-body h2,.md-body h3,.md-body h4 { margin:0.8em 0 0.35em; font-weight:700; line-height:1.3 }
        .md-body h1 { font-size:1.2em } .md-body h2 { font-size:1.1em } .md-body h3 { font-size:1em }
        .md-body ul,.md-body ol { margin:0.4em 0 0.6em 1.4em; padding:0 }
        .md-body li { margin-bottom:0.2em }
        .md-body code { background:#0f172a; border:1px solid #1e293b; border-radius:4px; padding:0.1em 0.35em; font-family:monospace; font-size:0.85em; color:#93c5fd }
        .md-body pre { background:#0f172a; border:1px solid #1e293b; border-radius:6px; padding:0.75em 1em; overflow-x:auto; margin:0.5em 0 }
        .md-body pre code { background:none; border:none; padding:0; font-size:0.82em; color:#94a3b8 }
        .md-body blockquote { border-left:3px solid #334155; margin:0.5em 0; padding:0.2em 0.75em; color:#94a3b8 }
        .md-body table { border-collapse:collapse; width:100%; margin:0.5em 0; font-size:0.85em }
        .md-body th,.md-body td { border:1px solid #1e293b; padding:0.3em 0.6em; text-align:left }
        .md-body th { background:#1e293b; color:#cbd5e1; font-weight:600 }
        .md-body a { color:#818cf8; text-decoration:underline }
        .md-body strong { color:#e2e8f0; font-weight:700 }
        .md-body em { color:#cbd5e1 }
        .md-body hr { border:none; border-top:1px solid #1e293b; margin:0.75em 0 }
      `}</style>

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
            NIM AI Gateway
            {lockedModelLabel && <span style={{ fontSize:'0.72rem', color:'#6366f1', marginLeft:'0.5rem', fontWeight:400 }}>🔒 {lockedModelLabel}</span>}
          </span>
          <div style={s.headerRight}>
            {conv.activeConvId && (
              <button onClick={conv.toggleConvMemory} disabled={conv.memToggling} title={conv.convMemEnabled ? 'Context ON' : 'Context OFF'}
                style={{ ...s.hdrBtn, color: conv.convMemEnabled ? '#34d399' : '#475569', borderColor: conv.convMemEnabled ? '#1e4e3a' : '#334155' }}>
                {conv.convMemEnabled ? '◉' : '○'} Ctx
              </button>
            )}
            {conv.activeConvId && (
              <button onClick={() => settings.setSettingsOpen(true)} style={s.hdrBtn} title="Conversation settings">⚙</button>
            )}
            <button onClick={() => { usage.setUsageOpen(o => !o); toolLog.setToolLogOpen(false); mem.setMemOpen(false); files.setFilesOpen(false) }}
              style={{ ...s.hdrBtn, ...(usage.usageOpen ? { color:'#34d399', borderColor:'#1e4e3a' } : {}) }}
              title="Token usage & cost">
              $ Usage
            </button>
            <button onClick={() => { toolLog.setToolLogOpen(o => !o); mem.setMemOpen(false); files.setFilesOpen(false); usage.setUsageOpen(false) }}
              style={{ ...s.hdrBtn, ...(toolLog.toolLogOpen ? { color:'#818cf8', borderColor:'#4338ca' } : {}) }}
              title="AI tool call history">
              🔧 Log
            </button>
            <button onClick={() => { files.setFilesOpen(true); mem.setMemOpen(false); toolLog.setToolLogOpen(false) }} style={{ ...s.hdrBtn, ...(files.attachedFiles.length > 0 ? { color:'#fbbf24', borderColor:'#78350f' } : {}) }}>
              {files.attachedFiles.length > 0 ? `📎 ${files.attachedFiles.length}` : '📎'} Files
            </button>
            <button onClick={() => { mem.setMemOpen(true); files.setFilesOpen(false) }} style={s.hdrBtn}>
              {mem.memPending ? <span style={s.updatingDot} /> : hasMemory && <span style={s.memDot} />}
              Memory
            </button>
            <button onClick={() => { insights.setInsightsOpen(o => !o); mem.setMemOpen(false); files.setFilesOpen(false); toolLog.setToolLogOpen(false); usage.setUsageOpen(false); admin.setInviteOpen(false) }}
              style={{ ...s.hdrBtn, ...(insights.insightsOpen ? { color:'#818cf8', borderColor:'#4338ca' } : {}) }}
              title="AI insights about you">
              💡{insights.unreadCount > 0 && <span style={s.unreadBadge}>{insights.unreadCount}</span>}
            </button>
            {userRole === 'admin' && (
              <button onClick={() => { admin.setInviteOpen(o => !o); mem.setMemOpen(false); files.setFilesOpen(false); toolLog.setToolLogOpen(false); usage.setUsageOpen(false); insights.setInsightsOpen(false) }}
                style={{ ...s.hdrBtn, ...(admin.inviteOpen ? { color:'#818cf8', borderColor:'#4338ca' } : {}) }}
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
        <div style={{ ...s.overlay, zIndex: (settings.settingsOpen || ws.wsModalOpen) ? 21 : 10 }}
          onClick={() => {
            if (ws.wsModalOpen) ws.setWsModalOpen(false)
            else if (settings.settingsOpen) settings.setSettingsOpen(false)
            else { mem.setMemOpen(false); files.setFilesOpen(false); toolLog.setToolLogOpen(false); usage.setUsageOpen(false); admin.setInviteOpen(false); insights.setInsightsOpen(false) }
          }} />
      )}

      <SettingsModal
        settingsOpen={settings.settingsOpen}
        setSettingsOpen={settings.setSettingsOpen}
        editSysPrompt={settings.editSysPrompt}
        setEditSysPrompt={settings.setEditSysPrompt}
        editLockModel={settings.editLockModel}
        setEditLockModel={settings.setEditLockModel}
        editWsId={settings.editWsId}
        setEditWsId={settings.setEditWsId}
        sidebarWsList={ws.sidebarWsList}
        saveSettings={settings.saveSettings}
        settingsSaving={settings.settingsSaving}
      />

      <WorkspaceModal
        wsModalOpen={ws.wsModalOpen}
        setWsModalOpen={ws.setWsModalOpen}
        wsModalTarget={ws.wsModalTarget}
        wsFieldName={ws.wsFieldName}
        setWsFieldName={ws.setWsFieldName}
        wsFieldDesc={ws.wsFieldDesc}
        setWsFieldDesc={ws.setWsFieldDesc}
        wsFieldSys={ws.wsFieldSys}
        setWsFieldSys={ws.setWsFieldSys}
        saveWsModal={ws.saveWsModal}
        deleteWs={ws.deleteWs}
        wsSaving={ws.wsSaving}
      />

      <FilesPanel
        filesOpen={files.filesOpen}
        setFilesOpen={files.setFilesOpen}
        filesTab={files.filesTab}
        setFilesTab={files.setFilesTab}
        libFiles={files.libFiles}
        attachedFiles={files.attachedFiles}
        workspaces={files.workspaces}
        wsFilter={files.wsFilter}
        setWsFilter={files.setWsFilter}
        fileUploading={files.fileUploading}
        urlIngest={files.urlIngest}
        setUrlIngest={files.setUrlIngest}
        urlIngesting={files.urlIngesting}
        renameId={files.renameId}
        setRenameId={files.setRenameId}
        renameVal={files.renameVal}
        setRenameVal={files.setRenameVal}
        fileInputRef={files.fileInputRef}
        attachedIds={files.attachedIds}
        uploadFile={files.uploadFile}
        ingestUrl={files.ingestUrl}
        attachFile={files.attachFile}
        detachFile={files.detachFile}
        viewFile={files.viewFile}
        downloadFile={files.downloadFile}
        deleteFile={files.deleteFile}
        commitRename={files.commitRename}
        statusColor={files.statusColor}
        activeConvId={conv.activeConvId}
      />

      <FileViewer
        fileViewer={files.fileViewer}
        setFileViewer={files.setFileViewer}
        viewerTab={files.viewerTab}
        setViewerTab={files.setViewerTab}
        viewerEdit={files.viewerEdit}
        setViewerEdit={files.setViewerEdit}
        viewerSaving={files.viewerSaving}
        viewerVersions={files.viewerVersions}
        viewerVerLoading={files.viewerVerLoading}
        downloadFile={files.downloadFile}
        saveFileEdit={files.saveFileEdit}
        loadFileVersions={files.loadFileVersions}
        restoreFileVersion={files.restoreFileVersion}
        fmtDate={fmtDate}
      />

      <ToolLogPanel
        toolLogOpen={toolLog.toolLogOpen}
        setToolLogOpen={toolLog.setToolLogOpen}
        toolLogs={toolLog.toolLogs}
        toolLogsLoading={toolLog.toolLogsLoading}
        loadToolLogs={toolLog.loadToolLogs}
        activeConvId={conv.activeConvId}
      />

      <UsagePanel
        usageOpen={usage.usageOpen}
        setUsageOpen={usage.setUsageOpen}
        usageData={usage.usageData}
        usageLoading={usage.usageLoading}
        loadUsage={usage.loadUsage}
      />

      <InsightsPanel
        insightsOpen={insights.insightsOpen}
        setInsightsOpen={insights.setInsightsOpen}
        insights={insights.insights}
        insightsLoading={insights.insightsLoading}
        loadInsights={insights.loadInsights}
        markInsightRead={insights.markInsightRead}
        deleteInsight={insights.deleteInsight}
      />

      <InvitePanel
        inviteOpen={admin.inviteOpen}
        setInviteOpen={admin.setInviteOpen}
        inviteList={admin.inviteList}
        inviteLoading={admin.inviteLoading}
        newToken={admin.newToken}
        tokenGenerating={admin.tokenGenerating}
        loadInvites={admin.loadInvites}
        generateInvite={admin.generateInvite}
        reEmbedding={admin.reEmbedding}
        reEmbedMsg={admin.reEmbedMsg}
        triggerReEmbed={admin.triggerReEmbed}
      />

      <MemoryPanel
        memOpen={mem.memOpen}
        setMemOpen={mem.setMemOpen}
        memData={mem.memData}
        memTab={mem.memTab}
        setMemTab={mem.setMemTab}
        memLoading={mem.memLoading}
        memFlashed={mem.memFlashed}
        memPending={mem.memPending}
        memHistory={mem.memHistory}
        histLoading={mem.histLoading}
        diffIdx={mem.diffIdx}
        setDiffIdx={mem.setDiffIdx}
        editContent={mem.editContent}
        setEditContent={mem.setEditContent}
        editProj={mem.editProj}
        setEditProj={mem.setEditProj}
        memSaving={mem.memSaving}
        hasMemory={hasMemory}
        sections={sections}
        projectSections={projectSections}
        wordCount={wordCount}
        panelSlide={panelSlide}
        diffTarget={diffTarget}
        diffLines={diffLines}
        wsMemData={mem.wsMemData}
        wsMemLoading={mem.wsMemLoading}
        wsMemEditing={mem.wsMemEditing}
        setWsMemEditing={mem.setWsMemEditing}
        wsMemContent={mem.wsMemContent}
        setWsMemContent={mem.setWsMemContent}
        wsMemSaving={mem.wsMemSaving}
        sidebarWsId={ws.sidebarWsId}
        pollMemory={mem.pollMemory}
        loadWsMemory={mem.loadWsMemory}
        saveWsMemory={mem.saveWsMemory}
        openEdit={mem.openEdit}
        cancelEdit={mem.cancelEdit}
        saveEdit={mem.saveEdit}
        exportMemory={mem.exportMemory}
        handleImport={mem.handleImport}
        activeConvId={conv.activeConvId}
        convMemEnabled={conv.convMemEnabled}
        toggleConvMemory={conv.toggleConvMemory}
        memToggling={conv.memToggling}
        importRef={importRef}
        loadGraphStats={insights.loadGraphStats}
        graphLoading={insights.graphLoading}
        graphStats={insights.graphStats}
      />
    </div>
  )
}
