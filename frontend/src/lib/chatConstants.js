export const MODEL_KEYS = {
  llama:     'meta/llama-3.1-8b-instruct',
  coder:     'deepseek-ai/deepseek-v4-flash',
  reasoning: 'meta/llama-3.3-70b-instruct',
}
export const MODEL_LABELS = {
  [MODEL_KEYS.llama]:     'LLaMA 3.1 8B',
  [MODEL_KEYS.coder]:     'DeepSeek V4',
  [MODEL_KEYS.reasoning]: 'LLaMA 3.3 70B',
}
export const MODEL_SUBLABELS = {
  [MODEL_KEYS.llama]:     'fast',
  [MODEL_KEYS.coder]:     'code',
  [MODEL_KEYS.reasoning]: 'reasoning',
}
export const COMPARE_MODELS = Object.values(MODEL_KEYS)

export const SECTION_COLORS = {
  USER:'#818cf8', STACK:'#34d399', PROJECT:'#fbbf24', CORRECTIONS:'#f87171', PATTERNS:'#a78bfa',
  GOALS:'#38bdf8', ARCH:'#fb923c', STATUS:'#4ade80', PENDING:'#f472b6',
}
