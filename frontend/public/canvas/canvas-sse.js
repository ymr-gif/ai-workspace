/* NIM // CANVAS — Stage 5C/D: Real SSE stream integration
 *
 * Place in frontend/public/canvas/ and load in index.html AFTER canvas-live.js,
 * BEFORE BootScreen.jsx (before the Babel scripts).
 *
 * Responsibilities:
 *   • Intercept NIM_CANVAS_CB assignment via Object.defineProperty
 *   • Replace onDemoSend with real POST /api/chat/stream SSE handler
 *   • Map SSE events → canvas node animations + Session output streaming
 *   • Wire file_ids (File→Session wire) and workspace_id (Workspace→Session wire)
 */
(function nimCanvasSSE() {

  /* ── Shared node animation helpers ──────────────────── */
  function setAnim(id, state) {
    window.NIM_CANVAS_CB?._setNodeAnim?.(id, state);
  }
  function streamToSession(text, done) {
    window.NIM_CANVAS_CB?._streamSession?.(text, done);
  }
  function triggerInsight(text) {
    window.dispatchEvent(new CustomEvent('nim-insight', { detail: { text } }));
  }
  function pulseNode(id) {
    setAnim(id, 'processing');
    setTimeout(() => setAnim(id, 'done'), 800);
    setTimeout(() => setAnim(id, 'idle'), 1800);
  }

  /* ── Build ChatRequest body from canvas state ────────── */
  function buildBody() {
    const text     = window.NIM_CANVAS_LAST_INPUT      || '';
    const convId   = window.NIM_CANVAS_LAST_SESSION_ID
                   || window.NIM_CANVAS_GLOBAL_CONV_ID
                   || null;
    const wsId     = window.NIM_CANVAS_LAST_WS_ID      || null;
    const model    = window.NIM_CANVAS_LAST_MODEL       || null;   // null → auto
    const fileIds  = window.NIM_CANVAS_LAST_FILE_IDS    || [];     // 5D: file wire
    const params   = window.NIM_CANVAS_LAST_PARAMS      || {};

    const body = { message: text };
    if (convId)            body.conversation_id = convId;
    if (wsId)              body.workspace_id    = wsId;
    if (model && model !== 'auto') body.model_override = model;
    if (fileIds.length)    body.file_ids        = fileIds;         // new field (5D)
    if (params.tempOn)     body.temperature     = params.temp;
    if (params.tokOn)      body.max_tokens      = params.tok;
    if (params.toppOn)     body.top_p           = params.topp;
    return body;
  }

  /* ── Real SSE send ───────────────────────────────────── */
  async function realSend() {
    const token = window.NIM_CANVAS_TOKEN || localStorage.getItem('nim_token');
    if (!token) { window.location.replace('/'); return; }

    const text = window.NIM_CANVAS_LAST_INPUT?.trim();
    if (!text) return;

    /* Activation sequence: Input → Config → Memory → Session */
    setAnim('input',   'activating');
    setTimeout(() => setAnim('config',  'activating'), 200);
    setTimeout(() => setAnim('memory',  'processing'), 400);
    setTimeout(() => setAnim('session', 'processing'), 600);

    let fullText = '';
    let convId   = null;

    try {
      const res = await fetch('/api/chat/stream', {
        method:  'POST',
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
        body:    JSON.stringify(buildBody()),
      });

      if (res.status === 401) { window.location.replace('/'); return; }
      if (!res.ok) {
        setAnim('session', 'error');
        setTimeout(() => setAnim('session', 'idle'), 2000);
        return;
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let event;
          try { event = JSON.parse(raw); } catch { continue; }

          switch (event.type) {

            case 'token':
              fullText += event.content || '';
              streamToSession(fullText, false);
              break;

            case 'preamble_discard':
              /* streamed text was pre-tool preamble — drop it, real answer follows */
              fullText = '';
              streamToSession('', false);
              break;

            case 'done':
              streamToSession(fullText, true);
              convId = event.conversation_id || convId;
              if (event.last_session) {
                /* update session node title */
                window.NIM_CANVAS_CB?._updateSessionMeta?.({
                  lastSession: event.last_session,
                  totalTokens: event.total_tokens,
                  costUsd:     event.cost_usd,
                  queryType:   event.query_type,
                  srcCount:    event.src_count,
                  model:       event.model,
                });
              }
              if (convId) window.NIM_CANVAS_LAST_SESSION_ID = convId;
              /* append exchange to session history */
              if (window.NIM_CANVAS_LAST_INPUT && fullText) {
                window.NIM_CANVAS_CB?._appendMessages?.([
                  { role: 'user',      content: window.NIM_CANVAS_LAST_INPUT },
                  { role: 'assistant', content: fullText,
                    model: event.model || '', total_tokens: event.total_tokens || 0 },
                ]);
              }
              /* done flash on all nodes */
              ['input','config','memory','session'].forEach((id, k) =>
                setTimeout(() => setAnim(id, 'done'), k * 80)
              );
              setTimeout(() => ['input','config','memory','session'].forEach(id => setAnim(id,'idle')), 1200);
              /* trigger insight card 2s after stream */
              setTimeout(() => triggerInsight(
                "You've sent a new message — want me to summarize the key points?"
              ), 2000);
              break;

            case 'tool_call':
              pulseNode('logs');
              break;

            case 'tool_result':
              /* logs node already pulsed */
              break;

            case 'confirm_write_memory':
              pulseNode('memory');
              break;

            case 'proactive':
              triggerInsight(event.content || '');
              break;

            case 'ask_user':
              /* Pass through to session output as-is (already rendered as text) */
              break;

            case 'canvas_update':
              /* AI modified canvas via tool — re-fetch graph and patch React Flow state */
              (function() {
                const tok = window.NIM_CANVAS_TOKEN || localStorage.getItem('nim_token');
                fetch('/api/canvas/graph', { headers: { 'Authorization': 'Bearer ' + tok } })
                  .then(r => r.ok ? r.json() : null)
                  .then(data => { if (data) window.NIM_CANVAS_CB?._patch?.(data); })
                  .catch(() => {});
              })();
              pulseNode('logs');
              break;

            case 'error':
              streamToSession('[ERROR] ' + (event.message || 'Unknown error'), true);
              setAnim('session', 'error');
              setTimeout(() => setAnim('session', 'idle'), 2500);
              break;
          }
        }
      }
    } catch (err) {
      streamToSession('[NETWORK ERROR] ' + err.message, true);
      setAnim('session', 'error');
      setTimeout(() => setAnim('session', 'idle'), 2500);
    }
  }

  /* ── Intercept NIM_CANVAS_CB assignment ─────────────── *
   * Canvas.jsx does: window.NIM_CANVAS_CB = { onMemExpand, onRemoveBranch, onDemoSend }
   * Our setter injects realSend as onDemoSend and stores internal helpers.
   */
  let _cb = null;
  Object.defineProperty(window, 'NIM_CANVAS_CB', {
    get() { return _cb; },
    set(val) {
      _cb = {
        ...val,
        /* replace demo send with real SSE send */
        onDemoSend: realSend,
        /* expose internal helpers so realSend can call back into React state */
        _setNodeAnim:       val._setNodeAnim       || null,
        _streamSession:     val._streamSession     || null,
        _updateSessionMeta: val._updateSessionMeta || null,
        _patch:             val._patch             || null,
        _appendMessages:    val._appendMessages    || null,
      };
    },
    configurable: true,
  });

  console.info('[NIM SSE] interceptor installed — onDemoSend → realSend');

})();
