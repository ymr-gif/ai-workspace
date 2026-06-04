/* NIM // CANVAS — Stage 5B: Live data loader
 *
 * Place in frontend/public/canvas/ and load in index.html AFTER data.js,
 * BEFORE BootScreen.jsx (before the Babel scripts).
 *
 * Responsibilities:
 *   • Auth gate: redirect to / if no nim_token
 *   • Fetch all real API data in parallel
 *   • Patch window.NIM_CANVAS_DATA.INITIAL_NODES before React mounts
 *   • Expose window.NIM_CANVAS_TOKEN for canvas-sse.js
 */
(function nimCanvasLive() {
  /* ── 1. Auth gate ────────────────────────────────────── */
  const token = localStorage.getItem('nim_token');
  if (!token) {
    // No token — send to main app login
    window.location.replace('/');
    return;
  }
  window.NIM_CANVAS_TOKEN = token;
  const hdr = { 'Authorization': 'Bearer ' + token };

  /* ── 2. Fetch helpers ────────────────────────────────── */
  function apiGet(path) {
    return fetch(path, { headers: hdr })
      .then(r => { if (!r.ok) throw new Error(path + ':' + r.status); return r.json(); })
      .catch(() => null);
  }

  /* ── 3. Shape normalizers ────────────────────────────── */
  function normMemory(raw) {
    if (!raw) return null;
    // raw: { content, project_summary } — the existing API returns flat text.
    // Parse sections from the content string using the existing chatUtils.parseMemory
    // or derive a basic structure.
    const factLines = (raw.content || '').split('\n').filter(l => l.trim());
    return {
      factCount: factLines.length,
      sections: [
        { name:'USER',    color:'#27d8ff', count: factLines.filter(l=>/\[USER\]/i.test(l)).length || 0 },
        { name:'STACK',   color:'#3dff6e', count: factLines.filter(l=>/\[STACK\]/i.test(l)).length || 0 },
        { name:'PROJECT', color:'#ffb000', count: factLines.filter(l=>/\[PROJECT\]/i.test(l)).length || 0 },
        { name:'GOALS',   color:'#ff2222', count: factLines.filter(l=>/\[GOALS\]/i.test(l)).length || 0 },
      ].filter(s => s.count > 0).concat(
        // ensure at least one section shows
        factLines.length > 0 ? [{ name:'MEMORY', color:'#3dff6e', count: factLines.length }] : []
      ).slice(0, 4),
      topFact: factLines.length > 0 ? { text: factLines[0].replace(/^\[.*?\]\s*/,''), salience: 0.85, section:'MEMORY' } : null,
    };
  }

  function normFiles(raw) {
    if (!raw) return null;
    const list = Array.isArray(raw) ? raw : (raw.files || []);
    return list.map(f => ({
      id:       f.id || f.file_id || String(Math.random()),
      filename: f.filename || f.name || 'untitled',
      status:   (f.status || 'ready').toLowerCase().replace('error','failed'),
      attached: false,
    }));
  }

  function normSessions(raw) {
    if (!raw) return null;
    const list = Array.isArray(raw) ? raw : (raw.conversations || []);
    return list.slice(0, 20).map(c => ({
      id:           c.id || c.conversation_id,
      name:         (c.title || 'untitled').slice(0, 50),
      lastMsg:      c.last_message   || '',
      ts: c.updated_at
        ? new Date(c.updated_at).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
        : '',
    }));
  }

  function normUsage(raw) {
    if (!raw) return null;
    return {
      total_tokens: raw.total_tokens || 0,
      total_cost:   raw.total_cost   || 0,
      requests:     raw.total_requests || raw.requests || 0,
      by_model:     (raw.by_model || []).map(m => ({
        model:  m.model || m.model_key || 'unknown',
        tokens: m.tokens || m.total_tokens || 0,
        cost:   m.cost   || m.total_cost   || 0,
      })),
      window: raw.window || 'rolling 30d',
    };
  }

  function normLogs(raw) {
    if (!raw) return null;
    const list = Array.isArray(raw) ? raw : (raw.logs || raw.tool_calls || []);
    return list.slice(0, 50).map(l => ({
      id:     l.id || String(Math.random()),
      name:   l.tool_name || l.name || 'tool',
      args:   typeof l.args === 'string' ? l.args : JSON.stringify(l.args || {}),
      result: l.result_summary || l.result || '',
      ts: l.created_at
        ? new Date(l.created_at).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit', second:'2-digit' })
        : '',
    }));
  }

  /* ── 4a. Convert Neo4j CanvasNode → React Flow node ─── */
  const _NEO_TYPE_MAP = {
    input:'inputNode', session:'sessionNode', memory:'memoryNode',
    files:'filesNode', logs:'logsNode', usage:'usageNode',
    config:'configNode',
  };
  function neoToRF(n, idx) {
    const rfId = 'ai-' + n.node_id;
    // track backend-protected (core) node ids so the close-button guard can hide ✕
    if (n.protected) (window.NIM_PROTECTED_IDS ||= new Set()).add(rfId);
    return {
      id:       rfId,
      type:     _NEO_TYPE_MAP[n.node_type] || 'placeholder',
      data: {
        label:     n.node_type.toUpperCase(),
        animState: n.status === 'active' ? 'done' : 'idle',
        icon:      'Terminal',
        ...(n.config || {}),
        protected: !!n.protected,
      },
      position: (n.config || {}).position || { x: 1100 + idx * 200, y: 100 + idx * 70 },
    };
  }
  window.NIM_NEO_TO_RF = neoToRF;

  /* ── 4b. Patch INITIAL_NODES with live data ─────────── */
  function patchNodes(D, mem, files, sessions) {
    D.INITIAL_NODES = D.INITIAL_NODES.map(n => {
      switch (n.id) {
        case 'memory':
          return mem ? { ...n, data: { ...n.data, mem } } : n;
        case 'files':
          return files ? { ...n, data: { ...n.data, files } } : n;
        case 'session':
          return sessions ? { ...n, data: { ...n.data,
            session:        sessions[0] || n.data.session,
            recentSessions: sessions.slice(1, 3),
            allSessions:    sessions,
          }} : n;
        case 'input':
          return sessions ? { ...n, data: { ...n.data, sessions } } : n;
        default:
          return n;
      }
    });

    if (sessions) D.MOCK_SESSIONS = sessions;
  }

  /* ── 5. Main async load ──────────────────────────────── */
  const startTime = Date.now();

  Promise.allSettled([
    apiGet('/api/memory'),
    apiGet('/api/files'),
    apiGet('/api/usage'),
    apiGet('/api/tool-calls?limit=50'),
    apiGet('/api/conversations'),
    apiGet('/api/canvas/graph'),
    apiGet('/api/canvas/global'),
  ]).then(([memR, filesR, usageR, logsR, convsR, canvasR, globalR]) => {

    // Wait for data.js to finish defining NIM_CANVAS_DATA
    const ready = () => {
      const D = window.NIM_CANVAS_DATA;
      if (!D) return;
      clearInterval(poll);

      const mem     = normMemory(memR.status    === 'fulfilled' ? memR.value    : null);
      const files   = normFiles(filesR.status   === 'fulfilled' ? filesR.value  : null);
      const sessions= normSessions(convsR.status=== 'fulfilled' ? convsR.value  : null);
      const usage   = normUsage(usageR.status   === 'fulfilled' ? usageR.value  : null);
      const logs    = normLogs(logsR.status     === 'fulfilled' ? logsR.value   : null);

      patchNodes(D, mem, files, sessions);
      if (usage) D.MOCK_USAGE_CANVAS = usage;
      if (logs)  D.MOCK_LOGS_CANVAS  = logs;

      /* overlay AI canvas nodes from Neo4j */
      const aiGraph = canvasR.status === 'fulfilled' ? canvasR.value : null;
      if (aiGraph && aiGraph.nodes && aiGraph.nodes.length) {
        // hide the backend global session node — the static 'session' node already
        // represents the global session (and hosts the chat drawer)
        const hidden = new Set(aiGraph.nodes
          .filter(n => n.node_type === 'session' && (n.config || {}).kind === 'global')
          .map(n => n.node_id));
        const rfNodes = aiGraph.nodes.filter(n => !hidden.has(n.node_id)).map(neoToRF);
        D.INITIAL_NODES = D.INITIAL_NODES.concat(rfNodes);
        const rfEdges = (aiGraph.wires || [])
          .filter(w => !hidden.has(w.src_id) && !hidden.has(w.dst_id))
          .map(w => ({
            id:     'ai-wire-' + w.src_id + '__' + w.dst_id,
            source: 'ai-' + w.src_id,
            target: 'ai-' + w.dst_id,
            style:  { stroke: 'rgba(61,255,110,0.6)', strokeWidth: 1.5 },
          }));
        if (rfEdges.length) D.INITIAL_EDGES = D.INITIAL_EDGES.concat(rfEdges);
      }

      /* bootstrap JARVIS global conversation ID (history loaded by Canvas.jsx useEffect) */
      const globalConv = globalR.status === 'fulfilled' ? globalR.value : null;
      if (globalConv?.conversation_id) {
        window.NIM_CANVAS_GLOBAL_CONV_ID = globalConv.conversation_id;
      }

      /* remove permanently-closed static nodes */
      try {
        const closed = new Set(JSON.parse(localStorage.getItem('nim_canvas_closed') || '[]'));
        if (closed.size) {
          D.INITIAL_NODES = D.INITIAL_NODES.filter(n => !closed.has(n.id));
          D.INITIAL_EDGES = D.INITIAL_EDGES.filter(e => !closed.has(e.source) && !closed.has(e.target));
        }
      } catch {}

      /* restore saved node positions from localStorage */
      try {
        const saved = JSON.parse(localStorage.getItem('nim_canvas_positions') || '{}');
        if (Object.keys(saved).length) {
          D.INITIAL_NODES = D.INITIAL_NODES.map(n =>
            saved[n.id] ? { ...n, position: saved[n.id] } : n
          );
        }
      } catch {}

      console.info('[NIM LIVE] data patched in', Date.now() - startTime, 'ms', {
        mem: !!mem, files: !!files, sessions: !!sessions,
        usage: !!usage, logs: !!logs,
        aiNodes: aiGraph?.nodes?.length || 0,
        globalConv: globalConv?.conversation_id || null,
      });
    };

    const poll = setInterval(ready, 20);
    ready(); // try immediately too
  });
})();
