/* NIM // CANVAS — React Flow canvas shell + animation orchestrator. */
(function () {
  const C  = window.NIM_CANVAS_C;
  const S  = window.NIM_CANVAS_S;
  const D  = window.NIM_CANVAS_DATA;
  const RF = window.ReactFlow;
  const {
    ReactFlow, Handle, Position, Background, BackgroundVariant,
    Controls, MiniMap, useNodesState, useEdgesState, addEdge,
  } = RF;

  /* ── dot colors for placeholder nodes ── */
  const NODE_DOT_COLOR = {
    Terminal:'#ff2222', MessageSquare:'#27d8ff', Brain:'#3dff6e',
    FolderOpen:'#ffb000', ScrollText:'#8f8f8f', BarChart2:'#8f8f8f',
    Layers:'#27d8ff', Settings:'#ff2222',
  };

  function PlaceholderNode({ data }) {
    const dot = NODE_DOT_COLOR[data.icon] || '#555';
    return (
      <div style={{ ...S.nodeCard, ...getAnimStyle(data.animState) }}>
        <Handle type="target" position={Position.Left}  style={{ ...S.handle, left:-5 }} />
        <div style={S.nodeHeader}>
          <span style={{ width:8, height:8, background:dot, flexShrink:0, boxShadow:`0 0 5px ${dot}` }} />
          <span style={S.nodeLabel}>{data.label}</span>
        </div>
        <div style={S.nodeBody}>— stage 4 —</div>
        <Handle type="source" position={Position.Right} style={{ ...S.handle, right:-5 }} />
      </div>
    );
  }

  /* glow overlay per animation state */
  function getAnimStyle(state) {
    if (state === 'activating') return { boxShadow:'0 0 0 1px rgba(255,34,34,0.8), 0 0 14px rgba(255,34,34,0.25)' };
    if (state === 'processing') return { boxShadow:'0 0 0 1px rgba(139,92,246,0.8), 0 0 14px rgba(139,92,246,0.25)' };
    if (state === 'done')       return { boxShadow:'0 0 0 1px rgba(61,255,110,0.8),  0 0 14px rgba(61,255,110,0.25)' };
    if (state === 'error')      return { boxShadow:'0 0 0 2px rgba(255,34,34,1),      0 0 22px rgba(255,34,34,0.4)' };
    return {};
  }
  window.getAnimStyle = getAnimStyle;

  /* ── Compatibility matrix ── */
  const COMPAT = {
    'inputNode|sessionNode':      { ok:true,  label:'message routing' },
    'configNode|sessionNode':     { ok:true,  label:'model params'     },
    'workspaceNode|sessionNode':  { ok:true,  label:'scoped context'   },
    'sessionNode|memoryNode':     { ok:true,  label:'read/write'       },
    'sessionNode|filesNode':      { ok:true,  label:'file context'     },
    'sessionNode|usageNode':      { ok:true,  label:'usage tracking'   },
    'filesNode|logsNode':         { ok:true,  label:'audit trail'      },
    'memoryNode|memEditNode':     { ok:true,  label:'memory branch'    },
    'memoryNode|memHistoryNode':  { ok:true,  label:'memory branch'    },
    'memoryNode|memGraphNode':    { ok:true,  label:'memory branch'    },
  };
  function checkCompat(a, b) {
    if (!a || !b || a === b) return null;
    return COMPAT[a+'|'+b] || COMPAT[b+'|'+a] || { ok:null, label:'custom wire' };
  }
  window.NIM_CHECK_COMPAT = checkCompat;

  /* ── Smart handle routing ── */
  const HANDLE_SRC = ['s-top', 's-right', 's-bot', 's-left'];
  const HANDLE_TGT = ['t-top', 't-right', 't-bot', 't-left'];
  const NODE_W = { inputNode:280, sessionNode:300, configNode:280, memoryNode:260, filesNode:280, workspaceNode:280, logsNode:260, usageNode:260 };
  const OCCUPANCY_PENALTY = 80;

  function getHandlePos(node, hid) {
    const w = node.width  || NODE_W[node.type] || 280;
    const h = node.height || 220;
    const x = node.position.x, y = node.position.y;
    switch (hid) {
      case 's-top':   case 't-top':   return { x: x + w/2, y };
      case 's-bot':   case 't-bot':   return { x: x + w/2, y: y + h };
      case 's-right': case 't-right': return { x: x + w,   y: y + h/2 };
      case 's-left':  case 't-left':  return { x,           y: y + h/2 };
      default:                        return { x: x + w/2,  y: y + h/2 };
    }
  }

  function pickHandles(srcId, tgtId, nodes, edges) {
    const src = nodes.find(n => n.id === srcId);
    const tgt = nodes.find(n => n.id === tgtId);
    if (!src || !tgt) return {};
    const srcOcc = {}, tgtOcc = {};
    for (const e of edges) {
      if (e.source === srcId && e.sourceHandle) srcOcc[e.sourceHandle] = (srcOcc[e.sourceHandle]||0)+1;
      if (e.target === tgtId && e.targetHandle) tgtOcc[e.targetHandle] = (tgtOcc[e.targetHandle]||0)+1;
    }
    const tgtCx = tgt.position.x + (tgt.width||NODE_W[tgt.type]||280)/2;
    const tgtCy = tgt.position.y + (tgt.height||220)/2;
    const srcCx = src.position.x + (src.width||NODE_W[src.type]||280)/2;
    const srcCy = src.position.y + (src.height||220)/2;
    let best = null, bestScore = Infinity;
    for (const sh of HANDLE_SRC) {
      const sp = getHandlePos(src, sh);
      for (const th of HANDLE_TGT) {
        const tp = getHandlePos(tgt, th);
        const score = Math.hypot(sp.x - tgtCx, sp.y - tgtCy)
                    + Math.hypot(tp.x - srcCx, tp.y - srcCy)
                    + (srcOcc[sh]||0) * OCCUPANCY_PENALTY
                    + (tgtOcc[th]||0) * OCCUPANCY_PENALTY;
        if (score < bestScore) { bestScore = score; best = { sourceHandle:sh, targetHandle:th }; }
      }
    }
    return best || {};
  }

  /* ── Neo4j → React Flow node conversion (shared with canvas-live.js) ── */
  const _NEO_TYPE_MAP = {
    input:'inputNode', session:'sessionNode', memory:'memoryNode',
    files:'filesNode', logs:'logsNode', usage:'usageNode',
    workspace:'workspaceNode', config:'configNode',
  };
  function neoToRF(n, idx) {
    return {
      id:       'ai-' + n.node_id,
      type:     _NEO_TYPE_MAP[n.node_type] || 'placeholder',
      data: {
        label:     n.node_type.toUpperCase(),
        animState: n.status === 'active' ? 'done' : 'idle',
        icon:      'Terminal',
        ...(n.config || {}),
      },
      position: (n.config || {}).position || { x: 1100 + idx * 200, y: 100 + idx * 70 },
    };
  }

  /* pre-stamp smart handles on INITIAL_EDGES using known node positions */
  const SMART_INITIAL_EDGES = D.INITIAL_EDGES.map((e, i, arr) => ({
    ...e, ...pickHandles(e.source, e.target, D.INITIAL_NODES, arr.slice(0, i)),
  }));

  /* ── d3-force physics (continuous live simulation) ── */
  /* simRef, pinnedRef, physRef hold mutable state outside React renders */

  const NODE_TYPES = {
    placeholder:    PlaceholderNode,
    inputNode:      window.InputNode,
    sessionNode:    window.SessionNode,
    configNode:     window.ConfigNode,
    memoryNode:     window.MemoryNode,
    memEditNode:    window.MemoryEditNode,
    memHistoryNode: window.MemoryHistoryNode,
    memGraphNode:   window.MemoryGraphNode,
    filesNode:      window.FilesNode,
    workspaceNode:  window.WorkspaceNode,
    logsNode:       window.LogsNode,
    usageNode:      window.UsageNode,
  };

  /* ── Edge context menu ── */
  function EdgeContextMenu({ x, y, edgeId, onClose, onRemove }) {
    React.useEffect(() => {
      const d = (e) => { if (e.key==='Escape') onClose(); };
      window.addEventListener('keydown', d);
      return () => window.removeEventListener('keydown', d);
    }, [onClose]);
    return (
      <div style={{ position:'fixed', left:x, top:y, zIndex:9999, ...S.ctxMenu }}
        onClick={e => e.stopPropagation()}>
        <div style={S.ctxHeader}>WIRE</div>
        <div style={S.ctxItem}
          onMouseEnter={e => { e.currentTarget.style.background='rgba(255,34,34,0.08)'; e.currentTarget.style.color=C.RED; }}
          onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color=C.FG3; }}
          onClick={() => { onRemove(edgeId); onClose(); }}>
          <span style={{ width:7, height:7, background:C.RED, display:'inline-block' }} />
          REMOVE WIRE
        </div>
      </div>
    );
  }

  /* ── Node right-click context menu ── */
  function ContextMenu({ x, y, onClose, onAddNode }) {
    React.useEffect(() => {
      const d = (e) => { if (e.key === 'Escape') onClose(); };
      window.addEventListener('keydown', d);
      return () => window.removeEventListener('keydown', d);
    }, [onClose]);
    return (
      <div style={{ position:'fixed', left:x, top:y, zIndex:9999, ...S.ctxMenu }}
        onClick={e => e.stopPropagation()}>
        <div style={S.ctxHeader}>Add Node</div>
        {D.CTX_NODE_TYPES.map(item => {
          const dot = NODE_DOT_COLOR[item.icon] || '#555';
          return (
            <div key={item.id} style={S.ctxItem}
              onMouseEnter={e => { e.currentTarget.style.background='rgba(255,34,34,0.08)'; e.currentTarget.style.color=C.RED; }}
              onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color=C.FG3; }}
              onClick={() => { onAddNode(item, x, y); onClose(); }}>
              <span style={{ width:7, height:7, background:dot, flexShrink:0, display:'inline-block' }} />
              {item.label}
            </div>
          );
        })}
      </div>
    );
  }

  /* ── Main canvas ── */
  function NimCanvas() {
    const [nodes, setNodes, onNodesChange] = useNodesState(D.INITIAL_NODES);
    const [edges, setEdges, onEdgesChange] = useEdgesState(SMART_INITIAL_EDGES);
    const [menu,        setMenu]        = React.useState(null);
    const [edgeMenu,    setEdgeMenu]    = React.useState(null);
    const [memExpanded, setMemExpanded] = React.useState(false);

    /* physics refs */
    const simRef    = React.useRef(null);
    const pinnedRef = React.useRef(new Set());
    const rafRef    = React.useRef(null);
    const physRef   = React.useRef({ repulsion:-1200, linkDist:220, linkStr:0.06, collide:85, decay:0.45 });
    /* live-mirror for smart drag re-routing (avoids stale closure in RAF) */
    const nodesRef   = React.useRef(D.INITIAL_NODES);
    const dragRafRef = React.useRef(null);
    /* AI wire map: edgeId → {src_id, dst_id} for backend deletion lookups */
    const aiWireMapRef = React.useRef({});

    /* probe: confirm effect fires */
    React.useEffect(() => { console.info('[NIM] NimCanvas mounted'); }, []);

    /* keep nodesRef in sync so drag re-router always has current positions */
    React.useEffect(() => { nodesRef.current = nodes; }, [nodes]);

    /* ── Mount: create d3 simulation ── */
    React.useEffect(() => {
      try {
        const d3 = window.d3;
        if (!d3) { console.warn('[NIM] d3 not found'); return; }
        const P = physRef.current;
      const sNodes = D.INITIAL_NODES.map(n => ({ id:n.id, x:n.position.x, y:n.position.y, vx:0, vy:0 }));
      const sLinks = D.INITIAL_EDGES.map(e => ({ source:e.source, target:e.target }));

      const sim = d3.forceSimulation(sNodes)
        .force('link',    d3.forceLink(sLinks).id(d=>d.id).distance(P.linkDist).strength(P.linkStr))
        .force('charge',  d3.forceManyBody().strength(P.repulsion).distanceMax(700))
        .force('collide', d3.forceCollide(P.collide).strength(0.9).iterations(3))
        .force('center',  d3.forceCenter(700, 380).strength(0.018))
        .velocityDecay(P.decay)
        .alphaDecay(0.014)
        .alphaMin(0.001);

      simRef.current = sim;

      /* RAF loop — push sim positions into React Flow when active */
      const tick = () => {
        if (sim.alpha() > sim.alphaMin() * 1.5) {
          const sn = sim.nodes();
          setNodes(nds => nds.map(nd => {
            const s = sn.find(s => s.id === nd.id);
            if (!s) return nd;
            const nx = Math.round(s.x), ny = Math.round(s.y);
            if (nd.position.x === nx && nd.position.y === ny) return nd;
            return { ...nd, position:{ x:nx, y:ny } };
          }));
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);

      /* Expose controls for CONFIG node physics panel */
      window.NIM_SIM = {
        reheat: (a=0.6) => { sim.alpha(a).restart(); },
        set: (key, val) => {
          const d3 = window.d3;
          physRef.current[key] = val;
          if (key==='repulsion') sim.force('charge', d3.forceManyBody().strength(val).distanceMax(700));
          if (key==='linkDist')  { const l=sim.force('link'); if(l) l.distance(val); }
          if (key==='linkStr')   { const l=sim.force('link'); if(l) l.strength(val); }
          if (key==='collide')   sim.force('collide', d3.forceCollide(val).strength(0.9).iterations(3));
          if (key==='decay')     sim.velocityDecay(val);
          sim.alpha(Math.max(sim.alpha(), 0.25)).restart();
        },
        getPhys: () => ({ ...physRef.current }),
        getAlpha: () => sim.alpha(),
      };

        window.NIM_SIM_READY = true;
        console.info('[NIM] simulation started, alpha=' + sim.alpha().toFixed(3));
        return () => { sim.stop(); cancelAnimationFrame(rafRef.current); };
      } catch(err) { console.error('[NIM SIM ERROR]', err); }
    }, []);

    /* ── Edge sync: rebuild link force when edges change ── */
    React.useEffect(() => {
      const sim = simRef.current;
      if (!sim || !window.d3) return;
      const P = physRef.current;
      const simNodeIds = new Set(sim.nodes().map(n => n.id));
      /* only include edges whose both endpoints are in the sim */
      const safeLinks = edges
        .filter(e => simNodeIds.has(e.source) && simNodeIds.has(e.target))
        .map(e => ({ source: e.source, target: e.target }));
      sim.force('link', window.d3.forceLink(safeLinks)
        .id(d => d.id).distance(P.linkDist).strength(P.linkStr));
      sim.alpha(Math.max(sim.alpha(), 0.3)).restart();
    }, [edges]);

    /* ── Node count sync: add/remove nodes without resetting ── */
    React.useEffect(() => {
      const sim = simRef.current;
      if (!sim) return;
      const cur = sim.nodes(), curIds = new Set(cur.map(n=>n.id));
      const newIds = new Set(nodes.map(n=>n.id));
      const toAdd = nodes.filter(n => !curIds.has(n.id));
      const kept  = cur.filter(n => newIds.has(n.id));
      if (!toAdd.length && kept.length === cur.length) return;
      toAdd.forEach(n => {
        const rel = edges.find(e=>e.source===n.id||e.target===n.id);
        const relId = rel ? (rel.source===n.id?rel.target:rel.source) : null;
        const base  = relId ? kept.find(s=>s.id===relId) : null;
        kept.push({ id:n.id, x: base?base.x+(Math.random()-.5)*130:n.position.x,
                              y: base?base.y+(Math.random()-.5)*130:n.position.y, vx:0, vy:0 });
      });
      sim.nodes(kept);
      /* rebuild link force AFTER node list update so d3 can resolve all IDs */
      const P2 = physRef.current;
      sim.force('link', window.d3.forceLink(
        edges.map(e => ({ source: e.source, target: e.target }))
      ).id(d => d.id).distance(P2.linkDist).strength(P2.linkStr));
      sim.alpha(Math.max(sim.alpha(), 0.4)).restart();
    }, [nodes.length]);

    /* update one node's animState */
    const setNodeAnim = React.useCallback((id, state) => {
      setNodes(nds => nds.map(n => n.id === id ? { ...n, data:{ ...n.data, animState:state } } : n));
    }, [setNodes]);

    /* expand / collapse memory branches */
    const onMemExpand = React.useCallback(() => {
      if (memExpanded) {
        setNodes(nds => nds
          .filter(n => !['mem-edit','mem-history','mem-graph'].includes(n.id))
          .map(n => n.id === 'memory' ? { ...n, data:{ ...n.data, isExpanded:false } } : n)
        );
        setEdges(eds => eds.filter(e => !['e-mem-edit','e-mem-hist','e-mem-graph'].includes(e.id)));
        setMemExpanded(false);
      } else {
        const mem = nodes.find(n => n.id === 'memory');
        const mx  = mem?.position.x || 780;
        const my  = mem?.position.y || 100;
        const branchNodes = [
          { id:'mem-edit',    type:'memEditNode',    data:{}, position:{ x:mx+300, y:my-80  } },
          { id:'mem-history', type:'memHistoryNode', data:{}, position:{ x:mx+300, y:my+90  } },
          { id:'mem-graph',   type:'memGraphNode',   data:{}, position:{ x:mx+300, y:my+280 } },
        ];
        setNodes(nds => [
          ...nds.map(n => n.id === 'memory' ? { ...n, data:{ ...n.data, isExpanded:true } } : n),
          ...branchNodes,
        ]);
        const allNodes = [...nodes, ...branchNodes];
        setEdges(eds => {
          const pairs = [
            ['memory','mem-edit',   'e-mem-edit'],
            ['memory','mem-history','e-mem-hist'],
            ['memory','mem-graph',  'e-mem-graph'],
          ];
          let next = eds;
          for (const [src, tgt, id] of pairs) {
            const { sourceHandle, targetHandle } = pickHandles(src, tgt, allNodes, next);
            next = [...next, { id, source:src, target:tgt, sourceHandle, targetHandle, animated:true, style:{ stroke:'rgba(139,92,246,0.7)', strokeWidth:2 } }];
          }
          return next;
        });
        setMemExpanded(true);
      }
    }, [memExpanded, nodes, setNodes, setEdges]);

    /* remove individual branch node */
    const onRemoveBranch = React.useCallback((nodeId) => {
      const edgeMap = { 'mem-edit':'e-mem-edit', 'mem-history':'e-mem-hist', 'mem-graph':'e-mem-graph' };
      setNodes(nds => {
        const next = nds.filter(n => n.id !== nodeId);
        const anyLeft = next.some(n => ['mem-edit','mem-history','mem-graph'].includes(n.id));
        if (!anyLeft) {
          setMemExpanded(false);
          return next.map(n => n.id === 'memory' ? { ...n, data:{ ...n.data, isExpanded:false } } : n);
        }
        return next;
      });
      if (edgeMap[nodeId]) setEdges(eds => eds.filter(e => e.id !== edgeMap[nodeId]));
    }, [setNodes, setEdges]);

    /* demo send — activation sequence + streaming */
    const onDemoSend = React.useCallback(() => {
      const txt = D.MOCK_STREAM;
      /* reset */
      setNodes(nds => nds.map(n => n.id === 'session' ? { ...n, data:{ ...n.data, streamText:'', isStreaming:false } } : n));

      setNodeAnim('input', 'activating');
      setTimeout(() => setNodeAnim('config', 'activating'), 200);
      setTimeout(() => setNodeAnim('memory', 'processing'), 400);
      setTimeout(() => {
        setNodeAnim('session', 'processing');
        let i = 0;
        const timer = setInterval(() => {
          i = Math.min(i + 5, txt.length);
          setNodes(nds => nds.map(n => n.id === 'session'
            ? { ...n, data:{ ...n.data, streamText:txt.slice(0,i), isStreaming:i < txt.length } }
            : n
          ));
          if (i >= txt.length) {
            clearInterval(timer);
            setTimeout(() => {
              ['input','config','memory','session'].forEach((id, k) =>
                setTimeout(() => setNodeAnim(id, 'done'), k * 80)
              );
              setTimeout(() => ['input','config','memory','session'].forEach(id => setNodeAnim(id, 'idle')), 1200);
              /* trigger insight card after animation settles */
              setTimeout(() => window.dispatchEvent(new CustomEvent('nim-insight', {
                detail: { text:"You've compared routing strategies often — want me to draft a decision table?" }
              })), 2000);
            }, 300);
          }
        }, 28);
      }, 600);
    }, [setNodeAnim, setNodes]);

    /* wire semantic feedback — watch edges, propagate to node data */
    React.useEffect(() => {
      const hasFile = edges.some(e => e.source === 'files'     && e.target === 'session');
      const hasWs   = edges.some(e => e.source === 'workspace' && e.target === 'session');
      setNodes(nds => nds.map(n => {
        if (n.id === 'session')   return { ...n, data: { ...n.data, fileAttached: hasFile, wsWired: hasWs } };
        if (n.id === 'files')     return { ...n, data: { ...n.data, wireAttached: hasFile } };
        if (n.id === 'workspace') return { ...n, data: { ...n.data,
          scopedSessions: hasWs ? [{ id:'session', name:'routing-strategy' }] : [] } };
        return n;
      }));
    }, [edges]);

    /* ── internal helpers for canvas-sse.js (Stage 5) ── */
    const streamSession = React.useCallback((text, done) => {
      setNodes(nds => nds.map(n => n.id === 'session'
        ? { ...n, data: { ...n.data, streamText: text, isStreaming: !done } }
        : n
      ));
    }, [setNodes]);

    /* merge AI canvas graph delta into React Flow state */
    const patchCanvas = React.useCallback(({ nodes: neoNodes, wires }) => {
      const rfNodes = (neoNodes || []).map(neoToRF);
      setNodes(nds => [...nds.filter(n => !n.id.startsWith('ai-')), ...rfNodes]);
      const rfEdges = (wires || []).map(w => {
        const id = 'ai-wire-' + w.src_id + '__' + w.dst_id;
        aiWireMapRef.current[id] = { src_id: w.src_id, dst_id: w.dst_id };
        return { id, source:'ai-'+w.src_id, target:'ai-'+w.dst_id,
          style:{ stroke:'rgba(61,255,110,0.6)', strokeWidth:1.5 } };
      });
      setEdges(eds => [...eds.filter(e => !e.id.startsWith('ai-wire-')), ...rfEdges]);
    }, [setNodes, setEdges]);

    /* wrap onEdgesChange to delete AI wires from backend on removal */
    const handleEdgesChange = React.useCallback((changes) => {
      onEdgesChange(changes);
      const tok = localStorage.getItem('nim_token');
      for (const ch of changes) {
        if (ch.type !== 'remove') continue;
        const wire = aiWireMapRef.current[ch.id];
        if (!wire) continue;
        delete aiWireMapRef.current[ch.id];
        fetch('/api/canvas/wire', {
          method: 'DELETE',
          headers: { 'Content-Type':'application/json', 'Authorization':'Bearer '+tok },
          body: JSON.stringify(wire),
        }).catch(() => {});
      }
    }, [onEdgesChange]);

    /* expose callbacks via window bridge */
    React.useEffect(() => {
      window.NIM_CANVAS_CB = {
        onMemExpand, onRemoveBranch, onDemoSend, onAutoArrange,
        _setNodeAnim:   setNodeAnim,
        _streamSession: streamSession,
        _patch:         patchCanvas,
      };
    }, [onMemExpand, onRemoveBranch, onDemoSend, onAutoArrange, setNodeAnim, streamSession, patchCanvas]);

    /* ARRANGE — reheat simulation (Obsidian-style: let physics settle organically) */
    const onAutoArrange = React.useCallback(() => {
      window.NIM_SIM?.reheat(1);
    }, []);

    /* Drag: fix node in sim while dragging, release on drop */
    const onNodeDragStart = React.useCallback((_, node) => {
      const sim = simRef.current; if (!sim) return;
      const s = sim.nodes().find(n=>n.id===node.id);
      if (s) { s.fx=s.x; s.fy=s.y; }
      sim.alphaTarget(0.3).restart();
    }, []);
    const onNodeDrag = React.useCallback((_, node) => {
      /* d3 sim: keep dragged node fixed at cursor */
      const sim = simRef.current;
      if (sim) {
        const s = sim.nodes().find(n => n.id === node.id);
        if (s) { s.fx = node.position.x; s.fy = node.position.y; }
      }
      /* RAF-throttled edge re-routing — runs at most once per screen frame */
      if (dragRafRef.current) cancelAnimationFrame(dragRafRef.current);
      dragRafRef.current = requestAnimationFrame(() => {
        dragRafRef.current = null;
        /* patch the moving node to its current drag position */
        const patchedNodes = nodesRef.current.map(n =>
          n.id === node.id ? { ...n, position: node.position } : n
        );
        setEdges(eds => {
          let changed = false;
          const next = eds.map(e => {
            if (e.source !== node.id && e.target !== node.id) return e;
            /* exclude this edge from its own occupancy score */
            const others = eds.filter(x => x.id !== e.id);
            const smart = pickHandles(e.source, e.target, patchedNodes, others);
            if (smart.sourceHandle === e.sourceHandle && smart.targetHandle === e.targetHandle) return e;
            changed = true;
            return { ...e, ...smart };
          });
          return changed ? next : eds;
        });
      });
    }, [setEdges]);
    const onNodeDragStop = React.useCallback((_, node) => {
      const sim = simRef.current; if (!sim) return;
      const s = sim.nodes().find(n=>n.id===node.id);
      if (s && !pinnedRef.current.has(node.id)) { s.fx=null; s.fy=null; }
      sim.alphaTarget(0);
      /* persist AI node position to Neo4j */
      if (node.id.startsWith('ai-')) {
        const nid = node.id.slice(3);
        const tok = localStorage.getItem('nim_token');
        fetch('/api/canvas/nodes/' + nid, {
          method: 'PATCH',
          headers: { 'Content-Type':'application/json', 'Authorization':'Bearer '+tok },
          body: JSON.stringify({ config: { position: node.position } }),
        }).catch(() => {});
      }
      /* save all node positions to localStorage (static nodes) */
      try {
        const pos = {};
        nodesRef.current.forEach(n => { pos[n.id] = n.position; });
        localStorage.setItem('nim_canvas_positions', JSON.stringify(pos));
      } catch {}
    }, []);

    /* Node right-click → pin/unpin */
    const onNodeCtx = React.useCallback((e, node) => {
      e.preventDefault();
      const sim = simRef.current; if (!sim) return;
      const s = sim.nodes().find(n=>n.id===node.id);
      if (!s) return;
      const wasPinned = pinnedRef.current.has(node.id);
      if (wasPinned) { pinnedRef.current.delete(node.id); s.fx=null; s.fy=null; sim.alpha(0.1).restart(); }
      else           { pinnedRef.current.add(node.id);    s.fx=s.x;  s.fy=s.y; }
      setNodes(nds => nds.map(n => n.id===node.id ? { ...n, data:{...n.data, pinned:!wasPinned} } : n));
    }, [setNodes]);

    const onConnect       = React.useCallback((p) => {
      const smart = (!p.sourceHandle || !p.targetHandle)
        ? pickHandles(p.source, p.target, nodes, edges) : {};
      setEdges(eds => addEdge({ ...p, ...smart, style:{ stroke:C.FG4, strokeWidth:1.5 } }, eds));
      /* persist to Neo4j when either endpoint is an AI canvas node */
      const isAI = id => id && id.startsWith('ai-');
      if (isAI(p.source) || isAI(p.target)) {
        const srcId  = p.source.replace('ai-', '');
        const dstId  = p.target.replace('ai-', '');
        const edgeId = 'ai-wire-' + srcId + '__' + dstId;
        const wire   = { src_id: srcId, dst_id: dstId,
          src_port: smart.sourceHandle || 'out',
          dst_port: smart.targetHandle || 'in',
          relation: 'connected' };
        aiWireMapRef.current[edgeId] = wire;
        const tok = localStorage.getItem('nim_token');
        fetch('/api/canvas/wire', {
          method: 'POST',
          headers: { 'Content-Type':'application/json', 'Authorization':'Bearer '+tok },
          body: JSON.stringify(wire),
        }).catch(() => {});
      }
    }, [setEdges, nodes, edges]);
    const onEdgeCtx       = React.useCallback((e, edge) => { e.preventDefault(); setEdgeMenu({ x:e.clientX, y:e.clientY, edgeId:edge.id }); }, []);
    const onConnectStart  = React.useCallback((_, { nodeId }) => {
      const nd = nodes.find(n => n.id === nodeId);
      window.NIM_CONNECTING_TYPE = nd?.type || null;
      window.dispatchEvent(new CustomEvent('nim-connect-start', { detail:{ nodeType: nd?.type } }));
    }, [nodes]);
    const onConnectEnd    = React.useCallback(() => {
      window.NIM_CONNECTING_TYPE = null;
      window.dispatchEvent(new CustomEvent('nim-connect-end'));
    }, []);
    const onPaneCtx       = React.useCallback((e) => { e.preventDefault(); setEdgeMenu(null); setMenu({ x:e.clientX, y:e.clientY }); }, []);
    const onPaneClick     = React.useCallback(() => { setMenu(null); setEdgeMenu(null); }, []);
    const onAddNode     = React.useCallback((item, mx, my) => {
      setNodes(ns => [...ns, {
        id: item.id+'-'+Date.now(), type:'placeholder',
        data:{ label:item.label.replace(' Node','').toUpperCase(), icon:item.icon },
        position:{ x:mx-100, y:my-40 },
      }]);
    }, [setNodes]);

    return (
      <div style={{ position:'absolute', inset:0 }} onClick={() => setMenu(null)}>
        <div style={{ position:'fixed', inset:0, zIndex:0, pointerEvents:'none',
          background:'#000 url("../../assets/cpu-schematic.svg") center/cover no-repeat', opacity:0.7 }} />

        <div style={{ position:'absolute', inset:0, zIndex:1 }}>
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={handleEdgesChange}
            onConnect={onConnect} onEdgeContextMenu={onEdgeCtx}
            onConnectStart={onConnectStart} onConnectEnd={onConnectEnd}
            onNodeDragStart={onNodeDragStart} onNodeDrag={onNodeDrag} onNodeDragStop={onNodeDragStop}
            onNodeContextMenu={onNodeCtx}
            onPaneContextMenu={onPaneCtx} onPaneClick={onPaneClick}
            nodeTypes={NODE_TYPES}
            defaultEdgeOptions={{ style:{ stroke:'#555555', strokeWidth:1.5 } }}
            connectionLineStyle={{ stroke:'#808080', strokeWidth:1, strokeDasharray:'4 4' }}
            deleteKeyCode={['Backspace','Delete']}
            fitView fitViewOptions={{ padding:0.28 }}
            style={{ background:'transparent' }}
            proOptions={{ hideAttribution:true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1.2} color="#1e1e1e" style={{ background:'transparent' }} />
            <MiniMap position="bottom-left"
              style={{ background:'#0a0a0a', border:'1px solid #4a4a4a', borderRadius:0 }}
              maskColor="rgba(0,0,0,0.7)" nodeColor="#333" />
            <Controls position="bottom-left"
              style={{ display:'flex', flexDirection:'row', gap:2,
                background:'none', border:'none', boxShadow:'none', bottom:120 }}
              showInteractive={false} />
          </ReactFlow>
        </div>

        {menu     && <ContextMenu    x={menu.x}     y={menu.y}     onClose={() => setMenu(null)}    onAddNode={onAddNode} />}
        {edgeMenu && <EdgeContextMenu x={edgeMenu.x} y={edgeMenu.y} edgeId={edgeMenu.edgeId}
          onClose={() => setEdgeMenu(null)}
          onRemove={id => setEdges(eds => eds.filter(e => e.id !== id))} />}
      </div>
    );
  }

  Object.assign(window, { NimCanvas, PlaceholderNode });
})();
