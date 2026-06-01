/* NIM // CANVAS — Logs + Usage popup nodes. Exports: LogsNode, UsageNode */
(function () {
  const C = window.NIM_CANVAS_C;
  const S = window.NIM_CANVAS_S;
  const D = window.NIM_CANVAS_DATA;
  const { Handle, Position } = window.ReactFlow;

  /* floating popup portal positioned near a React Flow node */
  function NodePopup({ nodeId, title, onClose, children }) {
    const [pos, setPos] = React.useState({ x:0, y:0, ready:false });
    React.useEffect(() => {
      const el = document.querySelector(`[data-id="${nodeId}"]`);
      if (el) {
        const r = el.getBoundingClientRect();
        setPos({ x: Math.max(10, r.right + 12), y: Math.min(r.top, window.innerHeight - 360), ready:true });
      }
    }, [nodeId]);

    if (!pos.ready) return null;
    return ReactDOM.createPortal(
      <div style={{ position:'fixed', left:pos.x, top:pos.y, zIndex:1200, width:320,
        background:'#0c0c0c', border:'1px solid #4a4a4a', borderLeft:`2px solid ${C.RED}`,
        boxShadow:'4px 4px 0 #000', fontFamily:C.TERM }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
          padding:'7px 10px', borderBottom:`1px solid ${C.LINE}` }}>
          <span style={{ fontFamily:C.DISP, fontSize:9, color:C.RED, letterSpacing:'0.12em', textTransform:'uppercase' }}>{title}</span>
          <button onClick={onClose} style={{ background:'none', border:`1px solid ${C.LINE2}`,
            color:C.FG4, cursor:'pointer', fontFamily:C.DISP, fontSize:8, padding:'2px 6px', letterSpacing:'0.06em' }}>X</button>
        </div>
        {children}
      </div>,
      document.body
    );
  }

  /* small compact node card (for logs/usage before popup opens) */
  function CompactCard({ dot, dotColor, label, hint, onClick, animState }) {
    const [hovered, setHovered] = React.useState(false);
    return (
      <div style={{ ...S.nodeCard, width:180, cursor:'pointer',
        ...(window.getAnimStyle||((s)=>({})))(animState),
        ...(hovered ? { borderLeftColor:`${dotColor}` } : {}) }}
        onClick={onClick} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
        <div style={S.nodeHeader}>
          <span style={{ width:8, height:8, background:dotColor, flexShrink:0, boxShadow:`0 0 5px ${dotColor}` }} />
          <span style={S.nodeLabel}>{label}</span>
        </div>
        <div style={{ padding:'6px 10px', fontFamily:C.DISP, fontSize:7, color:C.FG5, letterSpacing:'0.1em', textTransform:'uppercase' }}>
          {hint}
        </div>
      </div>
    );
  }

  /* ─────────────── LOGS NODE ─────────────── */
  function LogsNode({ data }) {
    const [open,    setOpen]    = React.useState(false);
    const [expArgs, setExpArgs] = React.useState({});
    const logs = D.MOCK_LOGS_CANVAS;

    return (
      <>
        <Handle type="target" position={Position.Left} style={{ ...S.handle, left:-5 }} />
        <CompactCard dot="[L]" dotColor={C.CYN} label="LOGS"
          hint={`${logs.length} TOOL CALLS · CLICK TO VIEW`} animState={data.animState}
          onClick={() => setOpen(o=>!o)} />
        <Handle type="source" position={Position.Right} style={{ ...S.handle, right:-5 }} />

        {open && (
          <NodePopup nodeId="logs" title="Tool Call Log" onClose={() => setOpen(false)}>
            {/* session filter stub */}
            <div style={{ display:'flex', gap:4, padding:'6px 10px', borderBottom:`1px solid ${C.LINE}` }}>
              {['ALL','Infra','Research'].map(s => (
                <button key={s} style={{ padding:'2px 7px', border:`1px solid ${C.LINE2}`, background:'none',
                  color:C.FG5, fontFamily:C.DISP, fontSize:7, cursor:'pointer', letterSpacing:'0.06em' }}>{s}</button>
              ))}
            </div>
            <div style={{ maxHeight:260, overflowY:'auto' }} className="nim-scroll">
              {logs.map(l => (
                <div key={l.id} style={{ padding:'7px 10px', borderBottom:`1px solid ${C.LINE}` }}>
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:3 }}>
                    <span style={{ fontFamily:C.DISP, fontSize:9, color:C.CYN, letterSpacing:'0.08em' }}>{l.name}</span>
                    <span style={{ fontFamily:C.TERM, fontSize:10, color:C.FG5 }}>{l.ts}</span>
                  </div>
                  <div style={{ cursor:'pointer', marginBottom:3 }}
                    onClick={() => setExpArgs(e => ({ ...e, [l.id]:!e[l.id] }))}>
                    <span style={{ fontFamily:C.DISP, fontSize:7, color:C.FG5, letterSpacing:'0.08em' }}>
                      ARGS {expArgs[l.id]?'▲':'▼'}
                    </span>
                    {expArgs[l.id] && (
                      <div style={{ fontFamily:C.TERM, fontSize:11, color:C.FG5, marginTop:3, wordBreak:'break-all' }}>{l.args}</div>
                    )}
                  </div>
                  <div style={{ fontFamily:C.TERM, fontSize:11, color:C.FG3 }}>{l.result}</div>
                </div>
              ))}
            </div>
          </NodePopup>
        )}
      </>
    );
  }

  /* ─────────────── USAGE NODE ─────────────── */
  function UsageNode({ data }) {
    const [open, setOpen] = React.useState(false);
    const u = D.MOCK_USAGE_CANVAS;

    return (
      <>
        <Handle type="target" position={Position.Left} style={{ ...S.handle, left:-5 }} />
        <CompactCard dot="[$]" dotColor={C.GRN} label="USAGE"
          hint={`$${u.total_cost.toFixed(4)} · ${u.requests} REQS`} animState={data.animState}
          onClick={() => setOpen(o=>!o)} />
        <Handle type="source" position={Position.Right} style={{ ...S.handle, right:-5 }} />

        {open && (
          <NodePopup nodeId="usage" title="Usage & Cost" onClose={() => setOpen(false)}>
            {/* totals */}
            <div style={{ padding:'10px 12px', borderBottom:`1px solid ${C.LINE}` }}>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG5, letterSpacing:'0.1em' }}>TOTAL TOKENS</span>
                <span style={{ fontFamily:C.TERM, fontSize:14, color:C.FG1 }}>{u.total_tokens.toLocaleString()}</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG5, letterSpacing:'0.1em' }}>TOTAL COST</span>
                <span style={{ fontFamily:C.TERM, fontSize:14, color:C.GRN }}>${u.total_cost.toFixed(4)}</span>
              </div>
              <div style={{ display:'flex', justifyContent:'space-between' }}>
                <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG5, letterSpacing:'0.1em' }}>REQUESTS</span>
                <span style={{ fontFamily:C.TERM, fontSize:13, color:C.FG2 }}>{u.requests}</span>
              </div>
            </div>
            {/* per-model table */}
            <div style={{ padding:'6px 0' }}>
              <div style={{ padding:'3px 12px 5px', fontFamily:C.DISP, fontSize:7, color:C.FG5, letterSpacing:'0.1em' }}>PER MODEL</div>
              {u.by_model.map(m => {
                const pct = Math.round((m.tokens / u.total_tokens) * 100);
                return (
                  <div key={m.model} style={{ padding:'5px 12px', borderTop:`1px solid ${C.LINE}` }}>
                    <div style={{ display:'flex', justifyContent:'space-between', marginBottom:3 }}>
                      <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG3, letterSpacing:'0.04em' }}>{m.model}</span>
                      <span style={{ fontFamily:C.TERM, fontSize:11, color:C.GRN }}>${m.cost.toFixed(4)}</span>
                    </div>
                    <div style={{ height:3, background:C.LINE, position:'relative' }}>
                      <div style={{ position:'absolute', top:0, left:0, height:'100%', width:`${pct}%`,
                        background:C.GRN, boxShadow:`0 0 4px ${C.GRN}` }} />
                    </div>
                    <div style={{ fontFamily:C.TERM, fontSize:10, color:C.FG5, marginTop:2 }}>
                      {m.tokens.toLocaleString()} tok · {pct}%
                    </div>
                  </div>
                );
              })}
            </div>
            <div style={{ padding:'5px 12px', borderTop:`1px solid ${C.LINE}`,
              fontFamily:C.DISP, fontSize:7, color:C.FG5, letterSpacing:'0.1em', textTransform:'uppercase' }}>
              {u.window}
            </div>
          </NodePopup>
        )}
      </>
    );
  }

  Object.assign(window, { LogsNode, UsageNode });
})();
