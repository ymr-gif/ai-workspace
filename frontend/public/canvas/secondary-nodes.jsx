/* NIM // CANVAS — Files node. Exports: FilesNode */
(function () {
  const C = window.NIM_CANVAS_C;
  const S = window.NIM_CANVAS_S;
  const { Handle, Position } = window.ReactFlow;

  const SC = (st) => ({
    ready:      { bg:'rgba(61,255,110,0.12)',  color:'#3dff6e' },
    processing: { bg:'rgba(255,176,0,0.12)',   color:'#ffb000' },
    failed:     { bg:'rgba(255,34,34,0.12)',   color:'#ff2222' },
  }[st] || { bg:'rgba(100,100,100,0.12)', color:'#5a5a5a' });

  const _CORE_NODES = new Set(['input', 'session', 'memory', 'config']);
  function NodeControls({ nodeId, pinned }) {
    // real Neo4j nodes (ai-{uuid}) guard by the backend `protected` flag
    const canClose = !_CORE_NODES.has(nodeId) && !window.NIM_PROTECTED_IDS?.has(nodeId);
    const b = {
      background:'none', border:'none', cursor:'pointer',
      fontFamily:C.DISP, fontSize:10, padding:'0 2px', lineHeight:1,
      transition:'color 0.1s', color:C.FG5,
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

  /* ─────────────── FILES NODE ─────────────── */
  function FilesNode({ data, id }) {
    const [files, setFiles]     = React.useState(data.files || []);
    const [url, setUrl]         = React.useState('');
    const [fetching, setFetch]  = React.useState(false);

    function toggleAttach(id) {
      setFiles(fs => fs.map(f => f.id===id ? {...f, attached:!f.attached} : f));
    }
    function handleFetch() {
      if (!url.trim()) return;
      setFetch(true);
      setTimeout(() => {
        setFiles(fs => [...fs, { id:'f'+Date.now(), filename:url.split('/').pop()||'fetched.md', status:'processing', attached:false }]);
        setUrl(''); setFetch(false);
      }, 1200);
    }

    const attachedCount = files.filter(f=>f.attached).length;
    const ns = {
      card:   { ...S.nodeCard, width:300, ...((window.getAnimStyle||((s)=>({})))(data.animState)) },
      hdr:    { ...S.nodeHeader, justifyContent:'space-between' },
      hLabel: { display:'flex', alignItems:'center', gap:7 },
      dot:    { width:8, height:8, background:C.AMB, flexShrink:0, boxShadow:`0 0 5px ${C.AMB}` },
      badge:  (n) => n>0 ? { display:'inline-flex', alignItems:'center', justifyContent:'center',
        minWidth:16, height:16, borderRadius:0, background:C.AMB, color:'#000',
        fontFamily:C.DISP, fontSize:8, fontWeight:700, padding:'0 3px' } : null,
      sec:    { padding:'6px 10px', borderBottom:`1px solid ${C.LINE}` },
      sLbl:   { fontFamily:C.DISP, fontSize:7, color:C.FG5, letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:5 },
      urlRow: { display:'flex', gap:4 },
      urlIn:  { flex:1, background:'#000', border:`1px solid ${C.LINE2}`, color:C.FG2, fontFamily:C.TERM,
                fontSize:11, padding:'4px 6px', outline:'none', borderRadius:0 },
      fetchB: { padding:'4px 8px', background:'none', border:`1px solid rgba(61,255,110,0.6)`,
                color:'#3dff6e', fontFamily:C.DISP, fontSize:8, cursor:'pointer', letterSpacing:'0.06em' },
      upB:    { padding:'4px 8px', background:'none', border:`1px solid rgba(39,216,255,0.6)`,
                color:C.CYN, fontFamily:C.DISP, fontSize:8, cursor:'pointer', letterSpacing:'0.06em' },
      fileRow:{ display:'flex', alignItems:'center', gap:6, padding:'5px 10px', borderBottom:`1px solid ${C.LINE}` },
      chip:   (st) => ({ padding:'2px 5px', fontFamily:C.DISP, fontSize:7, fontWeight:700,
                letterSpacing:'0.06em', background:SC(st).bg, color:SC(st).color, flexShrink:0 }),
      fname:  { flex:1, fontFamily:C.TERM, fontSize:11, color:C.FG3, overflow:'hidden',
                textOverflow:'ellipsis', whiteSpace:'nowrap' },
      iconBtn:{ background:'none', border:'none', color:C.FG5, cursor:'pointer', fontFamily:C.DISP,
                fontSize:10, padding:'0 2px', lineHeight:1 },
      attBtn: (a) => ({ ...{background:'none', border:`1px solid ${a?C.GRN:C.LINE2}`, color:a?C.GRN:C.FG5,
                cursor:'pointer', fontFamily:C.DISP, fontSize:8, padding:'1px 5px', letterSpacing:'0.04em'} }),
    };

    return (
      <div style={ns.card}>
        <Handle type="target" position={Position.Left}  style={{ ...S.handle, left:-5 }} />
        <div style={ns.hdr}>
          <div style={ns.hLabel}>
            <span style={ns.dot} />
            <span style={S.nodeLabel}>FILES</span>
          </div>
          {attachedCount > 0 && <span style={ns.badge(attachedCount)}>{attachedCount} ATT</span>}
          <NodeControls nodeId={id} pinned={data.pinned} />
        </div>

        {/* File list */}
        <div style={{ maxHeight:160, overflowY:'auto' }} className="nim-scroll">
          {files.map(f => (
            <div key={f.id} style={ns.fileRow}>
              <span style={ns.chip(f.status)}>{f.status.slice(0,4).toUpperCase()}</span>
              <span style={ns.fname} title={f.filename}>{f.filename}</span>
              <button style={ns.iconBtn} title="View">V</button>
              <button style={ns.iconBtn} title="Download">D</button>
              <button onClick={() => toggleAttach(f.id)} style={ns.attBtn(f.attached)} title={f.attached?'Detach':'Attach'}>
                {f.attached?'✓':'+'}
              </button>
            </div>
          ))}
        </div>

        {/* Ingest URL */}
        <div style={ns.sec}>
          <div style={ns.sLbl}>Ingest URL</div>
          <div style={ns.urlRow}>
            <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://..." style={ns.urlIn} />
            <button onClick={handleFetch} style={ns.fetchB} disabled={fetching}>{fetching?'...':'FETCH'}</button>
          </div>
        </div>
        <div style={{ padding:'6px 10px' }}>
          <button style={ns.upB}>UPLOAD</button>
        </div>

        <Handle type="source" position={Position.Right} style={{ ...S.handle, right:-5 }} />
      </div>
    );
  }

  Object.assign(window, { FilesNode });
})();
