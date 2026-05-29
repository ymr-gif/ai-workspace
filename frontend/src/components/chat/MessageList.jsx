import { Fragment } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import s from '../../lib/chatStyles.js'
import { MODEL_LABELS, MODEL_SUBLABELS, COMPARE_MODELS } from '../../lib/chatConstants.js'

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
              {isFirstAi && <div style={{ fontSize:'0.72rem', color:'#475569', marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
              <div style={s.compareRow}>
                {COMPARE_MODELS.map(model => {
                  const resp = m.responses[model] || { text: '', streaming: false }
                  return (
                    <div key={model} style={s.compareCard}>
                      <div style={s.cardHeader}>{MODEL_LABELS[model]}</div>
                      {(resp.streaming || !resp.text)
                        ? <p style={s.text}>{resp.text || <span style={{ color:'#334155' }}>…</span>}{resp.streaming && <span style={s.cursor} />}</p>
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
            {isFirstAi && <div style={{ fontSize:'0.72rem', color:'#475569', marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
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
            {!m.streaming && m.role === 'assistant' && m.queryType && (
              <span style={{ fontSize:'0.65rem', color:'#334155', marginLeft:'0.15rem', textTransform:'uppercase', letterSpacing:'0.04em' }}>[{m.queryType}]</span>
            )}
            {!m.streaming && m.role === 'assistant' && m.srcCount > 0 && (
              <span style={{ fontSize:'0.68rem', marginLeft:'0.25rem', color: m.srcCount >= 3 ? '#34d399' : '#fbbf24' }}>· {m.srcCount} src</span>
            )}
          </div>
        </Fragment>
        )
      })}
      <div ref={bottomRef} />
      {pendingWriteFact && (
        <div style={{ display:'flex', gap:'0.6rem', alignItems:'flex-start', background:'rgba(52,211,153,0.08)', border:'1px solid rgba(52,211,153,0.25)', borderRadius:'8px', padding:'0.65rem 0.85rem', margin:'0 1.5rem 0.5rem' }}>
          <span style={{ fontSize:'1rem', flexShrink:0, marginTop:'1px', color:'#34d399' }}>✓</span>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:'0.7rem', color:'#34d399', fontWeight:600, marginBottom:'0.2rem', letterSpacing:'0.04em' }}>MEMORY SUGGESTION</div>
            <div style={{ fontSize:'0.85rem', color:'#6ee7b7', lineHeight:1.5 }}>{pendingWriteFact}</div>
            <div style={{ display:'flex', gap:'0.5rem', marginTop:'0.5rem' }}>
              <button onClick={() => onAcceptWrite(pendingWriteFact)} style={{ padding:'0.25rem 0.75rem', borderRadius:'6px', background:'#34d399', color:'#0f172a', border:'none', cursor:'pointer', fontSize:'0.78rem', fontWeight:600 }}>Accept</button>
              <button onClick={onDismissWrite} style={{ padding:'0.25rem 0.75rem', borderRadius:'6px', background:'none', color:'#94a3b8', border:'1px solid #334155', cursor:'pointer', fontSize:'0.78rem' }}>Dismiss</button>
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
