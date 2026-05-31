import { useEffect, useRef } from 'react'
import s, { RED, GRN, AMB, CYN, INSET, LINE, FG2, FG4, TERM } from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

const SCOPES = ['all', 'files', 'conversations', 'memory', 'graph']

const SOURCE_COLOR = {
  files:         AMB,
  conversations: RED,
  memory:        GRN,
  graph:         CYN,
}

export default function SearchPanel() {
  const p = usePanelProps()
  const { searchOpen, setSearchOpen, searchQuery, setSearchQuery, searchScope, setSearchScope, searchResults, searchLoading, clearSearch } = p.search
  const { selectConv } = p
  const inputRef = useRef(null)

  useEffect(() => {
    if (searchOpen) setTimeout(() => inputRef.current?.focus(), 60)
  }, [searchOpen])

  const results = searchResults?.results || []
  const grouped = SCOPES.slice(1).reduce((acc, src) => {
    acc[src] = results.filter(r => r.source === src)
    return acc
  }, {})
  const displayGroups = searchScope === 'all'
    ? SCOPES.slice(1).filter(src => grouped[src].length > 0)
    : [searchScope]

  return (
    <div style={{ ...s.toolLogPanel, transform: searchOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.toolLogHdr}>
        <span style={s.toolLogTitle}>🔍 Unified Search</span>
        <button onClick={() => { setSearchOpen(false); clearSearch() }} style={s.closeBtn}>✕</button>
      </div>

      <div style={{ padding:'0.75rem 1.25rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 }}>
        <input
          ref={inputRef}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search across files, conversations, memory…"
          style={{ ...s.sideSearchInput, width:'100%', padding:'0.5rem 0.75rem', fontSize:'0.85rem', marginBottom:'0.6rem', boxSizing:'border-box' }}
        />
        <div style={{ display:'flex', gap:'0.3rem', flexWrap:'wrap' }}>
          {SCOPES.map(sc => (
            <button key={sc} onClick={() => setSearchScope(sc)}
              style={{ ...s.wsPill, ...(searchScope === sc ? s.wsPillActive : {}), textTransform:'capitalize' }}>
              {sc}
            </button>
          ))}
        </div>
      </div>

      <div style={s.toolLogBody}>
        {searchLoading && <p style={s.emptyMem}>Searching…</p>}
        {!searchLoading && searchQuery.trim() && searchResults && results.length === 0 && (
          <p style={s.emptyMem}>No results.</p>
        )}
        {!searchLoading && !searchQuery.trim() && (
          <p style={s.emptyMem}>Type to search.</p>
        )}
        {!searchLoading && displayGroups.map(src => {
          const items = searchScope === 'all' ? grouped[src] : results.filter(r => r.source === src)
          if (!items.length) return null
            const color = SOURCE_COLOR[src] || '#8f8f8f'
          return (
            <div key={src} style={{ marginBottom:'1.25rem' }}>
              <div style={{ fontSize:'0.65rem', fontWeight:700, letterSpacing:'0.08em', color, textTransform:'uppercase', marginBottom:'0.4rem' }}>
                {src}
              </div>
              {items.map((r, i) => (
                <div key={i}
                  onClick={() => { if (src === 'conversations' && r.id) { selectConv(r.id); setSearchOpen(false); clearSearch() } }}
                  style={{ background:INSET, border:`1px solid ${LINE}`, padding:'0.55rem 0.75rem', marginBottom:'6px', cursor: src === 'conversations' ? 'pointer' : 'default' }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'0.5rem', marginBottom:'0.2rem' }}>
                    <span style={{ fontSize:'16px', color:FG2, flex:1, minWidth:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{r.title || '—'}</span>
                    <span style={{ fontSize:'13px', color:FG4, flexShrink:0, fontFamily:TERM }}>{r.score != null ? r.score.toFixed(2) : ''}</span>
                  </div>
                  {r.snippet && (
                    <div style={{ fontSize:'14px', color:FG4, lineHeight:1.45, overflow:'hidden', display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical' }}>
                      {r.snippet}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
