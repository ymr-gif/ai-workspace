import { useState } from 'react'
import s from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

// B+ signature: the retrieval chain under grounded answers, in TRACK cyan.
// Earned, never decorative — full trace on high grounding, collapsed chip on
// medium/low, absent when there are no sources.
// Provenance items: {chunk_id, source_id, dense_score, retrieval_type} — file
// source_ids resolve to library filenames; other chunks show an id stub.
export default function ProvenanceTrace({ provenance, grounding, onOpenMemory }) {
  const p = usePanelProps()
  const [expanded, setExpanded] = useState(false)
  if (!provenance || provenance.length === 0) return null

  const level = grounding?.level || 'low'
  const showFull = level === 'high' || expanded
  const top = [...provenance].sort((a, b) => (b.dense_score || 0) - (a.dense_score || 0)).slice(0, 4)

  function nodeLabel(item) {
    const f = p.files.libFiles?.find(x => x.id === item.source_id)
    if (f) return `file/${f.filename.length > 22 ? f.filename.slice(0, 20) + '…' : f.filename}`
    return `src/${String(item.chunk_id).slice(0, 6)}`
  }

  function openNode(item) {
    const f = p.files.libFiles?.find(x => x.id === item.source_id)
    if (f) p.files.viewFile(f.id)
    else onOpenMemory()
  }

  if (!showFull) {
    return (
      <span style={s.traceChip} onClick={() => setExpanded(true)} title="Show retrieval sources">
        TRACE ▸ {provenance.length} SRC
      </span>
    )
  }

  return (
    <div style={s.traceRow}>
      <span style={s.traceLbl}>TRACE</span>
      {top.map((item, i) => (
        <span key={item.chunk_id || i} style={{ display: 'inline-flex', alignItems: 'center' }}>
          {i > 0 && <span style={s.traceLink} />}
          <span style={s.traceNode} onClick={() => openNode(item)}
            title={`dense ${(item.dense_score || 0).toFixed(2)} · ${item.retrieval_type || 'retrieved'}`}>
            <span style={s.traceDia} />{nodeLabel(item)}
          </span>
        </span>
      ))}
      {provenance.length > top.length && (
        <span style={{ ...s.traceLbl, marginLeft: '0.5rem' }}>+{provenance.length - top.length}</span>
      )}
    </div>
  )
}
