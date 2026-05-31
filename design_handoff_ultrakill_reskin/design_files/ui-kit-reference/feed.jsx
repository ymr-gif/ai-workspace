/* NIM AI Gateway — message feed + model toolbar. Attaches to window. */
const NIM_S2 = window.NIM_S;
const { NimMd } = window;

/* ---------------------------------------------------------------- Feed */
function MessageFeed({ messages, activeConvId, bottomRef, proactive, dismissProactive, lastSession }) {
  const firstAiIdx = messages.findIndex(m => m.role === 'ai');
  const labels = window.NIM_MODEL_LABELS, subs = window.NIM_MODEL_SUB;
  return (
    <div style={NIM_S2.feed} className="nim-scroll">
      {messages.length === 0 && <p style={NIM_S2.hint}>{activeConvId ? 'Send a message to continue.' : 'Send a message to start.'}</p>}
      {messages.map((m, idx) => {
        const isFirstAi = lastSession && m.role === 'ai' && idx === firstAiIdx;
        if (m.role === 'compare') {
          return (
            <React.Fragment key={m.id}>
              {isFirstAi && <div style={{ fontFamily:window.NIM_C.DISP, fontSize:'9px', letterSpacing:'0.12em', textTransform:'uppercase', color:window.NIM_C.FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
              <div style={NIM_S2.compareRow}>
                {window.NIM_COMPARE.map(model => {
                  const resp = m.responses[model] || { text:'', streaming:false };
                  return (
                    <div key={model} style={NIM_S2.compareCard}>
                      <div style={NIM_S2.cardHeader}>{labels[model]}</div>
                      {(resp.streaming || !resp.text)
                        ? <p style={NIM_S2.text}>{resp.text || <span style={{ color:window.NIM_C.FG5 }}>…</span>}{resp.streaming && <span style={NIM_S2.cursor} />}</p>
                        : <NimMd text={resp.text} />}
                      <span style={NIM_S2.cardModel}>{subs[model]}</span>
                    </div>
                  );
                })}
              </div>
            </React.Fragment>
          );
        }
        const bubble = { ...NIM_S2.bubble, ...(m.role === 'user' ? NIM_S2.userBubble : m.role === 'err' ? NIM_S2.errBubble : NIM_S2.aiBubble) };
        return (
          <React.Fragment key={m.id}>
            {isFirstAi && <div style={{ fontFamily:window.NIM_C.DISP, fontSize:'9px', letterSpacing:'0.12em', textTransform:'uppercase', color:window.NIM_C.FG4, marginBottom:'0.4rem' }}>✦ {lastSession}</div>}
            <div style={bubble}>
              {(m.streaming || m.role === 'err' || m.role === 'user')
                ? <p style={NIM_S2.text}>{m.text}{m.streaming && <span style={NIM_S2.cursor} />}</p>
                : <NimMd text={m.text} />}
              {m.model && !m.streaming && <span style={NIM_S2.tag}>{labels[m.model]} · {subs[m.model]}</span>}
              {m.totalTokens && !m.streaming &&
                <span style={NIM_S2.tokMeta}>{m.totalTokens.toLocaleString()} tok · ${(m.costUsd || 0).toFixed(5)}</span>}
              {!m.streaming && m.role === 'ai' && m.queryType &&
                <span style={{ fontFamily:window.NIM_C.TERM, fontSize:'14px', color:window.NIM_C.FG4, marginLeft:'0.15rem', textTransform:'uppercase' }}> [{m.queryType}]</span>}
              {!m.streaming && m.role === 'ai' && m.srcCount > 0 &&
                <span style={{ fontFamily:window.NIM_C.TERM, fontSize:'14px', marginLeft:'0.25rem', color: m.srcCount >= 3 ? window.NIM_C.GRN : window.NIM_C.AMB }}> · {m.srcCount} src</span>}
            </div>
          </React.Fragment>
        );
      })}
      <div ref={bottomRef} />
      {proactive && (
        <div style={NIM_S2.proactiveCard}>
          <span style={{ fontSize:'1rem', flexShrink:0, marginTop:'1px' }}>💡</span>
          <div style={{ flex:1 }}>
            <div style={NIM_S2.proactiveLabel}>SUGGESTION</div>
            <div style={NIM_S2.proactiveTxt}>{proactive}</div>
          </div>
          <button style={NIM_S2.proactiveDismiss} onClick={dismissProactive} title="Dismiss">✕</button>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- Param slider */
function ParamSlider({ label, enabled, onToggle, value, min, max, step, onChange, fmt }) {
  return (
    <div style={NIM_S2.paramItem}>
      <input type="checkbox" checked={enabled} onChange={e => onToggle(e.target.checked)} style={{ accentColor:'#6366f1', cursor:'pointer' }} />
      <span style={{ ...NIM_S2.paramLabel, color: enabled ? '#94a3b8' : '#475569' }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={!enabled}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex:1, accentColor:'#6366f1', cursor: enabled ? 'pointer' : 'default' }} />
      <span style={{ ...NIM_S2.paramVal, color: enabled ? '#94a3b8' : '#334155' }}>{fmt ? fmt(value) : value}</span>
    </div>
  );
}

/* ---------------------------------------------------------------- Toolbar */
function ModelToolbar({ selectedModel, setSelectedModel, compareMode, setCompareMode, paramsOpen, setParamsOpen,
                        params, setParams, attachedFiles, detachFile, input, setInput, loading, send }) {
  const P = params, sp = (k, v) => setParams({ ...P, [k]: v });
  return (
    <div>
      <div style={NIM_S2.toolbarWrap}>
        <div style={NIM_S2.toolbar}>
          <div style={NIM_S2.modelPills}>
            {window.NIM_MODELS.map(([key, label]) => (
              <button key={key} onClick={() => setSelectedModel(key)}
                style={{ ...NIM_S2.pill, ...(selectedModel === key ? NIM_S2.pillActive : {}) }}>{label}</button>
            ))}
          </div>
          <div style={NIM_S2.toolRight}>
            <button onClick={() => setCompareMode(!compareMode)} style={{ ...NIM_S2.pill, ...(compareMode ? NIM_S2.pillCompare : {}) }}
              title="Run same prompt on all 3 models">⊞ Compare</button>
            <button onClick={() => setParamsOpen(!paramsOpen)} style={{ ...NIM_S2.pill, ...(paramsOpen ? NIM_S2.pillActive : {}) }}
              title="Temperature / max tokens / top-p">⚙</button>
          </div>
        </div>
        {paramsOpen && (
          <div style={NIM_S2.paramsBar}>
            <ParamSlider label="Temp" enabled={P.tempOn} onToggle={v => sp('tempOn', v)} value={P.temp} min={0} max={2} step={0.05} onChange={v => sp('temp', v)} fmt={v => v.toFixed(2)} />
            <ParamSlider label="Tokens" enabled={P.tokOn} onToggle={v => sp('tokOn', v)} value={P.tok} min={256} max={4096} step={256} onChange={v => sp('tok', v)} fmt={v => v} />
            <ParamSlider label="Top-p" enabled={P.toppOn} onToggle={v => sp('toppOn', v)} value={P.topp} min={0} max={1} step={0.05} onChange={v => sp('topp', v)} fmt={v => v.toFixed(2)} />
          </div>
        )}
      </div>
      {attachedFiles.length > 0 && (
        <div style={NIM_S2.fileChipsRow}>
          {attachedFiles.map(f => (
            <span key={f.id} style={NIM_S2.fileChip}>
              📄 {f.filename.length > 24 ? f.filename.slice(0, 22) + '…' : f.filename}
              <span style={NIM_S2.chipX} onClick={() => detachFile(f.id)} title="Detach">✕</span>
            </span>
          ))}
        </div>
      )}
      <form onSubmit={send} style={NIM_S2.bar}>
        <input value={input} onChange={e => setInput(e.target.value)}
          placeholder={compareMode ? 'Compare prompt across all models…' : 'Ask anything…'} disabled={loading} style={NIM_S2.input} />
        <button type="submit" disabled={loading || !input.trim()} style={{ ...NIM_S2.send, ...(compareMode ? { background:'#065f46' } : {}) }}>
          {loading ? '…' : compareMode ? '⊞' : 'Send'}
        </button>
      </form>
    </div>
  );
}

Object.assign(window, { MessageFeed, ModelToolbar });
