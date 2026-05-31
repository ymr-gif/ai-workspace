/* NIM // SYSTEM TERMINAL — orchestrator. Wires the demo together. */
const { Sidebar, ChatHeader, MessageFeed, ModelToolbar, MemoryPanel, FilesPanel, BootScreen, MainMenu } = window;

const NIM_REPLIES = [
  "Good question. The gateway scores the prompt, then routes to the cheapest model that clears the confidence bar — escalating only when the score is low.\n\n- **factual** lookups → `LLaMA 3.1 8B`\n- **code** generation → `DeepSeek V4`\n- **multi-step reasoning** → `LLaMA 3.3 70B`\n\nEvery answer reports its `query_type` and source count so you can tune routing later.",
  "Short version: chunk → embed → store per workspace, then retrieve top-k at query time and attach as context. The `provenance[]` field is what powers the `· N src` badge on each reply.",
  "I'd cap it at **$25/mo** by default, soft-warn at 80%, hard-stop at 100% with an admin override. Track spend per `query_type` so you can see where routing is most expensive.",
];

function App() {
  const [phase, setPhase] = React.useState('boot');   // 'boot' | 'menu' | 'app'
  const [conversations, setConversations] = React.useState(window.NIM_CONVERSATIONS);
  const [activeConvId, setActiveConvId] = React.useState('c1');
  const [messages, setMessages] = React.useState(window.NIM_MESSAGES['c1']);
  const [wsId, setWsId] = React.useState(null);
  const [search, setSearch] = React.useState('');
  const [input, setInput] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [selectedModel, setSelectedModel] = React.useState('auto');
  const [compareMode, setCompareMode] = React.useState(false);
  const [paramsOpen, setParamsOpen] = React.useState(false);
  const [params, setParams] = React.useState({ tempOn: true, temp: 0.8, tokOn: false, tok: 1024, toppOn: false, topp: 0.9 });
  const [ctxOn, setCtxOn] = React.useState(true);
  const [proactive, setProactive] = React.useState('You\u2019ve compared routing strategies a few times \u2014 want me to draft a decision table?');
  const [memOpen, setMemOpen] = React.useState(false);
  const [filesOpen, setFilesOpen] = React.useState(false);
  const [usageOpen, setUsageOpen] = React.useState(false);
  const [logOpen, setLogOpen] = React.useState(false);
  const [insightsOpen, setInsightsOpen] = React.useState(false);
  const [attachedIds, setAttachedIds] = React.useState(new Set(['f1']));
  const bottomRef = React.useRef(null);
  const replyIdx = React.useRef(0);

  React.useEffect(() => { bottomRef.current?.scrollIntoView?.({ block: 'end' }); }, [messages]);

  const activeConv = conversations.find(c => c.id === activeConvId);
  const lockedLabel = activeConv?.locked_model ? window.NIM_MODEL_LABELS.reasoning : null;
  const files = window.NIM_FILES;
  const attachedFiles = files.filter(f => attachedIds.has(f.id));

  const closeAllPanels = () => { setMemOpen(false); setFilesOpen(false); setUsageOpen(false); setLogOpen(false); setInsightsOpen(false); };
  const anyOpen = memOpen || filesOpen || usageOpen || logOpen || insightsOpen;

  function selectConv(id) {
    setActiveConvId(id);
    setMessages(window.NIM_MESSAGES[id] || []);
    setProactive(null);
  }
  function newChat() {
    const id = 'c' + Date.now();
    const conv = { id, title: 'New conversation', updated_at: 'now', workspace_id: wsId };
    window.NIM_MESSAGES[id] = [];
    setConversations([conv, ...conversations]);
    selectConv(id);
  }
  function toggleAttach(id) {
    setAttachedIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const MENU_ITEMS = [
    { id: 'new',        label: 'New Session' },
    { id: 'resume',     label: 'Resume', note: '· ' + window.NIM_CONVERSATIONS[0].title.slice(0, 22) + '…' },
    { id: 'memory',     label: 'Memory Core' },
    { id: 'diagnostics',label: 'Diagnostics' },
    { id: 'config',     label: 'Config', note: '· offline', disabled: true },
    { id: 'disconnect', label: 'Disconnect' },
  ];
  function handleMenu(id) {
    if (id === 'new')        { newChat(); setPhase('app'); }
    else if (id === 'resume') { selectConv('c1'); setPhase('app'); }
    else if (id === 'memory') { selectConv('c1'); setPhase('app'); closeAllPanels(); setMemOpen(true); }
    else if (id === 'diagnostics') { selectConv('c1'); setPhase('app'); closeAllPanels(); setUsageOpen(true); }
    else if (id === 'disconnect') { closeAllPanels(); setPhase('boot'); }
  }

  function send(e) {
    e.preventDefault();
    if (!input.trim() || loading) return;
    const userMsg = { id: 'u' + Date.now(), role: 'user', text: input };
    const text = input;
    setInput(''); setProactive(null);

    if (compareMode) {
      const id = 'cmp' + Date.now();
      const responses = {}; window.NIM_COMPARE.forEach(m => responses[m] = { text: '', streaming: true });
      setMessages(prev => [...prev, userMsg, { id, role: 'compare', responses }]);
      const targets = { llama: 'Fast take: route by prompt length.', coder: 'Code-first: classify generative vs explanatory, weight files referenced.', reasoning: 'Score complexity + risk; escalate low-confidence routes to the 70B.' };
      window.NIM_COMPARE.forEach((m, i) => {
        setTimeout(() => setMessages(prev => prev.map(msg => msg.id === id
          ? { ...msg, responses: { ...msg.responses, [m]: { text: targets[m], streaming: false } } } : msg)), 500 + i * 450);
      });
      return;
    }

    setLoading(true);
    const aiId = 'a' + Date.now();
    setMessages(prev => [...prev, userMsg, { id: aiId, role: 'ai', text: '', streaming: true }]);
    const full = NIM_REPLIES[replyIdx.current % NIM_REPLIES.length]; replyIdx.current++;
    let i = 0;
    const model = selectedModel === 'auto' ? 'reasoning' : selectedModel;
    const timer = setInterval(() => {
      i += Math.max(2, Math.round(full.length / 60));
      const chunk = full.slice(0, i);
      setMessages(prev => prev.map(m => m.id === aiId ? { ...m, text: chunk } : m));
      if (i >= full.length) {
        clearInterval(timer);
        const tok = 400 + Math.floor(Math.random() * 900);
        setMessages(prev => prev.map(m => m.id === aiId ? {
          ...m, text: full, streaming: false, model,
          totalTokens: tok, costUsd: tok * 0.00000033,
          queryType: ['factual', 'relational', 'broad'][replyIdx.current % 3],
          srcCount: attachedFiles.length > 0 ? 3 : 1,
        } : m));
        setLoading(false);
      }
    }, 45);
  }

  if (phase === 'boot') return <BootScreen onWake={() => setPhase('menu')} />;
  if (phase === 'menu') return <MainMenu items={MENU_ITEMS} onSelect={handleMenu} />;

  return (
    <div style={window.NIM_S.root}>
      <Sidebar conversations={conversations} activeConvId={activeConvId} selectConv={selectConv}
        wsList={window.NIM_WORKSPACES} wsId={wsId} setWsId={setWsId} search={search} setSearch={setSearch} newChat={newChat} />

      <div style={window.NIM_S.chat}>
        <ChatHeader activeConvId={activeConvId} ctxOn={ctxOn} toggleCtx={() => setCtxOn(o => !o)}
          openMemory={() => { closeAllPanels(); setMemOpen(true); }}
          openFiles={() => { closeAllPanels(); setFilesOpen(true); }}
          attachedCount={attachedFiles.length}
          usageOpen={usageOpen} toggleUsage={() => { const v = !usageOpen; closeAllPanels(); setUsageOpen(v); }}
          logOpen={logOpen} toggleLog={() => { const v = !logOpen; closeAllPanels(); setLogOpen(v); }}
          insightsOpen={insightsOpen} toggleInsights={() => { const v = !insightsOpen; closeAllPanels(); setInsightsOpen(v); }}
          lockedLabel={lockedLabel} onLogout={() => { closeAllPanels(); setPhase('menu'); }} />

        <MessageFeed messages={messages} activeConvId={activeConvId} bottomRef={bottomRef}
          proactive={proactive} dismissProactive={() => setProactive(null)} lastSession={null} />

        <ModelToolbar selectedModel={selectedModel} setSelectedModel={setSelectedModel}
          compareMode={compareMode} setCompareMode={setCompareMode}
          paramsOpen={paramsOpen} setParamsOpen={setParamsOpen} params={params} setParams={setParams}
          attachedFiles={attachedFiles} detachFile={toggleAttach}
          input={input} setInput={setInput} loading={loading} send={send} />
      </div>

      {anyOpen && <div style={window.NIM_S.overlay} onClick={closeAllPanels} />}
      <MemoryPanel open={memOpen} onClose={() => setMemOpen(false)} />
      <FilesPanel open={filesOpen} onClose={() => setFilesOpen(false)} files={files} attachedIds={attachedIds} toggleAttach={toggleAttach} />
      <SidePanelStub open={usageOpen} title="$ Usage" onClose={() => setUsageOpen(false)} kind="usage" />
      <SidePanelStub open={logOpen} title="🔧 Tool Log" onClose={() => setLogOpen(false)} kind="log" />
      <SidePanelStub open={insightsOpen} title="💡 Insights" onClose={() => setInsightsOpen(false)} kind="insights" />
    </div>
  );
}

/* Compact stub panels for Usage / Log / Insights (same chrome, seeded rows) */
function SidePanelStub({ open, title, onClose, kind }) {
  const S = window.NIM_S;
  const base = kind === 'usage' ? S.usagePanel : kind === 'log' ? S.toolLogPanel : S.insightsPanel;
  return (
    <div style={{ ...base, transform: open ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={S.usageHdr}>
        <span style={S.usageTitle}>{title}</span>
        <button style={S.closeBtn} onClick={onClose}>✕</button>
      </div>
      <div style={S.usageBody} className="nim-scroll">
        {kind === 'usage' && [['Total tokens', '128,402'], ['Total cost', '$0.0423'], ['Requests', '214'], ['Avg / req', '$0.00020']].map(([k, v]) => (
          <div key={k} style={S.usageStat}><span style={S.usageKey}>{k}</span><span style={S.usageVal}>{v}</span></div>
        ))}
        {kind === 'log' && [['retrieve_context', '{ "k": 6 }', '6 chunks · 41ms'], ['web_fetch', '{ "url": "…/spec" }', 'ok · 220ms'], ['write_memory', '{ "fact": "…" }', 'stored']].map(([n, a, r], i) => (
          <div key={i} style={S.toolLogRow}>
            <div style={S.toolLogMeta}><span style={S.toolLogName}>{n}</span><span style={S.toolLogTime}>14:3{i}</span></div>
            <div style={S.toolLogArgs}>{a}</div>
            <div style={S.toolLogResult}>{r}</div>
          </div>
        ))}
        {kind === 'insights' && ['You compare routing strategies often — a saved decision table may help.', 'Most of your spend is on the 70B model for reasoning prompts.'].map((t, i) => (
          <div key={i} style={S.insightRow}>
            <span style={S.insightDot} />
            <div style={S.insightContent}>{t}<div style={S.insightMeta}>{i ? '1h ago' : '12m ago'}</div></div>
            <button style={S.insightDel}>🗑</button>
          </div>
        ))}
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
