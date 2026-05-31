/* NIM AI Gateway — demo seed data + model constants (window globals) */
window.NIM_MODELS = [
  ['auto', 'Auto'], ['llama', 'LLaMA 8B'], ['coder', 'DeepSeek'], ['reasoning', '70B'],
];
window.NIM_MODEL_LABELS = {
  auto: 'Auto-routed', llama: 'LLaMA 3.1 8B', coder: 'DeepSeek V4', reasoning: 'LLaMA 3.3 70B',
};
window.NIM_MODEL_SUB = { auto: 'routed', llama: 'fast', coder: 'code', reasoning: 'reasoning' };
window.NIM_COMPARE = ['llama', 'coder', 'reasoning'];

window.NIM_WORKSPACES = [
  { id: 'ws1', name: 'Research' },
  { id: 'ws2', name: 'Infra' },
];

window.NIM_CONVERSATIONS = [
  { id: 'c1', title: 'Auto-routing strategy for code prompts', updated_at: '14:32', workspace_id: 'ws2', locked_model: true },
  { id: 'c2', title: 'Summarize the RAG ingestion pipeline', updated_at: '11:08', workspace_id: 'ws1' },
  { id: 'c3', title: 'Cost ceiling per user — policy draft', updated_at: 'Tue', workspace_id: null, memory_enabled: false },
  { id: 'c4', title: 'DeepSeek vs 70B on refactors', updated_at: 'Mon', workspace_id: 'ws2' },
];

// messages keyed by conversation id
window.NIM_MESSAGES = {
  c1: [
    { id: 'm1', role: 'user', text: 'How should auto-routing pick between the 8B and 70B models for a code prompt?' },
    { id: 'm2', role: 'ai', model: 'reasoning', totalTokens: 1284, costUsd: 0.00042, queryType: 'relational', srcCount: 3,
      text: "Score the prompt on **complexity** and **risk**, then route to the cheapest model that clears the bar.\n\n- Short, single-file edits → `LLaMA 3.1 8B` (fast, cheap)\n- Multi-file refactors or ambiguous specs → `LLaMA 3.3 70B`\n- Anything code-generation heavy → `DeepSeek V4`\n\nKeep a confidence threshold so low-confidence routes escalate automatically." },
    { id: 'm3', role: 'user', text: 'What signal works best for "complexity"?' },
    { id: 'm4', role: 'ai', model: 'reasoning', totalTokens: 642, costUsd: 0.00021, queryType: 'factual', srcCount: 1,
      text: "Token count of the prompt plus a quick AST-ish heuristic: number of referenced files, presence of stack traces, and whether the ask is *generative* vs *explanatory*. A small classifier on those features beats raw length alone." },
  ],
  c2: [
    { id: 'm1', role: 'user', text: 'Give me a one-paragraph summary of the RAG ingestion pipeline.' },
    { id: 'm2', role: 'ai', model: 'coder', totalTokens: 880, costUsd: 0.00029, queryType: 'broad', srcCount: 4,
      text: "Files and ingested URLs are chunked, embedded, and written to the vector store keyed by workspace. At query time the gateway pulls the top-k chunks, attaches them as context, and records `provenance[]` so each answer can report its source count." },
  ],
  c3: [
    { id: 'm1', role: 'user', text: 'Draft a per-user monthly cost ceiling policy.' },
    { id: 'm2', role: 'ai', model: 'llama', totalTokens: 410, costUsd: 0.00013, queryType: 'temporal', srcCount: 0,
      text: "Default ceiling **$25/mo**, soft-warn at 80%, hard-stop at 100% with an admin override. Reset on the 1st. Track spend per `query_type` so routing can be tuned where it's most expensive." },
  ],
  c4: [],
};

window.NIM_FILES = [
  { id: 'f1', filename: 'architecture-notes.md', status: 'ready' },
  { id: 'f2', filename: 'routing-benchmarks.csv', status: 'ready' },
  { id: 'f3', filename: 'ingestion-spec.pdf', status: 'processing' },
  { id: 'f4', filename: 'old-pricing.txt', status: 'failed' },
];

window.NIM_MEMORY = [
  { name: 'USER', color: '#27d8ff', pairs: [['name', 'Yusuf'], ['role', 'solo dev / operator'], ['timezone', 'UTC+3']] },
  { name: 'STACK', color: '#3dff6e', pairs: [['backend', 'FastAPI + Postgres'], ['frontend', 'React + Vite'], ['prefers', 'TypeScript over JS']] },
  { name: 'PROJECT', color: '#ffb000', pairs: [['name', 'NIM AI Gateway'], ['goal', 'unified multi-model API'], ['status', 'frontend complete']] },
  { name: 'GOALS', color: '#ff2222', pairs: [['next', 'JWT + role policies'], ['then', 'cost ceilings per user']] },
];

window.nimStatusColor = (st) => ({
  ready:      { bg: 'rgba(61,255,110,0.10)', color: '#3dff6e' },
  processing: { bg: 'rgba(255,176,0,0.10)',  color: '#ffb000' },
  failed:     { bg: 'rgba(255,34,34,0.10)',  color: '#ff2222' },
}[st] || { bg: 'rgba(90,90,90,0.10)', color: '#8f8f8f' });
