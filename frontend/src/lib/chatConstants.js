export const MODEL_KEYS = {
  llama:     'meta/llama-3.1-8b-instruct',
  coder:     'deepseek-ai/deepseek-v4-flash',
  reasoning: 'openai/gpt-oss-120b',
}
export const MODEL_LABELS = {
  [MODEL_KEYS.llama]:     'LLaMA 3.1 8B',
  [MODEL_KEYS.coder]:     'DeepSeek V4',
  [MODEL_KEYS.reasoning]: 'GPT-OSS 120B',
  // legacy ids — label replies persisted before the reasoning-model swaps
  'meta/llama-3.3-70b-instruct':            'LLaMA 3.3 70B',
  'nvidia/llama-3.3-nemotron-super-49b-v1': 'Nemotron 49B',
}
export const MODEL_SUBLABELS = {
  [MODEL_KEYS.llama]:     'fast',
  [MODEL_KEYS.coder]:     'code',
  [MODEL_KEYS.reasoning]: 'reasoning',
}
export const COMPARE_MODELS = Object.values(MODEL_KEYS)

export const SECTION_COLORS = {
  USER:'#4f9cf0', STACK:'#55d67c', PROJECT:'#f2a33c', CORRECTIONS:'#e5534b', PATTERNS:'#4f9cf0',
  GOALS:'#55d67c', ARCH:'#f2a33c', STATUS:'#55d67c', PENDING:'#f2a33c',
}
