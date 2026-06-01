/* NIM // CANVAS — Memory branch nodes (Edit / History / Graph).
   Requires: D3 v7 (window.d3), NIM_CANVAS_C, NIM_CANVAS_S, NIM_CANVAS_DATA */
(function () {
  const C = window.NIM_CANVAS_C;
  const S = window.NIM_CANVAS_S;
  const D = window.NIM_CANVAS_DATA;
  const { Handle, Position } = window.ReactFlow;

  const TYPE_COLORS = { user:'#27d8ff', project:'#ffb000', stack:'#3dff6e', preference:'#ff2222', goal:'#a78bfa' };

  function BranchHeader({ icon, label, nodeId }) {
    return (
      <div style={{ ...S.nodeHeader, borderLeft:'2px solid rgba(139,92,246,0.7)', justifyContent:'space-between' }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span style={{ width:8, height:8, background:'rgba(139,92,246,0.8)', boxShadow:'0 0 6px rgba(139,92,246,0.5)' }} />
          <span style={{ ...S.nodeLabel, color:'rgba(139,92,246,0.9)' }}>{icon} {label}</span>
        </div>
        <button style={{ background:'none', border:'1px solid #4a4a4a', color:'#5a5a5a', cursor:'pointer',
          fontFamily:C.DISP, fontSize:8, padding:'2px 6px', letterSpacing:'0.06em' }}
          onClick={() => window.NIM_CANVAS_CB?.onRemoveBranch?.(nodeId)}>X</button>
      </div>
    );
  }

  /* ─────────────── MEMORY · EDIT ─────────────── */
  function MemoryEditNode() {
    const secs = ['USER','STACK','PROJECT','GOALS'];
    const secColors = { USER:'#27d8ff', STACK:'#3dff6e', PROJECT:'#ffb000', GOALS:'#ff2222' };
    const [sec, setSec]   = React.useState('STACK');
    const [text, setText] = React.useState(D.MOCK_MEMORY_EDIT['STACK']);
    const [saved, setSaved] = React.useState(false);

    function handleSec(s) { setSec(s); setText(D.MOCK_MEMORY_EDIT[s]); setSaved(false); }
    function handleSave() { setSaved(true); setTimeout(() => setSaved(false), 1600); }

    const ns = {
      card: { ...S.nodeCard, width:280, borderLeft:'2px solid rgba(139,92,246,0.7)' },
      pills:{ display:'flex', gap:4, padding:'7px 10px', borderBottom:`1px solid ${C.LINE}`, flexWrap:'wrap' },
      pill: (a,c) => ({ padding:'2px 8px', border:`1px solid ${a?c:'#4a4a4a'}`, background:a?c+'22':'none',
        color:a?c:'#5a5a5a', fontFamily:C.DISP, fontSize:8, letterSpacing:'0.06em', cursor:'pointer' }),
      ta:   { width:'100%', background:'#000', border:`1px solid ${C.LINE2}`, borderRadius:0,
        color:'#94a3b8', fontFamily:C.TERM, fontSize:12, padding:'8px', resize:'none',
        outline:'none', boxSizing:'border-box', lineHeight:1.5, minHeight:110 },
      btns: { display:'flex', gap:6, padding:'7px 10px' },
      save: { flex:1, padding:'5px', background: saved ? '#065f46' : C.RED, border:'none', color: saved ? C.GRN : '#000',
        fontFamily:C.DISP, fontSize:9, fontWeight:700, letterSpacing:'0.12em', cursor:'pointer' },
      cncl: { padding:'5px 10px', background:'none', border:`1px solid ${C.LINE2}`, color:C.FG4,
        fontFamily:C.DISP, fontSize:9, letterSpacing:'0.08em', cursor:'pointer' },
    };
    return (
      <div style={ns.card}>
        <Handle type="target" position={Position.Left} style={{ ...S.handle, left:-5 }} />
        <BranchHeader icon="[E]" label="MEMORY · EDIT" nodeId="mem-edit" />
        <div style={ns.pills}>
          {secs.map(s => <button key={s} style={ns.pill(sec===s, secColors[s])} onClick={() => handleSec(s)}>{s}</button>)}
        </div>
        <div style={{ padding:'8px 10px 0' }}>
          <textarea value={text} onChange={e => setText(e.target.value)} style={ns.ta} />
        </div>
        <div style={ns.btns}>
          <button style={ns.save} onClick={handleSave}>{saved ? 'SAVED' : 'SAVE'}</button>
          <button style={ns.cncl} onClick={() => setText(D.MOCK_MEMORY_EDIT[sec])}>RESET</button>
        </div>
      </div>
    );
  }

  /* ─────────────── MEMORY · HISTORY ─────────────── */
  function MemoryHistoryNode() {
    const hist = D.MOCK_HISTORY;
    const [open, setOpen]     = React.useState(null);
    const [restored, setRst]  = React.useState(null);

    function restore(v) {
      setRst(v);
      setTimeout(() => setRst(null), 1500);
    }

    const ns = {
      card:   { ...S.nodeCard, width:300, borderLeft:'2px solid rgba(139,92,246,0.7)' },
      row:    { padding:'7px 10px', borderBottom:`1px solid ${C.LINE}`, cursor:'pointer' },
      ver:    { fontFamily:C.TERM, fontSize:11, color:'rgba(139,92,246,0.9)', marginRight:8 },
      desc:   { fontFamily:C.DISP, fontSize:9, color:C.FG3, letterSpacing:'0.06em' },
      ts:     { fontFamily:C.DISP, fontSize:8, color:C.FG5, letterSpacing:'0.06em', float:'right' },
      diffWrap:{ padding:'7px 10px', background:'#050505', borderBottom:`1px solid ${C.LINE}` },
      added:  { fontFamily:C.TERM, fontSize:11, color:C.GRN, lineHeight:1.5 },
      removed:{ fontFamily:C.TERM, fontSize:11, color:'#f87171', lineHeight:1.5 },
      same:   { fontFamily:C.TERM, fontSize:11, color:C.FG5, lineHeight:1.5 },
      rst:    (v,r) => ({ marginTop:5, padding:'3px 8px', border:`1px solid ${v===r?C.GRN:'rgba(61,255,110,0.5)'}`,
        color:v===r?C.GRN:'rgba(61,255,110,0.7)', background:'none', fontFamily:C.DISP, fontSize:8,
        letterSpacing:'0.08em', cursor:'pointer' }),
    };

    return (
      <div style={ns.card}>
        <Handle type="target" position={Position.Left} style={{ ...S.handle, left:-5 }} />
        <BranchHeader icon="[H]" label="MEMORY · HISTORY" nodeId="mem-history" />
        <div style={{ maxHeight:280, overflowY:'auto' }} className="nim-scroll">
          {hist.map(h => (
            <React.Fragment key={h.version}>
              <div style={{ ...ns.row, background: open===h.version?'#0d0d0d':'transparent' }}
                onClick={() => setOpen(open===h.version?null:h.version)}>
                <span style={ns.ts}>{h.ts}</span>
                <span style={ns.ver}>{h.version}</span>
                <span style={ns.desc}>{h.desc}</span>
              </div>
              {open === h.version && (
                <div style={ns.diffWrap}>
                  {h.diff.added.map((l,i)   => <div key={'a'+i} style={ns.added}>+ {l}</div>)}
                  {h.diff.removed.map((l,i) => <div key={'r'+i} style={ns.removed}>– {l}</div>)}
                  {h.diff.same.map((l,i)    => <div key={'s'+i} style={ns.same}>  {l}</div>)}
                  <button style={ns.rst(h.version, restored)} onClick={() => restore(h.version)}>
                    {restored===h.version ? 'RESTORED' : 'RESTORE'}
                  </button>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    );
  }

  /* ─────────────── MEMORY · GRAPH (D3) ─────────────── */
  const GRAPH_FILTERS = ['ALL','user','project','stack','preference','goal'];

  function MemoryGraphNode() {
    const svgRef = React.useRef(null);
    const [filter, setFilter] = React.useState('ALL');
    const [tip, setTip]       = React.useState(null);

    React.useEffect(() => {
      const d3 = window.d3;
      if (!d3 || !svgRef.current) return;

      const W = 300, H = 200;
      const allN = D.MOCK_GRAPH.nodes;
      const allL = D.MOCK_GRAPH.links;

      const visNodes = filter === 'ALL' ? allN.map(n => ({...n})) : allN.filter(n => n.type === filter).map(n => ({...n}));
      const visIds   = new Set(visNodes.map(n => n.id));
      const visLinks = allL.filter(l => visIds.has(l.source?.id ?? l.source) && visIds.has(l.target?.id ?? l.target))
                          .map(l => ({ ...l, source: l.source?.id ?? l.source, target: l.target?.id ?? l.target }));

      const svg = d3.select(svgRef.current);
      svg.selectAll('*').remove();

      const sim = d3.forceSimulation(visNodes)
        .force('link', d3.forceLink(visLinks).id(d => d.id).distance(55))
        .force('charge', d3.forceManyBody().strength(-90))
        .force('center', d3.forceCenter(W/2, H/2))
        .force('collide', d3.forceCollide(18));

      const link = svg.append('g').selectAll('line').data(visLinks).join('line')
        .attr('stroke','#2a2a2a').attr('stroke-width',1);

      const node = svg.append('g').selectAll('circle').data(visNodes).join('circle')
        .attr('r', 6).attr('fill', d => TYPE_COLORS[d.type]||'#555')
        .attr('stroke','#000').attr('stroke-width',1)
        .style('cursor','pointer')
        .on('mouseenter', (ev, d) => setTip({ x:ev.offsetX, y:ev.offsetY, d }))
        .on('mouseleave', () => setTip(null))
        .call(d3.drag()
          .on('start', (ev,d) => { if(!ev.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; })
          .on('drag',  (ev,d) => { d.fx=ev.x; d.fy=ev.y; })
          .on('end',   (ev,d) => { if(!ev.active) sim.alphaTarget(0); d.fx=null; d.fy=null; })
        );

      const lbl = svg.append('g').selectAll('text').data(visNodes).join('text')
        .text(d => d.label).attr('font-size',8).attr('fill',C.FG5)
        .attr('font-family',"'JetBrains Mono',monospace").attr('pointer-events','none');

      sim.on('tick', () => {
        link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
        node.attr('cx',d=>d.x).attr('cy',d=>d.y);
        lbl.attr('x',d=>d.x+8).attr('y',d=>d.y+3);
      });
      return () => sim.stop();
    }, [filter]);

    const ns = {
      card:  { ...S.nodeCard, width:320, borderLeft:'2px solid rgba(139,92,246,0.7)' },
      pills: { display:'flex', gap:3, padding:'6px 10px', borderBottom:`1px solid ${C.LINE}`, flexWrap:'wrap' },
      pill:  (a) => ({ padding:'2px 6px', border:`1px solid ${a?'rgba(139,92,246,0.7)':'#4a4a4a'}`,
        background:a?'rgba(139,92,246,0.15)':'none', color:a?'rgba(139,92,246,0.9)':'#5a5a5a',
        fontFamily:C.DISP, fontSize:7, letterSpacing:'0.06em', cursor:'pointer' }),
      svgWrap:{ padding:'4px 8px', position:'relative' },
      tip:   { position:'absolute', background:'#0d0d0d', border:`1px solid ${C.LINE2}`, padding:'4px 7px',
        fontFamily:C.TERM, fontSize:10, color:C.FG3, pointerEvents:'none', zIndex:10,
        whiteSpace:'nowrap', transform:'translateY(-100%)' },
      foot:  { padding:'5px 10px', borderTop:`1px solid ${C.LINE}`, fontFamily:C.DISP, fontSize:7,
        color:C.FG5, letterSpacing:'0.08em', textTransform:'uppercase' },
    };

    return (
      <div style={ns.card} className="nodrag">
        <Handle type="target" position={Position.Left} style={{ ...S.handle, left:-5 }} />
        <BranchHeader icon="[G]" label="MEMORY · GRAPH" nodeId="mem-graph" />
        <div style={ns.pills}>
          {GRAPH_FILTERS.map(f => (
            <button key={f} style={ns.pill(filter===f)} onClick={() => setFilter(f)}>
              {f.toUpperCase()}
            </button>
          ))}
        </div>
        <div style={ns.svgWrap}>
          {tip && (
            <div style={{ ...ns.tip, left:tip.x, top:tip.y }}>
              {tip.d.label} · <span style={{ color:TYPE_COLORS[tip.d.type]||'#555' }}>{tip.d.type}</span>
            </div>
          )}
          <svg ref={svgRef} width={300} height={200} style={{ display:'block', background:'#050505' }} />
        </div>
        <div style={ns.foot}>LIVE DATA UNAVAILABLE · CONNECT BACKEND</div>
      </div>
    );
  }

  Object.assign(window, { MemoryEditNode, MemoryHistoryNode, MemoryGraphNode });
})();
