import { Fragment } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import s, { NOMINAL, AMBER, ALERT, INFOBLUE, FG4, FG5, LINE, MONO, VOID } from '../../../lib/chatStyles.js'
import { MODEL_LABELS, MODEL_SUBLABELS, COMPARE_MODELS } from '../../../lib/chatConstants.js'
import ProvenanceTrace from '../ProvenanceTrace'

const confirmBtn = (color) => ({
  padding:'0.35rem 0.9rem', background:color, color:VOID, border:'none', borderRadius:'3px',
  cursor:'pointer', fontFamily:MONO, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', fontWeight:700,
})
const dismissBtn = {
  padding:'0.35rem 0.7rem', background:'none', color:'#8ba3bd', border:'1px solid #2a4160', borderRadius:'3px',
  cursor:'pointer', fontFamily:MONO, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase',
}
const cardLabel = (color) => ({
  fontFamily:MONO, fontSize:'8.5px', color, marginBottom:'0.25rem', letterSpacing:'0.1em', textTransform:'uppercase',
})

export default function MessageList({
  messages, activeConvId, bottomRef,
  proactive, setProactive,
  setMessages,
  pendingWriteFact, onAcceptWrite, onDismissWrite,
  lastSession,
  pendingCalendarWrite, onAcceptCalendarWrite, onDismissCalendarWrite,
  toastMsg,
  onOpenMemory,
}) {
  const firstAiIdx = messages.findIndex(m => m.role === 'ai')
  return (
    <div style={s.feed}>
      {messages.length === 0 && <p style={s.hint}>{activeConvId ? 'Loading…' : 'Send a message to start.'}</p>}
      {messages.map((m, idx) => {
        const isFirstAi = lastSession && m.role === 'ai' && idx === firstAiIdx
        if (m.role === 'compare') {
          return (
            <Fragment key={m.id}>
              {isFirstAi && <div style={{ fontSize:'12px', color:FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
              <div style={s.compareRow}>
                {COMPARE_MODELS.map(model => {
                  const resp = m.responses[model] || { text: '', streaming: false }
                  return (
                    <div key={model} style={s.compareCard}>
                      <div style={s.cardHeader}>{MODEL_LABELS[model]}</div>
                      {(resp.streaming || !resp.text)
                        ? <p style={s.text}>{resp.text || <span style={{ color:FG5 }}>…</span>}{resp.streaming && <span style={s.cursor} />}</p>
                        : <div className="md-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{resp.text}</ReactMarkdown></div>
                      }
                      <span style={s.cardModel}>{MODEL_SUBLABELS[model]}</span>
                    </div>
                  )
                })}
              </div>
            </Fragment>
          )
        }
        return (
          <Fragment key={m.id}>
            {isFirstAi && <div style={{ fontSize:'12px', color:FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
            <div style={{ ...s.bubble, ...(m.role === 'user' ? s.userBubble : m.role === 'err' ? s.errBubble : s.aiBubble) }}>
            {m.toolCalls && m.toolCalls.map((tc, i) => (
              <div key={i}>
                <div style={s.toolPill} onClick={() => setMessages(prev => prev.map(msg => msg.id === m.id
                  ? { ...msg, toolCalls: msg.toolCalls.map((t, j) => j === i ? { ...t, expanded: !t.expanded } : t) }
                  : msg))}>
                  ⚙ {tc.name}{tc.result == null ? '…' : (tc.expanded ? ' ▲' : ' ▼')}
                </div>
                {tc.expanded && tc.result != null && <div style={s.toolResult}>{tc.result}</div>}
              </div>
            ))}
            {(m.streaming || m.role === 'err' || m.role === 'user')
              ? <p style={s.text}>{m.text}{m.streaming && <span style={s.cursor} />}</p>
              : <div className="md-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown></div>
            }
            {m.askUser && (
              <div style={s.askCard}>
                <span style={s.askIcon}>⚠️</span>
                <div>
                  <div style={s.askLabel}>NEEDS CLARIFICATION</div>
                  <div style={s.askQuestion}>{m.askUser}</div>
                </div>
              </div>
            )}
            {m.model && !m.streaming && <span style={s.tag}>{MODEL_LABELS[m.model] || m.model} · {MODEL_SUBLABELS[m.model] || ''}</span>}
            {m.totalTokens && !m.streaming && <span style={s.tokMeta}>{m.totalTokens.toLocaleString()} tok · ${(m.costUsd || 0).toFixed(5)}
              {m.queryType && m.role === 'ai' ? ` · ${m.queryType}` : ''}
              {m.role === 'ai' && m.srcCount > 0 ? <span style={{ color: m.srcCount >= 3 ? NOMINAL : AMBER }}> · {m.srcCount} src</span> : null}
              {m.webSearched ? <span style={{ color: INFOBLUE }}> · web</span> : null}
              {m.urlFetched ? <span style={{ color: INFOBLUE }}> · url</span> : null}
            </span>}
            {!m.streaming && m.role === 'ai' && m.grounding && m.grounding.level !== 'none' && (() => {
              const lvl = m.grounding.level
              const c = lvl === 'high' ? NOMINAL : lvl === 'medium' ? AMBER : ALERT
              const hasTrace = (m.activity && m.activity.length > 0)
              return (
                <>
                  <div
                    onClick={hasTrace ? () => setMessages(prev => prev.map(msg => msg.id === m.id ? { ...msg, traceExpanded: !msg.traceExpanded } : msg)) : undefined}
                    style={{ ...s.gaugeRow, cursor: hasTrace ? 'pointer' : 'default' }}
                    title="Grounding confidence — how well retrieval supports this answer"
                  >
                    GROUNDING
                    <span style={s.gaugeBar}>
                      <i style={{ ...s.gaugeFill, width:`${m.grounding.score ?? 0}%`, background:c }} />
                    </span>
                    <span style={{ color:c }}>{m.grounding.score}%</span>
                    {hasTrace ? (m.traceExpanded ? '▴' : '▾') : ''}
                  </div>
                  {m.traceExpanded && hasTrace && (
                    <div style={{ marginTop:'0.4rem', borderLeft:`2px solid ${LINE}`, paddingLeft:'0.6rem' }}>
                      <div style={{ fontSize:'9px', fontFamily:MONO, color:FG5, letterSpacing:'0.06em', textTransform:'uppercase', marginBottom:'0.25rem' }}>Reasoning steps</div>
                      {(() => {
                        const stagePrefix = (st) => st === 'tool' ? '→ ' : st === 'tool_result' ? '← ' : ''
                        return m.activity.map((a, i) => (
                          <div key={i} style={{ fontSize:'11.5px', fontFamily:MONO, color: a.level === 'error' ? ALERT : a.level === 'warn' ? AMBER : FG4, lineHeight:1.5, ...((a.stage === 'tool' || a.stage === 'tool_result') ? { paddingLeft:'12px' } : {}) }}>
                            <span>{stagePrefix(a.stage)}{a.detail}</span>{typeof a.ms === 'number' ? <span style={{ color:FG5 }}> · {a.ms}ms</span> : null}
                          </div>
                        ))
                      })()}
                    </div>
                  )}
                </>
              )
            })()}
            {!m.streaming && m.role === 'ai' && (
              <ProvenanceTrace provenance={m.provenance} grounding={m.grounding} onOpenMemory={onOpenMemory} />
            )}
          </div>
        </Fragment>
        )
      })}
      <div ref={bottomRef} />
      {pendingWriteFact && (
        <div style={{ display:'flex', gap:'0.6rem', alignItems:'flex-start', background:'rgba(85,214,124,0.08)', border:`1px solid rgba(85,214,124,0.40)`, borderRadius:'4px', padding:'0.65rem 0.85rem', margin:'0 1.1rem 0.5rem' }}>
          <span style={{ fontSize:'0.95rem', flexShrink:0, marginTop:'1px', color:NOMINAL }}>✓</span>
          <div style={{ flex:1 }}>
            <div style={cardLabel(NOMINAL)}>MEMORY SUGGESTION</div>
            <div style={{ fontSize:'13.5px', color:'#8ba3bd', lineHeight:1.4 }}>{pendingWriteFact}</div>
            <div style={{ display:'flex', gap:'0.5rem', marginTop:'0.5rem' }}>
              <button onClick={() => onAcceptWrite(pendingWriteFact)} style={confirmBtn(NOMINAL)}>Accept</button>
              <button onClick={onDismissWrite} style={dismissBtn}>Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {pendingCalendarWrite && (
        <div style={{ display:'flex', gap:'0.6rem', alignItems:'flex-start', background:'rgba(79,156,240,0.08)', border:'1px solid rgba(79,156,240,0.40)', borderRadius:'4px', padding:'0.65rem 0.85rem', margin:'0 1.1rem 0.5rem' }}>
          <span style={{ fontSize:'0.95rem', flexShrink:0, marginTop:'1px', color:INFOBLUE }}>📅</span>
          <div style={{ flex:1 }}>
            <div style={cardLabel(INFOBLUE)}>CALENDAR SUGGESTION</div>
            <div style={{ fontSize:'13.5px', color:'#8ba3bd', lineHeight:1.4 }}>{pendingCalendarWrite.summary}</div>
            <div style={{ display:'flex', gap:'0.5rem', marginTop:'0.5rem' }}>
              <button onClick={() => onAcceptCalendarWrite(pendingCalendarWrite)} style={confirmBtn(INFOBLUE)}>Accept</button>
              <button onClick={onDismissCalendarWrite} style={dismissBtn}>Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {toastMsg && (
        <div style={{ fontSize:'11px', color:INFOBLUE, textAlign:'center', margin:'0.25rem 1.1rem', fontFamily:MONO, letterSpacing:'0.04em' }}>
          {toastMsg}
        </div>
      )}
      {proactive && (
        <div style={s.proactiveCard}>
          <span style={{ fontSize:'0.95rem', flexShrink:0, marginTop:'1px' }}>💡</span>
          <div style={{ flex:1 }}>
            <div style={s.proactiveLabel}>SUGGESTION</div>
            <div style={s.proactiveTxt}>{proactive}</div>
          </div>
          <button style={s.proactiveDismiss} onClick={() => setProactive(null)} title="Dismiss">✕</button>
        </div>
      )}
    </div>
  )
}
