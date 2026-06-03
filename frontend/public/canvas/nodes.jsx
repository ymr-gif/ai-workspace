/* NIM // CANVAS — Stage 2/3 node components with animState support.
   Exports: InputNode, SessionNode, ConfigNode, MemoryNode */
(function () {
  const C = window.NIM_CANVAS_C;
  const S = window.NIM_CANVAS_S;
  const { Handle, Position } = window.ReactFlow;

  function animStyle(state) {
    if (state === 'activating') return { boxShadow:'0 0 0 1px rgba(255,34,34,0.8), 0 0 14px rgba(255,34,34,0.25)' };
    if (state === 'processing') return { boxShadow:'0 0 0 1px rgba(139,92,246,0.8), 0 0 14px rgba(139,92,246,0.25)' };
    if (state === 'done')       return { boxShadow:'0 0 0 1px rgba(61,255,110,0.8),  0 0 14px rgba(61,255,110,0.25)' };
    if (state === 'error')      return { boxShadow:'0 0 0 2px rgba(255,34,34,1),      0 0 22px rgba(255,34,34,0.4)' };
    return {};
  }

  /* ── Node action buttons (pin + close) — top-right of every node ── */
  const _CORE_NODES = new Set(['input', 'session', 'memory', 'config']);
  function NodeControls({ nodeId, pinned }) {
    // demo nodes guard by type-string id; real Neo4j nodes (ai-{uuid}) guard by
    // the backend `protected` flag tracked in NIM_PROTECTED_IDS
    const canClose = !_CORE_NODES.has(nodeId) && !window.NIM_PROTECTED_IDS?.has(nodeId);
    const b = {
      background:'none', border:'none', cursor:'pointer',
      fontFamily:C.DISP, fontSize:10, padding:'0 2px', lineHeight:1,
      transition:'color 0.1s', color: C.FG5,
    };
    return (
      <div style={{ display:'flex', gap:1, alignItems:'center', marginLeft:'auto', flexShrink:0 }}>
        {canClose && (
          <button title="Close" style={b}
            onClick={e => { e.stopPropagation(); window.NIM_CANVAS_CB?._closeNode?.(nodeId); }}
            onMouseEnter={e => e.currentTarget.style.color = C.RED}
            onMouseLeave={e => e.currentTarget.style.color = C.FG5}>✕</button>
        )}
        <button title={pinned ? 'Unpin' : 'Pin'}
          style={{ ...b, color: pinned ? C.AMB : C.FG5 }}
          onClick={e => { e.stopPropagation(); window.NIM_CANVAS_CB?._pinNode?.(nodeId, !pinned); }}
          onMouseEnter={e => e.currentTarget.style.color = C.AMB}
          onMouseLeave={e => e.currentTarget.style.color = pinned ? C.AMB : C.FG5}>◉</button>
      </div>
    );
  }

  function NodeHeader({ dot, label, name, extra, nodeId, pinned }) {
    return (
      <div style={S.nodeHeader}>
        <span style={{ width:8, height:8, background:dot, flexShrink:0, boxShadow:`0 0 5px ${dot}` }} />
        <span style={S.nodeLabel}>{label}</span>
        {name && <span style={{ fontFamily:C.DISP, fontSize:9, color:C.FG5, letterSpacing:'0.06em', paddingLeft:5 }}>| {name}</span>}
        {extra && <span>{extra}</span>}
        <NodeControls nodeId={nodeId} pinned={pinned} />
      </div>
    );
  }

  /* compat state: listens for nim-connect-* events, returns { ok, label } or null */
  function useCompatState(myType) {
    const [compat, setCompat] = React.useState(null);
    React.useEffect(() => {
      const onStart = (e) => {
        const c = window.NIM_CHECK_COMPAT?.(e.detail.nodeType, myType);
        setCompat(c || null);
      };
      const onEnd = () => setCompat(null);
      window.addEventListener('nim-connect-start', onStart);
      window.addEventListener('nim-connect-end',   onEnd);
      return () => {
        window.removeEventListener('nim-connect-start', onStart);
        window.removeEventListener('nim-connect-end',   onEnd);
      };
    }, [myType]);
    return compat;
  }

  /* compat border overlay */
  function compatStyle(compat) {
    if (!compat) return {};
    if (compat.ok === true)  return { boxShadow:'0 0 0 1px #3dff6e, 0 0 10px rgba(61,255,110,0.18)' };
    if (compat.ok === false) return { boxShadow:'0 0 0 1px rgba(255,34,34,0.5)' };
    return { boxShadow:'0 0 0 1px rgba(128,128,128,0.5)' };
  }

  /* small compat label strip shown just under the header */
  function CompatLabel({ compat }) {
    if (!compat) return null;
    const color = compat.ok === true ? '#3dff6e' : compat.ok === false ? '#ff2222' : '#808080';
    const sym   = compat.ok === true ? '\u2713' : compat.ok === false ? '\u2715' : '~';
    return (
      <div style={{ fontFamily:window.NIM_CANVAS_C.DISP, fontSize:7, letterSpacing:'0.1em',
        color, padding:'2px 10px', borderBottom:'1px solid #1a1a1a', textTransform:'uppercase' }}>
        {sym} {compat.label}
      </div>
    );
  }

  /* 4-way handle set — shared across all major node types */
  function AllHandles() {
    const { Handle:H, Position:P } = window.ReactFlow;
    const hs = { ...window.NIM_CANVAS_S.handle };
    return (
      <React.Fragment>
        <H type="target" position={P.Top}    id="t-top"    style={{ ...hs, top:-5    }} />
        <H type="source" position={P.Top}    id="s-top"    style={{ ...hs, top:-5    }} />
        <H type="target" position={P.Left}   id="t-left"  style={{ ...hs, left:-5   }} />
        <H type="source" position={P.Left}   id="s-left"  style={{ ...hs, left:-5   }} />
        <H type="target" position={P.Right}  id="t-right" style={{ ...hs, right:-5  }} />
        <H type="source" position={P.Right}  id="s-right" style={{ ...hs, right:-5  }} />
        <H type="target" position={P.Bottom} id="t-bot"   style={{ ...hs, bottom:-5 }} />
        <H type="source" position={P.Bottom} id="s-bot"   style={{ ...hs, bottom:-5 }} />
      </React.Fragment>
    );
  }

  /* ─────────────── SESSION OUTPUT PANEL (portal) ─────────────── */
  function nimMdSimple(text) {
    const esc = t => t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const inline = t => esc(t)
      .replace(/`([^`]+)`/g,'<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>')
      .replace(/(?:^|[^*])\*([^*]+)\*/g,'<em>$1</em>');
    let html='', inList=false;
    for (const ln of text.split('\n')) {
      if (/^\s*[-*—]\s+/.test(ln)) {
        if (!inList) { html+='<ul>'; inList=true; }
        html+='<li>'+inline(ln.replace(/^\s*[-*—]\s+/,''))+'</li>';
      } else {
        if (inList) { html+='</ul>'; inList=false; }
        if (ln.trim()) html+='<p>'+inline(ln)+'</p>';
      }
    }
    if (inList) html+='</ul>';
    return html;
  }

  function SessionOutputPanel({ session, streamText, isStreaming, messages = [] }) {
    const bottomRef  = React.useRef(null);
    const dragRef    = React.useRef(null);
    const [open,  setOpen]  = React.useState(false);
    const [width, setWidth] = React.useState(300);

    React.useEffect(() => { bottomRef.current?.scrollIntoView?.({ block:'end' }); }, [streamText, messages.length]);

    /* drag-to-resize: drag the left edge of the panel */
    function onResizeDown(e) {
      e.preventDefault();
      const startX  = e.clientX;
      const startW  = width;
      function onMove(ev) {
        const delta = startX - ev.clientX;
        setWidth(Math.max(180, Math.min(600, startW + delta)));
      }
      function onUp() {
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup',   onUp);
      }
      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup',   onUp);
    }

    const hasContent = streamText && streamText.length > 0;
    const VIO = 'rgba(139,92,246,0.75)';

    return ReactDOM.createPortal(
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, zIndex: 1000,
        display: 'flex', alignItems: 'stretch', pointerEvents: 'none',
      }}>
        {/* ── tab handle (always visible) ── */}
        <div
          onClick={() => setOpen(o => !o)}
          style={{
            pointerEvents: 'all',
            width: 20, alignSelf: 'center',
            background: '#0a0a0a',
            border: '1px solid #3a3a3a',
            borderRight: 'none',
            borderLeft: `2px solid ${VIO}`,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 80,
            color: VIO,
            fontFamily: C.DISP, fontSize: 11,
            userSelect: 'none',
            transition: 'background 0.1s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(139,92,246,0.08)'}
          onMouseLeave={e => e.currentTarget.style.background = '#0a0a0a'}
        >
          {open ? '›' : '‹'}
        </div>

        {/* ── expanded panel ── */}
        {open && (
          <div style={{
            pointerEvents: 'all',
            width, display: 'flex', flexDirection: 'column',
            background: '#0a0a0a',
            borderLeft: `2px solid ${VIO}`,
            borderTop: '1px solid #3a3a3a',
            borderBottom: '1px solid #3a3a3a',
            boxShadow: '-4px 0 12px rgba(0,0,0,0.6)',
            position: 'relative',
          }}>
            {/* drag resize handle */}
            <div onMouseDown={onResizeDown} style={{
              position: 'absolute', left: 0, top: 0, bottom: 0, width: 5,
              cursor: 'ew-resize', zIndex: 10,
              background: 'transparent',
            }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(139,92,246,0.25)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            />

            {/* header */}
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '7px 12px 7px 14px',
              borderBottom: '1px solid #1a1a1a', flexShrink: 0,
            }}>
              <span style={{ fontFamily:C.DISP, fontSize:8, color:VIO,
                letterSpacing:'0.12em', textTransform:'uppercase' }}>
                {session?.name || 'SESSION'}
              </span>
              <span style={{ fontFamily:C.DISP, fontSize:7, color:C.FG5,
                letterSpacing:'0.08em' }}>OUTPUT</span>
            </div>

            {/* body */}
            <div style={{ flex:1, overflowY:'auto', padding:'10px 14px' }} className="nim-scroll">
              {messages.length === 0 && !hasContent
                ? <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
                    minHeight:60, fontFamily:C.TERM, fontSize:12, color:C.FG5 }}>
                    — no messages yet —
                  </div>
                : <div>
                    {/* conversation history */}
                    {messages.map((m, i) => (
                      <div key={i} style={{ marginBottom:10, paddingBottom:10,
                        borderBottom:'1px solid #111' }}>
                        <div style={{ fontFamily:C.DISP, fontSize:7, letterSpacing:'0.1em',
                          marginBottom:3, color: m.role === 'user' ? C.AMB : VIO }}>
                          {m.role === 'user' ? 'USER' : 'JARVIS'}
                          {m.role !== 'user' && m.model &&
                            <span style={{ color:C.FG5, marginLeft:6 }}>{m.model}</span>}
                          {m.role !== 'user' && m.total_tokens > 0 &&
                            <span style={{ color:C.FG5, marginLeft:6 }}>{m.total_tokens} tok</span>}
                        </div>
                        <div style={{ fontFamily:C.TERM, fontSize:11, color:C.FG3, lineHeight:1.5 }}
                          dangerouslySetInnerHTML={{ __html: nimMdSimple(m.content) }} />
                      </div>
                    ))}
                    {/* live stream (current turn) */}
                    {hasContent && (
                      <div>
                        {messages.length > 0 &&
                          <div style={{ fontFamily:C.DISP, fontSize:7, letterSpacing:'0.1em',
                            marginBottom:3, color:VIO }}>JARVIS</div>}
                        <div style={{ fontFamily:C.TERM, fontSize:12, color:C.FG3, lineHeight:1.6 }}>
                          <div dangerouslySetInnerHTML={{ __html: nimMdSimple(streamText) }} />
                          {isStreaming && (
                            <span style={{ display:'inline-block', width:'0.5em', height:'1em',
                              background:C.RED, verticalAlign:'text-bottom',
                              animation:'blink 1s step-end infinite', marginLeft:2 }} />
                          )}
                        </div>
                      </div>
                    )}
                  </div>
              }
              <div ref={bottomRef} />
            </div>
          </div>
        )}
      </div>,
      document.body
    );
  }

  /* ─────────────── INSIGHT GHOST CARD ─────────────── */
  function InsightCard({ text, onInsert, onDismiss, countdown }) {
    return (
      <div style={{
        background:'rgba(39,216,255,0.06)', border:'1px solid rgba(39,216,255,0.3)',
        padding:'8px 10px', marginBottom:4,
        animation:'insightSlideIn 0.15s ease forwards',
      }}>
        <div style={{ fontFamily:C.DISP, fontSize:7, color:'rgba(39,216,255,0.6)',
          letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:5,
          display:'flex', justifyContent:'space-between' }}>
          <span>INSIGHT</span>
          <span style={{ color:C.FG5 }}>{countdown}s</span>
        </div>
        <div style={{ fontFamily:C.TERM, fontSize:12, color:C.FG4, lineHeight:1.4, marginBottom:7 }}>{text}</div>
        <div style={{ display:'flex', gap:5 }}>
          <button onClick={onInsert} style={{ flex:1, padding:'3px 0', background:'none',
            border:'1px solid rgba(39,216,255,0.5)', color:C.CYN,
            fontFamily:C.DISP, fontSize:8, letterSpacing:'0.08em', cursor:'pointer' }}>INSERT</button>
          <button onClick={onDismiss} style={{ padding:'3px 8px', background:'none',
            border:`1px solid ${C.LINE2}`, color:C.FG4,
            fontFamily:C.DISP, fontSize:8, letterSpacing:'0.08em', cursor:'pointer' }}>DISMISS</button>
        </div>
      </div>
    );
  }

  /* ─────────────── INPUT NODE ─────────────── */
  function InputNode({ data, id }) {
    const [text,      setText]      = React.useState('');
    const [insight,   setInsight]   = React.useState(null);
    const [countdown, setCountdown] = React.useState(10);

    /* listen for insight events from Canvas */
    React.useEffect(() => {
      const handler = (e) => { setInsight(e.detail.text); setCountdown(10); };
      window.addEventListener('nim-insight', handler);
      return () => window.removeEventListener('nim-insight', handler);
    }, []);

    /* countdown timer */
    React.useEffect(() => {
      if (!insight) return;
      if (countdown <= 0) { setInsight(null); return; }
      const t = setTimeout(() => setCountdown(n => n-1), 1000);
      return () => clearTimeout(t);
    }, [insight, countdown]);

    function handleSend(e) {
      e.preventDefault();
      if (!text.trim()) return;
      window.NIM_CANVAS_LAST_INPUT = text;
      /* no session override — buildBody() falls through to NIM_CANVAS_GLOBAL_CONV_ID */
      window.NIM_CANVAS_CB?.onDemoSend?.();
    }

    const compat = useCompatState('inputNode');
    const ns = {
      card:   { ...S.nodeCard, width:280, ...animStyle(data.animState), ...compatStyle(compat) },
      global: { display:'flex', alignItems:'center', gap:6, padding:'5px 10px',
                borderBottom:`1px solid ${C.LINE}`,
                fontFamily:C.DISP, fontSize:8, color:'rgba(255,34,34,0.5)', letterSpacing:'0.14em' },
      ta:     { width:'100%', background:'#000', border:`1px solid ${C.LINE2}`, borderRadius:0,
                color:C.FG1, fontFamily:C.TERM, fontSize:13, padding:'8px', resize:'none',
                outline:'none', boxSizing:'border-box', lineHeight:1.4 },
      send:   { width:'100%', padding:'7px', background:C.RED, border:'none', color:'#000',
                fontFamily:C.DISP, fontSize:10, fontWeight:700, letterSpacing:'0.12em',
                textTransform:'uppercase', cursor:'pointer' },
    };

    return (
      <div style={{ position:'relative' }}>
        {insight && (
          <InsightCard text={insight} countdown={countdown}
            onInsert={() => { setText(insight); setInsight(null); }}
            onDismiss={() => setInsight(null)} />
        )}
        <div style={ns.card}>
          <AllHandles />
          <NodeHeader dot={C.RED} label="INPUT" nodeId={id} pinned={data.pinned} />
          <CompatLabel compat={compat} />
          {/* global mode indicator */}
          <div style={ns.global}>
            <span style={{ width:5, height:5, background:'rgba(255,34,34,0.5)' }} />
            JARVIS // GLOBAL
          </div>
          {/* text area */}
          <div style={{ padding:'8px 10px 0' }}>
            <textarea rows={3} value={text} onChange={e => setText(e.target.value)}
              placeholder="address JARVIS..." style={ns.ta} />
          </div>
          {/* send */}
          <div style={{ padding:'8px 10px' }}>
            <form onSubmit={handleSend}>
              <button type="submit" style={ns.send}>Send</button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  /* ─────────────── SESSION NODE ─────────────── */
  function SessionNode({ data, id }) {
    const compatS = useCompatState('sessionNode');
    const { streamText='', isStreaming=false, messages=[] } = data;
    // global = the permanent JARVIS session (kind=global) or the static demo node
    // (no conversation_id). config is spread flat into data by neoToRF, so read data.kind.
    const isGlobal = data.kind === 'global' || !data.conversation_id;
    // single chat drawer lives on the static 'session' node; it follows the wired
    // session (Canvas.jsx swaps its messages to the Input→Session target).
    const hasChat  = id === 'session';

    const ns = {
      card:   { ...S.nodeCard, width:300, borderLeft:'2px solid rgba(139,92,246,0.7)', ...animStyle(data.animState) },
      label:  { fontFamily:C.DISP, fontSize:8, color:'rgba(139,92,246,0.6)', letterSpacing:'0.14em' },
    };

    return (
      <div style={{ ...ns.card, ...compatStyle(compatS) }}>
        <AllHandles />
        <CompatLabel compat={compatS} />
        <div style={{ ...S.nodeHeader }}>
          <span style={{ width:8, height:8, background:'rgba(139,92,246,0.9)', flexShrink:0,
            boxShadow:'0 0 6px rgba(139,92,246,0.6)',
            animation: data.animState==='processing' ? 'pulse 0.6s ease-in-out infinite' : 'pulse 2s ease-in-out infinite' }} />
          <div>
            <div style={{ fontFamily:C.TERM, fontSize:13, color:C.FG2 }}>
              {isGlobal ? 'GLOBAL SESSION' : 'AI SESSION'}
            </div>
            <div style={ns.label}>
              {isGlobal
                ? 'JARVIS // PERSISTENT'
                : (data.conversation_id.slice(0,8) + '…')}
            </div>
          </div>
          <NodeControls nodeId={id} pinned={data.pinned} />
        </div>

        {hasChat && (
          <SessionOutputPanel
            session={null}
            streamText={streamText}
            isStreaming={isStreaming}
            messages={messages}
          />
        )}
      </div>
    );
  }

  /* ─────────────── PHYSICS PANEL (inside CONFIG) ─────────────── */
  function PhysicsPanel({ ns }) {
    const [open, setOpen] = React.useState(false);
    const [phys, setPhys] = React.useState(() =>
      window.NIM_SIM?.getPhys() || { repulsion:-1200, linkDist:220, linkStr:0.06, decay:0.45 }
    );
    function update(key, val) {
      setPhys(p => ({ ...p, [key]: val }));
      window.NIM_SIM?.set(key, val);
    }
    const rows = [
      ['REPULSION', 'repulsion', -3000, -200, 100, v => v],
      ['LINK DIST',  'linkDist',  80,    400,  10,  v => v],
      ['LINK STR',   'linkStr',   0.01,  0.3,  0.01, v => v.toFixed(2)],
      ['FRICTION',   'decay',     0.2,   0.9,  0.05, v => v.toFixed(2)],
    ];
    return (
      <div style={{ ...ns.sec, borderBottom:`1px solid ${C.LINE}` }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', cursor:'pointer' }}
          onClick={() => setOpen(o => !o)}>
          <div style={ns.sLbl}>Physics</div>
          <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG5 }}>{open?'▲':'▼'}</span>
        </div>
        {open && rows.map(([label, key, mn, mx, step, fmt]) => (
          <div key={key} style={ns.slRow}>
            <span style={ns.slLbl}>{label}</span>
            <input type="range" min={mn} max={mx} step={step} value={phys[key]}
              onChange={e => update(key, parseFloat(e.target.value))}
              style={{ flex:1, accentColor:'rgba(139,92,246,0.9)', height:4 }} />
            <span style={ns.slVal}>{fmt(phys[key])}</span>
          </div>
        ))}
      </div>
    );
  }

  /* ─────────────── CONFIG NODE ─────────────── */
  const UNIT_ASCII = `   ▄███▄\n  █ ◆ ◆ █\n  █ ▀▀▀ █\n   ▀███▀\n  ▄█████▄\n ██  ▲  ██\n  ▀▀▀▀▀▀▀`;

  function ConfigNode({ data, id }) {
    const models = data.models || [];
    const [model,  setModel]  = React.useState('auto');
    const [pOpen,  setPOpen]  = React.useState(false);
    const [params, setParams] = React.useState({ temp:0.8, tokens:1024, topp:0.9 });
    const sp = (k,v) => setParams(p => ({ ...p, [k]:v }));

    const ns = {
      card:  { ...S.nodeCard, width:280, ...animStyle(data.animState) },
      sec:   { padding:'7px 10px', borderBottom:`1px solid ${C.LINE}` },
      sLbl:  { fontFamily:C.DISP, fontSize:8, color:C.FG5, letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:6 },
      pill:  (a) => ({ padding:'3px 8px', border:`1px solid ${a?C.RED:C.LINE2}`,
                       background:a?C.RED:'none', color:a?'#000':C.FG3,
                       fontFamily:C.DISP, fontSize:8, letterSpacing:'0.06em', cursor:'pointer' }),
      slRow: { display:'flex', alignItems:'center', gap:6, marginBottom:4 },
      slLbl: { fontFamily:C.DISP, fontSize:8, color:C.FG4, letterSpacing:'0.06em', minWidth:40 },
      slVal: { fontFamily:C.TERM, fontSize:11, color:C.FG3, minWidth:32, textAlign:'right' },
      uBox:  { border:`1px solid ${C.LINE2}`, position:'relative', margin:'8px 10px' },
      uHdr:  { display:'flex', justifyContent:'space-between', padding:'4px 8px', borderBottom:`1px solid ${C.LINE}` },
      ascii: { fontFamily:C.TERM, fontSize:10, color:C.FG5, lineHeight:1.1, padding:'6px 8px', whiteSpace:'pre', textAlign:'center' },
      uFtr:  { fontFamily:C.DISP, fontSize:7, color:C.FG5, textAlign:'center', padding:'3px 6px', borderTop:`1px solid ${C.LINE}`, letterSpacing:'0.06em' },
    };

    return (
      <div style={{ ...ns.card, ...compatStyle(useCompatState('configNode')) }}>
        <AllHandles />
        <NodeHeader dot={C.RED} label="CONFIG" nodeId={id} pinned={data.pinned} />
        <div style={ns.sec}>
          <div style={ns.sLbl}>Model</div>
          <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
            {models.map(m => <button key={m.id} style={ns.pill(model===m.id)} onClick={() => setModel(m.id)}>{m.label}</button>)}
          </div>
        </div>
        <div style={ns.sec}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', cursor:'pointer' }}
            onClick={() => setPOpen(o => !o)}>
            <div style={ns.sLbl}>Params</div>
            <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG5 }}>{pOpen?'▲':'▼'}</span>
          </div>
          {pOpen && (
            <div style={{ marginTop:6 }}>
              {[['TEMP','temp',0,2,0.05,v=>v.toFixed(2)],['TOKENS','tokens',256,4096,256,v=>v],['TOP-P','topp',0,1,0.05,v=>v.toFixed(2)]].map(([l,k,mn,mx,st,fmt])=>(
                <div key={k} style={ns.slRow}>
                  <span style={ns.slLbl}>{l}</span>
                  <input type="range" min={mn} max={mx} step={st} value={params[k]}
                    onChange={e => sp(k, parseFloat(e.target.value))}
                    style={{ flex:1, accentColor:C.RED, height:4 }} />
                  <span style={ns.slVal}>{fmt(params[k])}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ ...ns.sec, borderBottom:'none' }}>
          <div style={ns.sLbl}>Cost</div>
          <span style={{ fontFamily:C.TERM, fontSize:12, color:C.FG3 }}>$25.00 / 30d limit</span>
        </div>

        {/* physics panel */}
        <PhysicsPanel ns={ns} />

        {/* arrange / reheat */}
        <div style={{ padding:'6px 10px', borderTop:`1px solid ${C.LINE}`, display:'flex', gap:5 }}>
          <button
            style={{ flex:1, padding:'5px', background:'none',
              border:`1px solid ${C.LINE2}`, color:C.FG5,
              fontFamily:C.DISP, fontSize:8, letterSpacing:'0.1em',
              textTransform:'uppercase', cursor:'pointer', transition:'all 0.1s' }}
            onMouseEnter={e=>{e.currentTarget.style.color=C.RED;e.currentTarget.style.borderColor=C.RED;}}
            onMouseLeave={e=>{e.currentTarget.style.color=C.FG5;e.currentTarget.style.borderColor=C.LINE2;}}
            onClick={() => window.NIM_SIM?.reheat(1) || window.NIM_CANVAS_CB?.onAutoArrange?.()}>
            ARRANGE
          </button>
          <button
            style={{ flex:1, padding:'5px', background:'none',
              border:`1px solid ${C.LINE2}`, color:C.FG5,
              fontFamily:C.DISP, fontSize:8, letterSpacing:'0.1em',
              textTransform:'uppercase', cursor:'pointer', transition:'all 0.1s' }}
            onMouseEnter={e=>{e.currentTarget.style.color='rgba(139,92,246,0.9)';e.currentTarget.style.borderColor='rgba(139,92,246,0.5)';}}
            onMouseLeave={e=>{e.currentTarget.style.color=C.FG5;e.currentTarget.style.borderColor=C.LINE2;}}
            onClick={() => window.NIM_SIM?.reheat(0.4)}>
            REHEAT
          </button>
        </div>
        <div style={ns.uBox}>
          {[{top:-1,left:-1,bw:'2px 0 0 2px'},{top:-1,right:-1,bw:'2px 2px 0 0'},{bottom:-1,left:-1,bw:'0 0 2px 2px'},{bottom:-1,right:-1,bw:'0 2px 2px 0'}].map((t,i)=>(
            <span key={i} style={{ position:'absolute', width:8, height:8, borderColor:C.RED, borderStyle:'solid', borderWidth:t.bw, ...t }} />
          ))}
          <div style={ns.uHdr}>
            <span style={{ fontFamily:C.DISP, fontSize:8, color:C.FG3, letterSpacing:'0.08em' }}>UNIT 01</span>
            <span style={{ fontFamily:C.DISP, fontSize:8, color:C.AMB, letterSpacing:'0.06em' }}>STANDBY</span>
          </div>
          <div style={ns.ascii}>{UNIT_ASCII}</div>
          <div style={ns.uFtr}>PLACEHOLDER · SWAP SPRITE / IMG</div>
        </div>
      </div>
    );
  }

  /* ─────────────── MEMORY NODE ─────────────── */
  function MemoryNode({ data, id }) {
    const mem       = data.mem || { factCount:0, sections:[], topFact:null };
    const isExp     = data.isExpanded || false;
    const topSec    = mem.sections.find(s => s.name === mem.topFact?.section);

    const ns = {
      card:  { ...S.nodeCard, width:260, ...animStyle(data.animState) },
      count: { fontFamily:C.TERM, fontSize:13, color:C.FG3, padding:'8px 10px', borderBottom:`1px solid ${C.LINE}` },
      secs:  { display:'flex', gap:6, padding:'8px 10px', flexWrap:'wrap', borderBottom:`1px solid ${C.LINE}` },
      dot:   (c) => ({ width:7, height:7, background:c, boxShadow:`0 0 4px ${c}` }),
      sLbl:  { fontFamily:C.DISP, fontSize:8, letterSpacing:'0.08em', textTransform:'uppercase' },
      bar:   { height:3, background:'rgba(255,34,34,0.1)', margin:'7px 10px 0', position:'relative' },
      barFl: (c,w) => ({ position:'absolute', top:0, left:0, height:'100%', width:`${w*100}%`, background:c,
                         transition:'width 0.4s ease', boxShadow:`0 0 6px ${c}` }),
      hint:  { fontFamily:C.DISP, fontSize:8, color: isExp?'rgba(139,92,246,0.8)':C.FG5,
               textAlign:'center', letterSpacing:'0.1em', padding:'7px 10px',
               borderTop:`1px solid ${C.LINE}`, cursor:'pointer',
               background: isExp?'rgba(139,92,246,0.06)':'transparent',
               transition:'all 0.15s' },
    };

    return (
      <div style={{ ...ns.card, ...compatStyle(useCompatState('memoryNode')) }}>
        <AllHandles />
        <NodeHeader dot={C.GRN} label="MEMORY" nodeId={id} pinned={data.pinned}
          extra={
            <span style={{ width:7, height:7, background:C.GRN,
              boxShadow:`0 0 5px ${C.GRN}`,
              animation: data.animState==='processing' ? 'pulse 0.5s ease-in-out infinite' : 'pulse 2.5s ease-in-out infinite' }} />
          } />
        <div style={ns.count}>{mem.factCount} facts · {mem.sections.length} sections</div>
        <div style={ns.secs}>
          {mem.sections.map(s => (
            <div key={s.name} style={{ display:'inline-flex', alignItems:'center', gap:4 }}>
              <span style={ns.dot(s.color)} />
              <span style={{ ...ns.sLbl, color:s.color }}>{s.name}</span>
            </div>
          ))}
        </div>
        {mem.topFact && (
          <>
            <div style={{ padding:'6px 10px 0', fontFamily:C.TERM, fontSize:11, color:C.FG4 }}>
              {mem.topFact.text}
            </div>
            <div style={ns.bar}>
              <div style={ns.barFl(topSec?.color || C.GRN, mem.topFact.salience || 0.9)} />
            </div>
          </>
        )}
        <div style={ns.hint}
          onClick={() => window.NIM_CANVAS_CB?.onMemExpand?.()}
          onMouseEnter={e => { if (!isExp) e.currentTarget.style.color=C.FG3; }}
          onMouseLeave={e => { e.currentTarget.style.color = isExp?'rgba(139,92,246,0.8)':C.FG5; }}>
          {isExp ? 'CLICK TO COLLAPSE' : 'CLICK TO EXPAND'}
        </div>
      </div>
    );
  }

  Object.assign(window, { InputNode, SessionNode, ConfigNode, MemoryNode });
})();
