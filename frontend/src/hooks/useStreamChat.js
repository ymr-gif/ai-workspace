import { MODEL_KEYS } from '../lib/chatConstants.js'

export default function useStreamChat({ token, conv, modelParams, mem, insights, onLogout }) {
  const authHeaders = { 'Authorization': `Bearer ${token}` }

  function buildBody(text) {
    const body = { message: text, conversation_id: conv.activeConvId }
    if (modelParams.selectedModel !== 'auto') body.model_override = modelParams.selectedModel
    if (modelParams.compareMode) body.compare = true
    if (modelParams.tempEnabled)   body.temperature = modelParams.temperature
    if (modelParams.tokensEnabled) body.max_tokens  = modelParams.maxTokens
    if (modelParams.topPEnabled)   body.top_p       = modelParams.topP
    return body
  }

  async function send(e) {
    e.preventDefault()
    const text = conv.input.trim(); if (!text || conv.loading) return
    const isCompare = modelParams.compareMode
    const userId = conv.nextId.current++, aiId = conv.nextId.current++
    conv.setInput(''); conv.setLoading(true); conv.setProactive(null); conv.setPendingWriteFact(null); conv.setLastSession('')

    if (isCompare) {
      conv.setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'compare', responses: Object.fromEntries(Object.values(MODEL_KEYS).map(m => [m, { text: '', streaming: true }])) },
      ])
    } else {
      conv.setMessages(prev => [...prev,
        { id: userId, role: 'user', text, streaming: false },
        { id: aiId, role: 'ai', text: '', model: null, streaming: true },
      ])
    }

    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody(text)),
      })
      if (res.status === 401) { onLogout(); return }
      if (!res.ok) {
        conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: 'Request failed', streaming: false } : m))
        return
      }

      const reader = res.body.getReader(), decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { done, value } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n'); buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim(); if (!raw) continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              if (isCompare) {
                const model = event.model
                conv.setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: { ...m.responses, [model]: { ...m.responses[model], text: (m.responses[model]?.text||'') + event.content } } }
                  : m))
              } else {
                conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, text: m.text + event.content } : m))
              }
            } else if (event.type === 'preamble_discard') {
              // streamed tokens were pre-tool preamble — clear them; real answer follows
              if (isCompare) {
                const model = event.model
                conv.setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: { ...m.responses, [model]: { ...m.responses[model], text: '' } } }
                  : m))
              } else {
                conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, text: '' } : m))
              }
            } else if (event.type === 'done') {
              if (isCompare) {
                conv.setMessages(prev => prev.map(m => m.id === aiId
                  ? { ...m, responses: Object.fromEntries(Object.entries(m.responses).map(([k,v]) => [k, { ...v, streaming: false }])) }
                  : m))
              } else {
                conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, model: event.model, streaming: false, promptTokens: event.prompt_tokens, completionTokens: event.completion_tokens, totalTokens: event.total_tokens, costUsd: event.cost_usd, provenance: event.provenance || [], queryType: event.query_type || '', srcCount: event.src_count ?? 0, webSearched: event.web_searched ?? false, urlFetched: event.url_fetched ?? false } : m))
                mem.setMemTick(t => t + 1)
                setTimeout(() => { if (mem.memTab === 'graph') insights.loadGraphStats() }, 2000)
              }
              if (event.last_session) conv.setLastSession(event.last_session)
              const cid = event.conversation_id
              if (cid) {
                conv.setActiveConvId(cid)
                conv.setConversations(prev => {
                  const exists = prev.find(c => c.id === cid)
                  if (exists) return [{ ...exists, updated_at: new Date().toISOString() }, ...prev.filter(c => c.id !== cid)]
                  return [{ id: cid, title: text.slice(0, 60), updated_at: new Date().toISOString(), memory_enabled: true, system_prompt: '', locked_model: '' }, ...prev]
                })
              }
            } else if (event.type === 'tool_call') {
              conv.setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, toolCalls: [...(m.toolCalls || []), { name: event.name, args: event.args, result: null }] }
                : m))
            } else if (event.type === 'tool_result') {
              conv.setMessages(prev => prev.map(m => m.id === aiId
                ? { ...m, toolCalls: (m.toolCalls || []).map((tc, i) =>
                    i === (m.toolCalls.length - 1) ? { ...tc, result: event.content } : tc
                  )}
                : m))
            } else if (event.type === 'ask_user') {
              conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, askUser: event.question } : m))
            } else if (event.type === 'confirm_write_memory') {
              conv.setPendingWriteFact(event.fact)
            } else if (event.type === 'proactive') {
              conv.setProactive(event.content)
            } else if (event.type === 'error') {
              conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: event.message || 'Error', streaming: false } : m))
            }
          } catch { /* ignore */ }
        }
      }
    } catch (err) {
      conv.setMessages(prev => prev.map(m => m.id === aiId ? { ...m, role: 'err', text: `Network error: ${err.message}`, streaming: false } : m))
    } finally { conv.setLoading(false) }
  }

  return { send, buildBody }
}
