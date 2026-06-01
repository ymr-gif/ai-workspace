/* NIM // CANVAS — Memory branch nodes: Edit, History, Graph
   Exports: window.MemoryEditNode, window.MemoryHistoryNode, window.MemoryGraphNode */
(function () {
  const C = window.NIM_CANVAS_C;
  const S = window.NIM_CANVAS_S;
  const { Handle, Position } = window.ReactFlow;

  const VIO = 'rgba(139,92,246,0.75)';

  /* shared branch card style */
  function branchCard(w) {
    return { ...S.nodeCard, width: w || 260, borderLeft: `2px solid ${VIO}` };
  }

  /* shared header for branch nodes */
  function BranchHeader({ label, onClose }) {
    return (
      <div style={{ ...S.nodeHeader, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, background: VIO, boxShadow: `0 0 5px ${VIO}` }} />
          <span style={{ fontFamily: C.DISP, fontSize: 9, color: VIO,
            letterSpacing: '0.12em', textTransform: 'uppercase' }}>{label}</span>
        </div>
        <button style={{ background: 'none', border: 'none', color: C.FG5, cursor: 'pointer',
          fontFamily: C.DISP, fontSize: 8, padding: '0 2px' }}
          onClick={onClose}>✕</button>
      </div>
    );
  }

  /* shared handles */
  function BranchHandles() {
    return (
      <React.Fragment>
        <Handle type="target" position={Position.Left}   id="t-left"  style={{ ...S.handle, left: -5 }} />
        <Handle type="source" position={Position.Right}  id="s-right" style={{ ...S.handle, right: -5 }} />
        <Handle type="target" position={Position.Top}    id="t-top"   style={{ ...S.handle, top: -5 }} />
        <Handle type="source" position={Position.Bottom} id="s-bot"   style={{ ...S.handle, bottom: -5 }} />
      </React.Fragment>
    );
  }

  function dismiss(id) {
    window.NIM_CANVAS_CB?.onRemoveBranch?.(id);
  }

  /* ── MEMORY EDIT NODE ── */
  function MemoryEditNode({ data, id }) {
    const [text, setText] = React.useState('');
    const [saved, setSaved] = React.useState(false);
    const [section, setSection] = React.useState('USER');
    const SECTIONS = ['USER', 'STACK', 'PROJECT', 'GOALS'];

    function handleSave() {
      if (!text.trim()) return;
      /* Stage 5: POST /api/memory/edit — wire here in production */
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
      setText('');
    }

    const ns = {
      body:    { padding: '8px 10px' },
      tabs:    { display: 'flex', gap: 4, marginBottom: 8 },
      tab:     (a) => ({ fontFamily: C.DISP, fontSize: 7, letterSpacing: '0.08em',
        padding: '3px 7px', cursor: 'pointer', border: `1px solid ${a ? VIO : C.LINE2}`,
        background: a ? 'rgba(139,92,246,0.12)' : 'none',
        color: a ? VIO : C.FG5 }),
      area:    { width: '100%', minHeight: 70, background: '#0a0a0a',
        border: `1px solid ${C.LINE}`, color: C.FG2, fontFamily: C.TERM,
        fontSize: 12, padding: '6px 8px', resize: 'vertical', outline: 'none',
        boxSizing: 'border-box' },
      saveBtn: { marginTop: 6, width: '100%', padding: '5px', background: 'none',
        border: `1px solid ${saved ? C.GRN : VIO}`, color: saved ? C.GRN : VIO,
        fontFamily: C.DISP, fontSize: 8, letterSpacing: '0.1em',
        textTransform: 'uppercase', cursor: 'pointer', transition: 'all 0.15s' },
      hint:    { fontFamily: C.DISP, fontSize: 7, color: C.FG5, marginTop: 4,
        letterSpacing: '0.06em', textAlign: 'center' },
    };

    return (
      <div style={branchCard(280)}>
        <BranchHandles />
        <BranchHeader label="MEM / EDIT" onClose={() => dismiss(id)} />
        <div style={ns.body}>
          <div style={ns.tabs}>
            {SECTIONS.map(s => (
              <span key={s} style={ns.tab(s === section)} onClick={() => setSection(s)}>{s}</span>
            ))}
          </div>
          <textarea
            style={ns.area}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder={`Add a ${section} memory fact...`}
            className="nim-scroll"
          />
          <button style={ns.saveBtn} onClick={handleSave}>
            {saved ? '✓ SAVED' : 'WRITE MEMORY'}
          </button>
          <div style={ns.hint}>→ POST /api/memory/edit</div>
        </div>
      </div>
    );
  }

  /* ── MEMORY HISTORY NODE ── */
  function MemoryHistoryNode({ data, id }) {
    const MOCK = [
      { v: 'v7', ts: '2h ago', desc: 'Added React context note',      diff: '+1 fact' },
      { v: 'v6', ts: '5h ago', desc: 'Updated stack: Vite → Next.js', diff: '~1 fact' },
      { v: 'v5', ts: '1d ago', desc: 'New goals block written',        diff: '+3 facts' },
      { v: 'v4', ts: '2d ago', desc: 'User pref: dark mode always',    diff: '+1 fact' },
      { v: 'v3', ts: '3d ago', desc: 'Initial scaffold',               diff: '+8 facts' },
    ];
    const history = data.history || MOCK;
    const [sel, setSel] = React.useState(null);

    const ns = {
      list:  { maxHeight: 200, overflowY: 'auto', borderTop: `1px solid ${C.LINE}` },
      row:   (a) => ({ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 10px', borderBottom: `1px solid ${C.LINE}`,
        background: a ? 'rgba(139,92,246,0.08)' : 'transparent', cursor: 'pointer',
        transition: 'background 0.1s' }),
      ver:   { fontFamily: C.DISP, fontSize: 8, color: VIO, letterSpacing: '0.08em' },
      desc:  { fontFamily: C.TERM, fontSize: 11, color: C.FG3, flex: 1, margin: '0 8px' },
      diff:  { fontFamily: C.DISP, fontSize: 7, color: C.FG5, letterSpacing: '0.06em' },
      ts:    { fontFamily: C.DISP, fontSize: 7, color: C.FG5, textAlign: 'right', marginTop: 1 },
      empty: { fontFamily: C.TERM, fontSize: 11, color: C.FG5, textAlign: 'center', padding: '16px 0' },
      restoreBtn: { display: 'block', width: 'calc(100% - 20px)', margin: '8px 10px',
        padding: '5px', background: 'none', border: `1px solid ${C.LINE2}`, color: C.FG5,
        fontFamily: C.DISP, fontSize: 7, letterSpacing: '0.1em',
        textTransform: 'uppercase', cursor: 'pointer' },
    };

    return (
      <div style={branchCard(280)}>
        <BranchHandles />
        <BranchHeader label="MEM / HISTORY" onClose={() => dismiss(id)} />
        <div style={ns.list} className="nim-scroll">
          {history.length === 0
            ? <div style={ns.empty}>no history yet</div>
            : history.map((h, i) => (
              <div key={i} style={ns.row(sel === i)} onClick={() => setSel(sel === i ? null : i)}>
                <span style={ns.ver}>{h.v}</span>
                <span style={ns.desc}>{h.desc}</span>
                <div>
                  <div style={ns.diff}>{h.diff}</div>
                  <div style={ns.ts}>{h.ts}</div>
                </div>
              </div>
          ))}
        </div>
        {sel !== null && (
          <button style={ns.restoreBtn}
            onMouseEnter={e => { e.currentTarget.style.color = VIO; e.currentTarget.style.borderColor = VIO; }}
            onMouseLeave={e => { e.currentTarget.style.color = C.FG5; e.currentTarget.style.borderColor = C.LINE2; }}>
            RESTORE {history[sel]?.v}
          </button>
        )}
      </div>
    );
  }

  /* ── MEMORY GRAPH NODE ── */
  function MemoryGraphNode({ data, id }) {
    const canvasRef = React.useRef(null);
    const [hovered, setHovered] = React.useState(null);

    /* mini force graph — pure canvas, no d3 dependency from here */
    const NODES = [
      { id:'user',    label:'USER',    color:'#27d8ff', x:0.5, y:0.2, r:12 },
      { id:'stack',   label:'STACK',   color:'#3dff6e', x:0.2, y:0.5, r:10 },
      { id:'project', label:'PROJECT', color:'#ffb000', x:0.8, y:0.5, r:10 },
      { id:'goals',   label:'GOALS',   color:'#ff2222', x:0.35,y:0.8, r:8  },
      { id:'pref',    label:'PREF',    color:'#8888ff', x:0.65,y:0.8, r:8  },
    ];
    const LINKS = [
      ['user','stack'],['user','project'],['user','goals'],
      ['stack','project'],['goals','pref'],['project','pref'],
    ];

    React.useEffect(() => {
      const cv = canvasRef.current;
      if (!cv) return;
      const ctx = cv.getContext('2d');
      const W = cv.width, H = cv.height;

      function draw() {
        ctx.clearRect(0, 0, W, H);
        /* links */
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.lineWidth = 1;
        LINKS.forEach(([a, b]) => {
          const na = NODES.find(n => n.id === a);
          const nb = NODES.find(n => n.id === b);
          ctx.beginPath();
          ctx.moveTo(na.x * W, na.y * H);
          ctx.lineTo(nb.x * W, nb.y * H);
          ctx.stroke();
        });
        /* nodes */
        NODES.forEach(n => {
          const isH = hovered === n.id;
          ctx.beginPath();
          ctx.arc(n.x * W, n.y * H, isH ? n.r + 3 : n.r, 0, Math.PI * 2);
          ctx.fillStyle = isH ? n.color : n.color + '99';
          ctx.fill();
          if (isH) {
            ctx.shadowColor = n.color;
            ctx.shadowBlur  = 10;
            ctx.fill();
            ctx.shadowBlur  = 0;
          }
          ctx.fillStyle = 'rgba(0,0,0,0.8)';
          ctx.font = '7px monospace';
          ctx.textAlign = 'center';
          ctx.fillText(n.label, n.x * W, n.y * H + n.r + 10);
        });
      }
      draw();
    }, [hovered]);

    function onMouseMove(e) {
      const cv = canvasRef.current;
      if (!cv) return;
      const r  = cv.getBoundingClientRect();
      const mx = (e.clientX - r.left) / r.width;
      const my = (e.clientY - r.top)  / r.height;
      const hit = NODES.find(n => {
        const dx = n.x - mx, dy = n.y - my;
        return Math.sqrt(dx*dx + dy*dy) < 0.09;
      });
      setHovered(hit ? hit.id : null);
    }

    const ns = {
      body:  { padding: '8px 10px' },
      hint:  { fontFamily: C.DISP, fontSize: 7, color: C.FG5,
        letterSpacing: '0.06em', textAlign: 'center', marginTop: 4 },
      lbl:   { fontFamily: C.DISP, fontSize: 7, color: C.FG5,
        letterSpacing: '0.08em', marginBottom: 4 },
      neo:   { fontFamily: C.TERM, fontSize: 10, color: 'rgba(61,255,110,0.6)',
        padding: '4px 6px', background: 'rgba(61,255,110,0.04)',
        border: '1px solid rgba(61,255,110,0.15)', marginTop: 6 },
    };

    return (
      <div style={branchCard(280)}>
        <BranchHandles />
        <BranchHeader label="MEM / GRAPH" onClose={() => dismiss(id)} />
        <div style={ns.body}>
          <div style={ns.lbl}>SECTION GRAPH</div>
          <canvas
            ref={canvasRef}
            width={240} height={160}
            style={{ display: 'block', cursor: 'crosshair', background: '#050505',
              border: `1px solid ${C.LINE}` }}
            onMouseMove={onMouseMove}
            onMouseLeave={() => setHovered(null)}
          />
          {hovered && (
            <div style={{ fontFamily: C.DISP, fontSize: 7, color: VIO,
              letterSpacing: '0.08em', marginTop: 4 }}>
              {NODES.find(n => n.id === hovered)?.label} — {
                LINKS.filter(([a,b]) => a===hovered || b===hovered).length
              } connections
            </div>
          )}
          <div style={ns.neo}>
            neo4j: MATCH (m:Memory) RETURN m LIMIT 25
          </div>
          <div style={ns.hint}>→ GET /api/memory/graph (Stage 5)</div>
        </div>
      </div>
    );
  }

  Object.assign(window, { MemoryEditNode, MemoryHistoryNode, MemoryGraphNode });
})();
