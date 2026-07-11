import { useEffect, useMemo, useRef, useState } from 'react'
import s, { AMBER, NOMINAL, INFOBLUE, TRACK, FG3, FG4 } from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

const SRC_COLORS = { files: AMBER, conversations: INFOBLUE, memory: NOMINAL, graph: TRACK, action: FG3 }

// Ctrl+K palette: unified /api/search across everything + static actions.
// Absorbs the old SearchPanel.
export default function CommandPalette({ open, onClose, openDock, onLogout }) {
  const p = usePanelProps()
  const { search, conv, modelParams, selectConv } = p
  const [sel, setSel] = useState(0)
  const inputRef = useRef(null)
  const q = search.searchQuery

  const actions = useMemo(() => {
    const a = [
      { id: 'new', label: 'New session', run: () => conv.newChat() },
      { id: 'mind', label: 'Open dock · Mind (memory / goals / insights)', run: () => openDock('mind', 'memory') },
      { id: 'files', label: 'Open dock · Files', run: () => openDock('files', 'files') },
      { id: 'ops', label: 'Open dock · Ops (usage / log / automations)', run: () => openDock('ops', 'usage') },
      { id: 'compare', label: `${modelParams.compareMode ? 'Disable' : 'Enable'} compare mode`, run: () => modelParams.setCompareMode(!modelParams.compareMode) },
      { id: 'auto', label: 'Model → Auto routing', run: () => modelParams.setSelectedModel('auto') },
      { id: 'llama', label: 'Model → LLaMA 8B', run: () => modelParams.setSelectedModel('llama') },
      { id: 'coder', label: 'Model → DeepSeek', run: () => modelParams.setSelectedModel('coder') },
      { id: 'reasoning', label: 'Model → GPT-OSS 120B', run: () => modelParams.setSelectedModel('reasoning') },
      { id: 'logout', label: 'Log out', run: onLogout },
    ]
    if (conv.activeConvId) {
      const c = conv.conversations.find(x => x.id === conv.activeConvId)
      a.splice(1, 0, { id: 'export', label: 'Export this conversation (markdown)', run: () => conv.exportConv(conv.activeConvId, c?.title || 'conversation') })
    }
    if (!q.trim()) return a
    const needle = q.toLowerCase()
    return a.filter(x => x.label.toLowerCase().includes(needle))
  }, [q, conv.activeConvId, conv.conversations, modelParams.compareMode])

  const results = search.searchResults?.results || []
  const rows = useMemo(() => [
    ...results.map(r => ({ kind: 'result', ...r })),
    ...actions.map(a => ({ kind: 'action', source: 'action', title: a.label, run: a.run, id: a.id })),
  ], [results, actions])

  useEffect(() => { setSel(0) }, [q, open])
  useEffect(() => {
    if (open) { inputRef.current?.focus(); search.clearSearch() }
  }, [open])
  // window-level Escape — the input handler misses it when focus is elsewhere
  useEffect(() => {
    if (!open) return
    function onEsc(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [open])

  function runRow(row) {
    if (!row) return
    if (row.kind === 'action') row.run()
    else if (row.source === 'conversations') selectConv(row.id)
    else if (row.source === 'files') p.files.viewFile(row.id)
    else if (row.source === 'memory') openDock('mind', 'memory')
    else if (row.source === 'graph') openDock('mind', 'memory')
    onClose()
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSel(i => Math.min(i + 1, rows.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); runRow(rows[sel]) }
    else if (e.key === 'Escape') { e.preventDefault(); onClose() }
  }

  if (!open) return null
  return (
    <div style={s.paletteOverlay} onClick={onClose}>
      <div style={s.palette} onClick={e => e.stopPropagation()}>
        <input ref={inputRef} value={q} onChange={e => search.setSearchQuery(e.target.value)}
          onKeyDown={onKey} placeholder="Search conversations, files, memory — or type a command…"
          style={s.paletteInput} />
        <div style={s.paletteBody}>
          {search.searchLoading && <div style={{ ...s.paletteGroup }}>Searching…</div>}
          {results.length > 0 && <div style={s.paletteGroup}>Results</div>}
          {rows.map((row, i) => (
            <div key={`${row.kind}-${row.source}-${row.id ?? i}`}
              onMouseEnter={() => setSel(i)} onClick={() => runRow(row)}
              style={{ ...s.paletteRow, ...(i === sel ? s.paletteRowOn : {}) }}>
              {row.kind === 'action' && rows[i - 1]?.kind !== 'action' && null}
              <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {row.title}
                {row.snippet && <span style={{ color: FG4, marginLeft: '0.5rem', fontSize: '12px' }}>{row.snippet.slice(0, 60)}</span>}
              </span>
              {row.kind === 'result' && typeof row.score === 'number' && <span style={s.paletteScore}>{row.score.toFixed(2)}</span>}
              <span style={{ ...s.paletteSrc, color: SRC_COLORS[row.source] || FG3 }}>
                {row.source}{row.media_type === 'image' ? ' · img' : ''}
              </span>
            </div>
          ))}
          {rows.length === 0 && <div style={s.paletteGroup}>No matches</div>}
        </div>
        <div style={s.paletteHint}>
          <span>↑↓ navigate</span><span>↵ open</span><span>esc close</span>
        </div>
      </div>
    </div>
  )
}
