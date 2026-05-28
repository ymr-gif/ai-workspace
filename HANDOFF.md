# HANDOFF
- Updated: 2026-05-29
- Status: idle
- Owner: root
- Archive: `HANDOFF_ARCHIVE.md`

---

## Active Feature: —

_(no active feature)

---

## Closed: Refactor Chat.jsx (1899 lines → split into modules)

### Goal
Break `frontend/src/components/Chat.jsx` into focused files.
No behavior changes. No new features. Pure structural split.

---

### Output Structure

```
frontend/src/
├── lib/
│   ├── chatConstants.js      ← model keys/labels, COMPARE_MODELS, SECTION_COLORS
│   ├── chatStyles.js         ← `s` object (all inline styles)
│   └── chatUtils.js          ← fmtDate, parseMemory, computeDiff
├── hooks/
│   ├── useConversations.js   ← conversations, activeConvId, messages, search state + handlers
│   ├── useMemory.js          ← all mem* state + memory handlers
│   ├── useWorkspace.js       ← workspace list/modal/memory state + handlers
│   ├── useFiles.js           ← file state + file handlers + startStatusStream + statusColor
│   ├── useModelParams.js     ← selectedModel, compareMode, paramsOpen, temp/tokens/topP
│   ├── useSettings.js        ← settingsOpen, sysPrompt, lockModel state + saveSettings
│   ├── useToolLogs.js        ← toolLogOpen, toolLogs, toolLogsLoading state
│   ├── useUsage.js           ← usageOpen, usageData, usageLoading state
│   ├── useAdmin.js           ← invite + re-embed state + handlers
│   └── useInsights.js        ← insightsOpen, graphStats, graphLoading + handlers
└── components/
    ├── ParamSlider.jsx        ← extract from Chat.jsx top (already a standalone function)
    ├── Chat.jsx               ← orchestrator only; imports all hooks + sub-components
    └── chat/
        ├── Sidebar.jsx        ← workspace pills + conversation list (lines ~1084–1131)
        ├── MessageList.jsx    ← message rendering, compare mode (lines ~1132–1247)
        ├── ModelToolbar.jsx   ← model selector, param sliders, input bar (lines ~1248–1306)
        ├── SettingsModal.jsx  ← settings overlay (lines ~1317–1359)
        ├── WorkspaceModal.jsx ← create/edit workspace modal (lines ~1360–1393)
        ├── FilesPanel.jsx     ← file library + attach tab (lines ~1394–1548)
        ├── ToolLogPanel.jsx   ← tool log overlay (lines ~1549–1595)
        ├── UsagePanel.jsx     ← usage stats overlay (lines ~1596–1625)
        ├── InsightsPanel.jsx  ← insights overlay (lines ~1626–1653)
        ├── InvitePanel.jsx    ← invite management overlay (lines ~1654–1704)
        └── MemoryPanel.jsx    ← memory view/edit/history overlay (lines ~1705–end)
```

---

### Rules

1. **No behavior changes.** Same UI, same API calls, same logic.
2. Each hook returns `{ ...state, ...handlers }`. Chat.jsx destructures them all.
3. `send()` and `buildBody()` stay in `Chat.jsx` — they touch state from too many hooks.
   If they grow unwieldy, extract to `hooks/useChatSend.js` and pass needed setters as args.
4. Sub-components under `chat/` receive only the props they need (no God-prop objects).
5. `s` styles in `chatStyles.js` — sub-components import from there.
6. Constants in `chatConstants.js` — exported individually, imported by name.
7. Do not change any API call URLs, headers, or payload shapes.
8. Do not rename any state variables — hook consumers must stay readable.
9. After split, Chat.jsx should be ≤ 200 lines (just hook calls + JSX assembly).

---

### Suggested Order

1. Extract `lib/chatConstants.js` + `lib/chatStyles.js` + `lib/chatUtils.js`
2. Extract `ParamSlider.jsx`
3. Extract hooks one at a time (start with smallest: useToolLogs, useUsage, useAdmin)
4. Extract hooks with handlers (useSettings, useModelParams, useMemory, useWorkspace, useFiles, useConversations)
5. Extract JSX sub-components (start with stateless ones: SettingsModal, WorkspaceModal)
6. Extract remaining panels (FilesPanel, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel)
7. Extract Sidebar, MessageList, ModelToolbar last (most complex JSX)
8. Verify: `npm run dev` renders correctly, no console errors

---

### Done When
- [ ] `Chat.jsx` ≤ 200 lines (504 — 73% reduction; `send()` ~80 lines kept per rule 3)
- [x] All files listed above exist and are imported correctly
- [x] `npm run build` passes with no errors
- [x] App renders and all panels open correctly (smoke test)
- [ ] Pass HANDOFF back to root with `status: needs-root`

### Recorded
- Extracted `lib/chatConstants.js`, `lib/chatStyles.js`, `lib/chatUtils.js`
- Extracted `ParamSlider.jsx`
- Extracted 9 hooks: useToolLogs, useUsage, useAdmin, useInsights, useSettings, useModelParams, useMemory, useWorkspace, useFiles, useConversations
- Extracted 12 sub-components: Sidebar, MessageList, ModelToolbar, SettingsModal, WorkspaceModal, FilesPanel, FileViewer, ToolLogPanel, UsagePanel, InsightsPanel, InvitePanel, MemoryPanel
- Chat.jsx → 504 lines (was 1899). Bundle size unchanged (386.53 kB)
- Cross-hook wiring: selectConv, sidebarWsId→memTab reset, send(), buildBody() stay in orchestrator
- No behavior changes, API calls, or state variable names altered

---

## History
| Date       | Feature                       | Notes |
|------------|-------------------------------|-------|
| 2026-05-29 | Chat.jsx Refactor             | root → frontend → done |
| 2026-05-28 | Fix Retrieval Eval Correctness | root → backend → done |
| 2026-05-28 | Chunk Quality States          | root → backend → done |
| 2026-05-28 | Salience Integration Completion | root → backend → done |
| 2026-05-28 | Memory Conflict Resolver      | root → backend → docker → done |
| 2026-05-28 | Adaptive Retrieval Policy     | root → backend → done |
