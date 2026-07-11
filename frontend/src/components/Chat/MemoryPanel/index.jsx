import { useState } from 'react'
import s, { RED, GRN, AMB, CYN, FG1, FG2, FG3, FG4, FG5, LINE, LINE2, INSET, DISP, TERM } from '../../../lib/chatStyles.js'
import { SECTION_COLORS } from '../../../lib/chatConstants.js'
import { fmtDate, parseMemory, computeDiff } from '../../../lib/chatUtils.js'
import { usePanelProps } from '../PanelPropsContext.js'

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000
  if (diff < 60)    return 'just now'
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function MemoryPanel() {
  const p = usePanelProps()
  const { memOpen, setMemOpen, memData, memTab, setMemTab, memLoading, memFlashed, memPending, memHistory, histLoading, diffIdx, setDiffIdx, editContent, setEditContent, editProj, setEditProj, memSaving, pollMemory, openEdit, cancelEdit, saveEdit, exportMemory, handleImport, conflicts, conflictsLoading, loadConflicts, resolveConflict } = p.mem
  const { activeConvId } = p.conv
  const { loadGraphStats, graphLoading, graphStats, graphSample, graphSampleLoading, loadGraphSample } = p.insights
  const { hasMemory, sections, projectSections, wordCount, panelSlide, diffTarget, diffLines, importRef } = p
  const CONFLICT_BADGE = { contradiction: RED, duplicate: AMB, ambiguous: FG4 }
  const [selectedNode, setSelectedNode] = useState(null)
  const [graphLimit, setGraphLimit] = useState(50)
  const [graphEntityType, setGraphEntityType] = useState('')
  return (
    <div style={s.memPanel}>
      <div style={s.memHeader}>
        <div style={s.memTitleRow}>
          <div style={s.memTitle}>
            <span>⬡</span> Memory Sheet
            {memData?.version > 0 && <span style={{ fontSize:'14px', color:FG4 }}>v{memData.version}</span>}
          </div>
          <div style={s.memHdrBtns}>
            <button onClick={() => pollMemory(true)} style={s.refreshBtn} disabled={memLoading}>{memLoading ? '…' : '↻'}</button>
          </div>
        </div>
        <div style={s.memMeta}>
          {memPending ? <span style={{ color:GRN }}>updating…</span>
            : memData?.updated_at ? `Updated ${fmtDate(memData.updated_at)}` : 'No memory yet'}
        </div>
      </div>

      <div style={s.tabBar}>
        {['view', 'edit', 'history', 'graph', 'conflicts'].map(tab => (
          <button key={tab} onClick={() => {
            if (tab === 'edit') openEdit()
            else if (tab === 'graph') { setMemTab('graph'); loadGraphStats(); loadGraphSample(graphLimit, graphEntityType); setSelectedNode(null) }
            else if (tab === 'conflicts') { setMemTab('conflicts'); loadConflicts() }
            else setMemTab(tab)
          }}
            style={{ ...s.tabBtn, ...(memTab === tab ? s.tabActive : {}) }}>
            {tab === 'view' ? 'View' : tab === 'edit' ? 'Edit' : tab === 'graph' ? 'Graph' : tab === 'conflicts' ? `Conflicts${conflicts.length ? ` (${conflicts.length})` : ''}` : 'History'}
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
                ).map((f, i) => {
                  const sal = f.salience != null ? Math.min(Math.round(f.salience * 100), 100) : null
                  const salColor = f.salience >= 0.7 ? GRN : f.salience >= 0.4 ? AMB : FG4
                  return (
                    <div key={i} style={{
                      background:INSET, border:`1px solid ${LINE}`,
                      padding:'0.5rem 0.75rem', fontSize:'16px', color:FG2, lineHeight:1.5,
                      display:'flex', flexDirection:'column', gap:'0.3rem',
                    }}>
                      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:'0.5rem' }}>
                        <span style={{ flex:1 }}>{f.content}</span>
                        {sal != null && (
                          <div style={{ display:'flex', alignItems:'center', gap:'0.35rem', flexShrink:0, marginTop:'3px' }}>
                            <div style={{ width:'48px', height:'4px', background:LINE, overflow:'hidden' }}>
                              <div style={{ height:'100%', width:`${sal}%`, background: salColor }} />
                            </div>
                            <span style={{ fontSize:'0.65rem', color: salColor, minWidth:'26px' }}>{sal}%</span>
                          </div>
                        )}
                      </div>
                      {'last_used_at' in f && (
                        <div style={{ fontSize:'13px', color:FG4 }}>
                          {f.last_used_at ? `Last accessed: ${timeAgo(f.last_used_at)}` : 'Never accessed'}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            {sections.map(sec => (
              <div key={sec.name} style={s.section}>
                <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||FG3, background: (SECTION_COLORS[sec.name]||FG3)+'18' }}>{sec.name}</span>
                {sec.pairs.map((p, i) => (
                  <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                ))}
              </div>
            ))}
            {projectSections.length > 0 && (
              <>
                <div style={s.divider}><span style={s.divLabel}>PROJECT STATE</span><div style={{ flex:1, borderTop:`1px solid ${LINE}` }} /></div>
                {projectSections.map(sec => (
                  <div key={sec.name} style={s.section}>
                        <span style={{ ...s.secLabel, color: SECTION_COLORS[sec.name]||FG3, background: (SECTION_COLORS[sec.name]||FG3)+'18' }}>{sec.name}</span>
                    {sec.pairs.map((p, i) => (
                      <div key={i} style={s.kv}><span style={s.kvKey}>{p.key}</span><span style={s.kvVal}>{p.val}</span></div>
                    ))}
                  </div>
                ))}
              </>
            )}
          </>
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
                <div style={{ fontSize:'14px', color:FG4, marginBottom:'0.75rem' }}>Select a version to diff against current</div>
                <div style={s.historyList}>
                  {memHistory.map((v, i) => (
                    <div key={i} onClick={() => setDiffIdx(diffIdx === i ? null : i)}
                      style={{ ...s.historyItem, borderColor: diffIdx === i ? RED : LINE }}>
                      <span style={{ color:FG2 }}>v{v.version}</span>
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
        {memTab === 'graph' && (() => {
          const triples = graphSample?.triples || []
          const nodeIds = [...new Set(triples.flatMap(t => [t.source, t.target]))]
          const N = nodeIds.length
          const SW = 320, SH = 260, CX = SW / 2, CY = SH / 2
          const R = N <= 1 ? 0 : Math.min(CX - 24, CY - 24)
          const nr = N > 30 ? 4 : 6
          const nodes = nodeIds.map((id, i) => {
            const angle = (2 * Math.PI * i) / N - Math.PI / 2
            return { id, x: N === 1 ? CX : CX + R * Math.cos(angle), y: N === 1 ? CY : CY + R * Math.sin(angle) }
          })
          const posMap = Object.fromEntries(nodes.map(n => [n.id, n]))
          const selEdges = selectedNode ? triples.filter(t => t.source === selectedNode || t.target === selectedNode) : []
          const selNeighbors = new Set(selEdges.flatMap(t => [t.source, t.target]))

          return (
            <div>
              {!graphStats?.available && !graphLoading && (
                <p style={s.emptyMem}>Graph memory unavailable.<br /><span style={{ fontSize:'0.75rem' }}>Set NEO4J_PASSWORD to enable.</span></p>
              )}
              {graphStats?.available && (
                <>
                  <div style={{ display:'flex', gap:'0.75rem', marginBottom:'0.75rem' }}>
                    <div style={{ flex:1, background:INSET, border:`1px solid ${LINE}`, padding:'0.5rem', textAlign:'center' }}>
                      <div style={{ fontSize:'1.2rem', fontWeight:700, color:CYN }}>{graphStats.entities}</div>
                      <div style={{ fontSize:'13px', color:FG4 }}>Entities</div>
                    </div>
                    <div style={{ flex:1, background:INSET, border:`1px solid ${LINE}`, padding:'0.5rem', textAlign:'center' }}>
                      <div style={{ fontSize:'1.2rem', fontWeight:700, color:GRN }}>{graphStats.relations}</div>
                      <div style={{ fontSize:'13px', color:FG4 }}>Relations</div>
                    </div>
                  </div>

                  <div style={{ display:'flex', gap:'0.4rem', marginBottom:'0.6rem', alignItems:'center' }}>
                    <input value={graphEntityType} onChange={e => setGraphEntityType(e.target.value)}
                      placeholder="Type filter (PERSON…)" style={{ ...s.sideSearchInput, flex:1, padding:'0.3rem 0.5rem', fontSize:'0.72rem' }} />
                    <input type="number" value={graphLimit} min={5} max={200}
                      onChange={e => setGraphLimit(Number(e.target.value))}
                      style={{ ...s.sideSearchInput, width:'52px', padding:'0.3rem 0.4rem', fontSize:'0.72rem', textAlign:'center' }} />
                    <button onClick={() => { loadGraphSample(graphLimit, graphEntityType); setSelectedNode(null) }}
                      disabled={graphSampleLoading} style={s.actionBtn}>
                      {graphSampleLoading ? '…' : '↻'}
                    </button>
                  </div>

                  {graphSampleLoading && <p style={s.emptyMem}>Loading graph…</p>}
                  {!graphSampleLoading && graphSample && !graphSample.available && (
                    <p style={s.emptyMem}>Graph unavailable.</p>
                  )}
                  {!graphSampleLoading && graphSample?.available && N === 0 && (
                    <p style={s.emptyMem}>No entities yet.</p>
                  )}
                  {!graphSampleLoading && graphSample?.available && N > 0 && (
                    <>
                      <div style={{ background:INSET, border:`1px solid ${LINE}`, overflow:'hidden', marginBottom:'0.6rem' }}>
                        <svg viewBox={`0 0 ${SW} ${SH}`} style={{ width:'100%', display:'block' }}>
                          {triples.map((t, i) => {
                            const a = posMap[t.source], b = posMap[t.target]
                            if (!a || !b) return null
                            const isSelEdge = selEdges.includes(t)
                            return (
                              <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                                stroke={isSelEdge ? CYN : LINE}
                                strokeWidth={isSelEdge ? 1.5 : 1} />
                            )
                          })}
                          {nodes.map(n => {
                            const isSel = n.id === selectedNode
                            const isNeighbor = selNeighbors.has(n.id) && !isSel
                            const fill = isSel ? RED : isNeighbor ? CYN : selectedNode ? LINE : FG5
                            const stroke = isSel ? FG2 : isNeighbor ? CYN : FG4
                            return (
                              <g key={n.id} style={{ cursor:'pointer' }} onClick={() => setSelectedNode(n.id === selectedNode ? null : n.id)}>
                                <circle cx={n.x} cy={n.y} r={nr + 4} fill="transparent" />
                                <circle cx={n.x} cy={n.y} r={nr} fill={fill} stroke={stroke} strokeWidth={1.5} />
                                {(isSel || isNeighbor || N <= 12) && (
                                  <text x={n.x} y={n.y - nr - 3} textAnchor="middle"
                                    style={{ fontSize:'7px', fill: isSel ? FG2 : FG4, pointerEvents:'none', userSelect:'none' }}>
                                    {n.id.length > 14 ? n.id.slice(0, 13) + '…' : n.id}
                                  </text>
                                )}
                              </g>
                            )
                          })}
                        </svg>
                      </div>

                      {selectedNode ? (
                        <div style={{ background:INSET, border:`1px solid ${LINE}`, padding:'0.6rem 0.75rem', marginBottom:'0.5rem' }}>
                          <div style={{ fontSize:'16px', fontWeight:700, color:CYN, marginBottom:'0.4rem' }}>{selectedNode}</div>
                          {selEdges.length === 0
                            ? <div style={{ fontSize:'14px', color:FG4 }}>No relations.</div>
                            : selEdges.map((t, i) => (
                                <div key={i} style={{ fontSize:'14px', color:FG4, padding:'0.15rem 0', borderBottom:`1px solid ${LINE2}`, lineHeight:1.45 }}>
                                  {t.source === selectedNode
                                    ? <><span style={{ color:FG2 }}>{t.source}</span> <span style={{ color:FG4 }}>—[{t.relation}]→</span> <span style={{ color:FG3 }}>{t.target}</span></>
                                    : <><span style={{ color:FG3 }}>{t.source}</span> <span style={{ color:FG4 }}>—[{t.relation}]→</span> <span style={{ color:FG2 }}>{t.target}</span></>
                                  }
                                </div>
                              ))
                          }
                        </div>
                      ) : (
                        <p style={{ fontSize:'13px', color:FG5, textAlign:'center' }}>Click a node to explore its relations.</p>
                      )}
                    </>
                  )}
                </>
              )}
              {!graphStats && !graphLoading && <p style={s.emptyMem}>No data yet.</p>}
              <button onClick={() => { loadGraphStats(); loadGraphSample(graphLimit, graphEntityType); setSelectedNode(null) }}
                style={{ ...s.actionBtn, marginTop:'0.5rem' }} disabled={graphLoading || graphSampleLoading}>
                ↻ Refresh
              </button>
            </div>
          )
        })()}
        {memTab === 'conflicts' && (
          <div>
            {conflictsLoading && <p style={s.emptyMem}>Loading…</p>}
            {!conflictsLoading && conflicts.length === 0 && <p style={s.emptyMem}>No conflicts.</p>}
            {!conflictsLoading && conflicts.map(c => {
              const badgeColor = CONFLICT_BADGE[c.conflict_type] || '#8ba3bd'
              return (
                <div key={c.id} style={{ background:INSET, border:`1px solid ${LINE}`, padding:'0.75rem', marginBottom:'0.6rem' }}>
                  <span style={{ fontSize:'14px', fontWeight:700, color: badgeColor, background: badgeColor + '18', padding:'0.1em 0.45em', letterSpacing:'0.06em', textTransform:'uppercase', marginBottom:'0.5rem', display:'inline-block' }}>{c.conflict_type}</span>
                  <div style={{ display:'flex', gap:'0.5rem', marginBottom:'0.5rem' }}>
                    <div style={{ flex:1, background:LINE, border:`1px solid ${LINE2}`, padding:'0.5rem 0.65rem', fontSize:'16px', color:FG2, lineHeight:1.5 }}>
                      <div style={{ fontSize:'13px', color:FG4, marginBottom:'0.2rem' }}>A</div>
                      {c.fact_a}
                    </div>
                    <div style={{ flex:1, background:LINE, border:`1px solid ${LINE2}`, padding:'0.5rem 0.65rem', fontSize:'16px', color:FG2, lineHeight:1.5 }}>
                      <div style={{ fontSize:'13px', color:FG4, marginBottom:'0.2rem' }}>B</div>
                      {c.fact_b}
                    </div>
                  </div>
                  <div style={{ display:'flex', gap:'0.4rem', flexWrap:'wrap' }}>
                    {[['Keep A','keep_a',CYN],['Keep B','keep_b',GRN],['Merge','merge',AMB],['Discard Both','discard_both',RED]].map(([label, strategy, color]) => (
                      <button key={strategy} onClick={() => resolveConflict(c.id, strategy)}
                        style={{ padding:'0.2rem 0.6rem', border:`1px solid ${color}40`, background:`${color}12`, color, cursor:'pointer', fontSize:'14px', fontWeight:700 }}>
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
      </div>
    </div>
  )
}
