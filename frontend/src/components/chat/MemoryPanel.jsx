import s from '../../lib/chatStyles.js'
import { SECTION_COLORS } from '../../lib/chatConstants.js'
import { fmtDate, parseMemory, computeDiff } from '../../lib/chatUtils.js'

export default function MemoryPanel({
  memOpen, setMemOpen,
  memData, memTab, setMemTab, memLoading, memFlashed,
  memPending, memHistory, histLoading, diffIdx, setDiffIdx,
  editContent, setEditContent, editProj, setEditProj,
  memSaving, hasMemory, sections, projectSections,
  wordCount, panelSlide, diffTarget, diffLines,
  wsMemData, wsMemLoading, wsMemEditing, setWsMemEditing,
  wsMemContent, setWsMemContent, wsMemSaving,
  sidebarWsId,
  pollMemory, loadWsMemory, saveWsMemory,
  openEdit, cancelEdit, saveEdit,
  exportMemory, handleImport,
  activeConvId, convMemEnabled, toggleConvMemory, memToggling,
  importRef, loadGraphStats, graphLoading, graphStats,
  conflicts, conflictsLoading, loadConflicts, resolveConflict,
}) {
  const CONFLICT_BADGE = { contradiction: '#f87171', duplicate: '#fbbf24', ambiguous: '#64748b' }
  return (
    <div style={{ ...s.memPanel, transform: panelSlide }}>
      <div style={s.memHeader}>
        <div style={s.memTitleRow}>
          <div style={s.memTitle}>
            <span>⬡</span> Memory Sheet
            {memData?.version > 0 && <span style={{ fontSize:'0.7rem', color:'#475569', fontWeight:400 }}>v{memData.version}</span>}
          </div>
          <div style={s.memHdrBtns}>
            <button onClick={() => pollMemory(true)} style={s.refreshBtn} disabled={memLoading}>{memLoading ? '…' : '↻'}</button>
            <button onClick={() => setMemOpen(false)} style={s.closeBtn}>✕</button>
          </div>
        </div>
        <div style={s.memMeta}>
          {memPending ? <span style={{ color:'#34d399' }}>updating…</span>
            : memData?.updated_at ? `Updated ${fmtDate(memData.updated_at)}` : 'No memory yet'}
        </div>
      </div>

      <div style={s.tabBar}>
        {['view', ...(sidebarWsId ? ['workspace'] : []), 'edit', 'history', 'graph', 'conflicts'].map(tab => (
          <button key={tab} onClick={() => {
            if (tab === 'edit') openEdit()
            else if (tab === 'workspace') { setMemTab('workspace'); loadWsMemory(sidebarWsId) }
            else if (tab === 'graph') { setMemTab('graph'); loadGraphStats() }
            else if (tab === 'conflicts') { setMemTab('conflicts'); loadConflicts() }
            else setMemTab(tab)
          }}
            style={{ ...s.tabBtn, ...(memTab === tab ? s.tabActive : {}) }}>
            {tab === 'view' ? 'View' : tab === 'edit' ? 'Edit' : tab === 'workspace' ? 'Workspace' : tab === 'graph' ? 'Graph' : tab === 'conflicts' ? `Conflicts${conflicts.length ? ` (${conflicts.length})` : ''}` : 'History'}
          </button>
        ))}
      </div>

      <div style={{ ...s.memBody, ...(memFlashed && memTab === 'view' ? s.flashBody : {}) }}>
        {memTab === 'view' && (
          <>
            {memLoading && !memData && <p style={s.emptyMem}>Loading…</p>}
            {!memLoading && !hasMemory && <p style={s.emptyMem}>No memory yet.<br /><span style={{ fontSize:'0.75rem' }}>Updates after a few exchanges.</span></p>}
            {hasMemory && sections.length === 0 && (memData?.facts?.length > 0 || memData?.content?.trim()) && (
              <div style={{ display:'flex', flexDirection:'column', gap:'0.4rem', marginTop:'0.5rem' }}>
                {(memData.facts?.length > 0
                  ? memData.facts
                  : (memData.content || '').split('\n').filter(Boolean).map(line => ({ content: line }))
                ).map((f, i) => (
                  <div key={i} style={{
                    background:'#0a1220', border:'1px solid #1e293b', borderRadius:'6px',
                    padding:'0.5rem 0.75rem', fontSize:'0.78rem', color:'#cbd5e1', lineHeight:1.5,
                    display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'0.5rem',
                  }}>
                    <span style={{ flex:1 }}>{f.content}</span>
                    {f.salience != null && (
                      <span style={{
                        fontSize:'0.65rem', color: f.salience >= 0.7 ? '#34d399' : f.salience >= 0.4 ? '#fbbf24' : '#475569',
                        flexShrink:0, marginTop:'1px',
                      }}>{Math.min(Math.round(f.salience * 100), 100)}%</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            {sections.map(sec => (
              <div key={sec.name} style={s.section}>
                <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#94a3b8', background: (SECTION_COLORS[sec.name]||'#94a3b8')+'18' }}>{sec.name}</span>
                {sec.pairs.map((p, i) => (
                  <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                ))}
              </div>
            ))}
            {projectSections.length > 0 && (
              <>
                <div style={s.divider}><span style={s.divLabel}>PROJECT STATE</span><div style={{ flex:1, borderTop:'1px solid #1e293b' }} /></div>
                {projectSections.map(sec => (
                  <div key={sec.name} style={s.section}>
                    <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#94a3b8', background: (SECTION_COLORS[sec.name]||'#94a3b8')+'18' }}>{sec.name}</span>
                    {sec.pairs.map((p, i) => (
                      <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                    ))}
                  </div>
                ))}
              </>
            )}
            {sidebarWsId && (
              <>
                <div style={s.divider}><span style={s.divLabel}>WORKSPACE</span><div style={{ flex:1, borderTop:'1px solid #1e293b' }} /></div>
                {wsMemLoading && <p style={s.emptyMem}>Loading…</p>}
                {!wsMemLoading && !wsMemData?.content && <p style={s.emptyMem}>No workspace memory yet.</p>}
                {!wsMemLoading && wsMemData?.content && (() => {
                  const parsed = parseMemory(wsMemData.content)
                  return parsed.length > 0
                    ? parsed.map(sec => (
                        <div key={sec.name} style={s.section}>
                          <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#818cf8', background: (SECTION_COLORS[sec.name]||'#818cf8')+'18' }}>{sec.name}</span>
                          {sec.pairs.map((p, i) => (
                            <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                          ))}
                        </div>
                      ))
                    : wsMemData.content.split('\n').filter(Boolean).map((line, i) => (
                        <div key={i} style={{ background:'#0a1220', border:'1px solid #1e293b', borderRadius:'6px', padding:'0.5rem 0.75rem', fontSize:'0.78rem', color:'#cbd5e1', lineHeight:1.5 }}>{line}</div>
                      ))
                })()}
              </>
            )}
          </>
        )}
        {memTab === 'workspace' && (
          <div>
            {wsMemLoading && <p style={s.emptyMem}>Loading…</p>}
            {!wsMemLoading && !wsMemEditing && (
              <>
                {!wsMemData?.content
                  ? <p style={s.emptyMem}>No workspace memory yet.<br /><span style={{ fontSize:'0.75rem' }}>Updates after exchanges in this workspace.</span></p>
                  : parseMemory(wsMemData.content).map(sec => (
                      <div key={sec.name} style={s.section}>
                        <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||'#94a3b8', background: (SECTION_COLORS[sec.name]||'#94a3b8')+'18' }}>{sec.name}</span>
                        {sec.pairs.map((p, i) => (
                          <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                        ))}
                      </div>
                    ))
                }
                <button onClick={() => { setWsMemContent(wsMemData?.content || ''); setWsMemEditing(true) }}
                  style={{ ...s.actionBtn, marginTop:'0.75rem' }}>Edit</button>
              </>
            )}
            {!wsMemLoading && wsMemEditing && (
              <div>
                <textarea value={wsMemContent} onChange={e => setWsMemContent(e.target.value)}
                  rows={12} style={s.editArea} placeholder="[GOALS]&#10;goal: Build AI workspace" />
                <div style={s.editBtns}>
                  <button onClick={saveWsMemory} disabled={wsMemSaving} style={s.saveBtn}>{wsMemSaving ? 'Saving…' : 'Save'}</button>
                  <button onClick={() => setWsMemEditing(false)} style={s.cancelBtn}>Cancel</button>
                </div>
              </div>
            )}
            {wsMemData?.updated_at && !wsMemEditing && (
              <div style={{ fontSize:'0.68rem', color:'#334155', marginTop:'0.5rem' }}>Updated {fmtDate(wsMemData.updated_at)}</div>
            )}
          </div>
        )}

        {memTab === 'edit' && (
          <div>
            <div style={{ ...s.editLabel, marginTop:0 }}>USER STATE (key: value per line, headers as [SECTION])</div>
            <textarea value={editContent} onChange={e => setEditContent(e.target.value)} rows={10} style={s.editArea} placeholder="[USER]&#10;name: Alice" />
            <div style={s.editLabel}>PROJECT STATE</div>
            <textarea value={editProj} onChange={e => setEditProj(e.target.value)} rows={7} style={s.editArea} placeholder="[GOALS]&#10;goal: Build AI gateway" />
            <div style={s.editBtns}>
              <button onClick={saveEdit} disabled={memSaving} style={s.saveBtn}>{memSaving ? 'Saving…' : 'Save'}</button>
              <button onClick={cancelEdit} style={s.cancelBtn}>Cancel</button>
            </div>
          </div>
        )}
        {memTab === 'history' && (
          <div>
            {histLoading && <p style={s.emptyMem}>Loading…</p>}
            {!histLoading && memHistory.length === 0 && <p style={s.emptyMem}>No history yet.</p>}
            {!histLoading && memHistory.length > 0 && (
              <>
                <div style={{ fontSize:'0.7rem', color:'#475569', marginBottom:'0.75rem' }}>Select a version to diff against current</div>
                <div style={s.historyList}>
                  {memHistory.map((v, i) => (
                    <div key={i} onClick={() => setDiffIdx(diffIdx === i ? null : i)}
                      style={{ ...s.historyItem, borderColor: diffIdx === i ? '#6366f1' : '#1e293b' }}>
                      <span style={{ color:'#cbd5e1' }}>v{v.version}</span>
                      <div style={s.historyMeta}>{fmtDate(v.created_at)}</div>
                    </div>
                  ))}
                </div>
                {diffTarget && (
                  <div style={s.diffBox}>
                    <div style={s.diffTitle}>v{diffTarget.version} → current (v{memData?.version})</div>
                    {diffLines.length === 0 || diffLines.every(d => d.type === 'same')
                      ? <div style={{ ...s.diffLine, ...s.diffSame }}>No changes</div>
                      : diffLines.map((d, i) => (
                        <div key={i} style={{ ...s.diffLine, ...(d.type==='added' ? s.diffAdded : d.type==='removed' ? s.diffRemoved : s.diffSame) }}>
                          {d.type==='added' ? '+ ' : d.type==='removed' ? '− ' : '  '}{d.line}
                        </div>
                      ))
                    }
                  </div>
                )}
              </>
            )}
          </div>
        )}
        {memTab === 'graph' && (
          <div>
            {graphLoading && <p style={s.emptyMem}>Loading…</p>}
            {!graphLoading && graphStats && !graphStats.available && (
              <p style={s.emptyMem}>Graph memory unavailable.<br /><span style={{ fontSize:'0.75rem' }}>Set NEO4J_PASSWORD to enable.</span></p>
            )}
            {!graphLoading && graphStats?.available && (
              <>
                <div style={{ display:'flex', gap:'1rem', marginBottom:'1rem' }}>
                  <div style={{ flex:1, background:'#0a1220', border:'1px solid #1e293b', borderRadius:'8px', padding:'0.75rem', textAlign:'center' }}>
                    <div style={{ fontSize:'1.5rem', fontWeight:700, color:'#818cf8' }}>{graphStats.entities}</div>
                    <div style={{ fontSize:'0.72rem', color:'#475569', marginTop:'2px' }}>Entities</div>
                  </div>
                  <div style={{ flex:1, background:'#0a1220', border:'1px solid #1e293b', borderRadius:'8px', padding:'0.75rem', textAlign:'center' }}>
                    <div style={{ fontSize:'1.5rem', fontWeight:700, color:'#34d399' }}>{graphStats.relations}</div>
                    <div style={{ fontSize:'0.72rem', color:'#475569', marginTop:'2px' }}>Relations</div>
                  </div>
                </div>
                <p style={{ fontSize:'0.72rem', color:'#334155' }}>Graph is built automatically from conversations when memory is enabled.</p>
              </>
            )}
            {!graphLoading && !graphStats && (
              <p style={s.emptyMem}>No data yet.</p>
            )}
            <button onClick={loadGraphStats} style={{ ...s.actionBtn, marginTop:'0.5rem' }} disabled={graphLoading}>↻ Refresh</button>
          </div>
        )}
        {memTab === 'conflicts' && (
          <div>
            {conflictsLoading && <p style={s.emptyMem}>Loading…</p>}
            {!conflictsLoading && conflicts.length === 0 && <p style={s.emptyMem}>No conflicts.</p>}
            {!conflictsLoading && conflicts.map(c => {
              const badgeColor = CONFLICT_BADGE[c.conflict_type] || '#64748b'
              return (
                <div key={c.id} style={{ background:'#0a1220', border:'1px solid #1e293b', borderRadius:'8px', padding:'0.75rem', marginBottom:'0.6rem' }}>
                  <span style={{ fontSize:'0.65rem', fontWeight:600, color: badgeColor, background: badgeColor + '18', borderRadius:'4px', padding:'0.1em 0.45em', letterSpacing:'0.04em', textTransform:'uppercase', marginBottom:'0.5rem', display:'inline-block' }}>{c.conflict_type}</span>
                  <div style={{ display:'flex', gap:'0.5rem', marginBottom:'0.5rem' }}>
                    <div style={{ flex:1, background:'#0f172a', border:'1px solid #1e293b', borderRadius:'6px', padding:'0.5rem 0.65rem', fontSize:'0.78rem', color:'#cbd5e1', lineHeight:1.5 }}>
                      <div style={{ fontSize:'0.62rem', color:'#475569', marginBottom:'0.2rem', fontWeight:600 }}>A</div>
                      {c.fact_a}
                    </div>
                    <div style={{ flex:1, background:'#0f172a', border:'1px solid #1e293b', borderRadius:'6px', padding:'0.5rem 0.65rem', fontSize:'0.78rem', color:'#cbd5e1', lineHeight:1.5 }}>
                      <div style={{ fontSize:'0.62rem', color:'#475569', marginBottom:'0.2rem', fontWeight:600 }}>B</div>
                      {c.fact_b}
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:'0.4rem', flexWrap:'wrap' }}>
                    {[['Keep A','keep_a','#818cf8'],['Keep B','keep_b','#34d399'],['Merge','merge','#fbbf24'],['Discard Both','discard_both','#f87171']].map(([label, strategy, color]) => (
                      <button key={strategy} onClick={() => resolveConflict(c.id, strategy)}
                        style={{ padding:'0.2rem 0.6rem', borderRadius:'5px', border:`1px solid ${color}40`, background:`${color}12`, color, cursor:'pointer', fontSize:'0.75rem', fontWeight:600 }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              )
            })}
            <button onClick={loadConflicts} style={{ ...s.actionBtn, marginTop:'0.5rem' }} disabled={conflictsLoading}>↻ Refresh</button>
          </div>
        )}
      </div>

      <div style={s.memFooter}>
        <div style={s.footerRow}>
          <div style={s.footerActions}>
            <button onClick={exportMemory} style={s.actionBtn}>⬇ Export</button>
            <button onClick={() => importRef.current?.click()} style={s.actionBtn}>⬆ Import</button>
            <input ref={importRef} type="file" accept=".json" style={{ display:'none' }} onChange={handleImport} />
          </div>
          <span style={s.footerStats}>{hasMemory ? `${sections.length+projectSections.length} sec · ${wordCount}w` : 'Empty'}</span>
        </div>
        {activeConvId && (
          <div style={s.memToggleRow}>
            <span style={s.memToggleLabel}>Memory in this conversation</span>
            <button onClick={toggleConvMemory} disabled={memToggling}
              style={{ ...s.togglePill, color: convMemEnabled ? '#34d399' : '#475569', borderColor: convMemEnabled ? '#1e4e3a' : '#334155' }}>
              <span style={{ width:'7px', height:'7px', borderRadius:'50%', background: convMemEnabled ? '#34d399' : '#475569' }} />
              {convMemEnabled ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
