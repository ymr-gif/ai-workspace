import { Fragment } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import s, { GRN, AMB, FG4, FG5, RED, LINE } from '../../../lib/chatStyles.js'
import { MODEL_LABELS, MODEL_SUBLABELS, COMPARE_MODELS } from '../../../lib/chatConstants.js'

export default function MessageList({
  messages, activeConvId, bottomRef,
  proactive, setProactive,
  setMessages,
  pendingWriteFact, onAcceptWrite, onDismissWrite,
  lastSession,
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
              {isFirstAi && <div style={{ fontSize:'14px', color:FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
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
            {isFirstAi && <div style={{ fontSize:'14px', color:FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
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
            {m.totalTokens && !m.streaming && <span style={s.tokMeta}>{m.totalTokens.toLocaleString()} tok · ${(m.costUsd || 0).toFixed(5)}</span>}
            {!m.streaming && m.role === 'ai' && m.queryType && (
              <span style={{ fontSize:'14px', color:FG4, marginLeft:'0.15rem' }}>[{m.queryType}]</span>
            )}
            {!m.streaming && m.role === 'ai' && m.srcCount > 0 && (
              <span style={{ fontSize:'14px', marginLeft:'0.25rem', color: m.srcCount >= 3 ? GRN : AMB }}>· {m.srcCount} src</span>
            )}
            {m.webSearched && (
              <span style={{ background:'#0e7490', color:'white', fontSize:'0.65rem', padding:'1px 5px', borderRadius:'3px', marginLeft:'4px' }}>web</span>
            )}
            {m.urlFetched && (
              <span style={{ background:'#0369a1', color:'white', fontSize:'0.65rem', padding:'1px 5px', borderRadius:'3px', marginLeft:'4px' }}>url</span>
            )}
            {!m.streaming && m.role === 'ai' && m.grounding && m.grounding.level !== 'none' && (() => {
              const lvl = m.grounding.level
              const c = lvl === 'high' ? GRN : lvl === 'medium' ? AMB : RED
              const dot = lvl === 'high' ? '🟢' : lvl === 'medium' ? '🟡' : '🔴'
              const label = lvl.charAt(0).toUpperCase() + lvl.slice(1)
              const hasTrace = (m.activity && m.activity.length > 0)
              return (
                <>
                  <span
                    onClick={hasTrace ? () => setMessages(prev => prev.map(msg => msg.id === m.id ? { ...msg, traceExpanded: !msg.traceExpanded } : msg)) : undefined}
                    style={{ fontSize:'14px', marginLeft:'0.35rem', color:c, cursor: hasTrace ? 'pointer' : 'default', userSelect:'none' }}
                    title="Grounding confidence — how well retrieval supports this answer"
                  >
                    {dot} {label} · {m.grounding.score}%{hasTrace ? (m.traceExpanded ? ' ▴' : ' ▾') : ''}
                  </span>
                  {m.traceExpanded && hasTrace && (
                    <div style={{ marginTop:'0.4rem', borderLeft:`2px solid ${LINE}`, paddingLeft:'0.6rem' }}>
                      <div style={{ fontSize:'10px', color:FG5, letterSpacing:'0.06em', textTransform:'uppercase', marginBottom:'0.25rem' }}>Reasoning steps</div>
                      {m.activity.map((a, i) => (
                        <div key={i} style={{ fontSize:'13px', color: a.level === 'error' ? RED : a.level === 'warn' ? AMB : FG4, lineHeight:1.5 }}>
                          {a.detail}{typeof a.ms === 'number' ? <span style={{ color:FG5 }}> · {a.ms}ms</span> : null}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )
            })()}
          </div>
        </Fragment>
        )
      })}
      <div ref={bottomRef} />
      {pendingWriteFact && (
        <div style={{ display:'flex', gap:'0.6rem', alignItems:'flex-start', background:'rgba(61,255,110,0.08)', border:`1px solid rgba(61,255,110,0.40)`, padding:'0.65rem 0.85rem', margin:'0 1.25rem 0.5rem' }}>
          <span style={{ fontSize:'1rem', flexShrink:0, marginTop:'1px', color:GRN }}>✓</span>
          <div style={{ flex:1 }}>
            <div style={{ fontFamily:"'Silkscreen',monospace", fontSize:'9px', color:GRN, marginBottom:'0.25rem', letterSpacing:'0.1em', textTransform:'uppercase' }}>MEMORY SUGGESTION</div>
            <div style={{ fontSize:'17px', color:'#8f8f8f', lineHeight:1.35 }}>{pendingWriteFact}</div>
            <div style={{ display:'flex', gap:'0.5rem', marginTop:'0.5rem' }}>
              <button onClick={() => onAcceptWrite(pendingWriteFact)} style={{ padding:'0.4rem 1rem', background:RED, color:'#000', border:'none', cursor:'pointer', fontFamily:"'Silkscreen',monospace", fontSize:'10px', letterSpacing:'0.08em', textTransform:'uppercase', fontWeight:700 }}>Accept</button>
              <button onClick={onDismissWrite} style={{ padding:'0.4rem 0.75rem', background:'none', color:'#8f8f8f', border:'1px solid #4a4a4a', cursor:'pointer', fontFamily:"'Silkscreen',monospace", fontSize:'10px', letterSpacing:'0.08em', textTransform:'uppercase' }}>Dismiss</button>
            </div>
          </div>
        </div>
      )}
      {proactive && (
        <div style={s.proactiveCard}>
          <span style={{ fontSize:'1rem', flexShrink:0, marginTop:'1px' }}>💡</span>
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
