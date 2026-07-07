import s, { RED } from '../../../lib/chatStyles.js'
import ParamSlider from '../../ParamSlider.jsx'

export default function ModelToolbar({
  selectedModel, setSelectedModel,
  compareMode, setCompareMode,
  paramsOpen, setParamsOpen,
  tempEnabled, setTempEnabled, temperature, setTemperature,
  tokensEnabled, setTokensEnabled, maxTokens, setMaxTokens,
  topPEnabled, setTopPEnabled, topP, setTopP,
  attachedFiles, detachFile,
  input, setInput, loading,
  send,
  voice,
}) {
  return (
    <div>
      <div style={s.toolbarWrap}>
        <div style={s.toolbar}>
          <div style={s.modelPills}>
            {[['auto', 'Auto'], ['llama', 'LLaMA 8B'], ['coder', 'DeepSeek'], ['reasoning', '120B']].map(([key, label]) => (
              <button key={key} onClick={() => setSelectedModel(key)}
                style={{ ...s.pill, ...(selectedModel === key ? s.pillActive : {}) }}>
                {label}
              </button>
            ))}
          </div>
          <div style={s.toolRight}>
            <button onClick={() => setCompareMode(!compareMode)}
              style={{ ...s.pill, ...(compareMode ? s.pillCompare : {}) }}
              title="Run same prompt on all 3 models side by side">
              ⊞ Compare
            </button>
            <button onClick={() => setParamsOpen(!paramsOpen)}
              style={{ ...s.pill, ...(paramsOpen ? s.pillActive : {}) }}
              title="Temperature / max tokens / top-p">
              ⚙
            </button>
          </div>
        </div>

        {paramsOpen && (
          <div style={s.paramsBar}>
            <ParamSlider label="Temp" enabled={tempEnabled} onToggle={setTempEnabled}
              value={temperature} onChange={setTemperature} min={0} max={2} step={0.05}
              fmt={v => v.toFixed(2)} />
            <ParamSlider label="Tokens" enabled={tokensEnabled} onToggle={setTokensEnabled}
              value={maxTokens} onChange={setMaxTokens} min={256} max={4096} step={256}
              fmt={v => v} />
            <ParamSlider label="Top-p" enabled={topPEnabled} onToggle={setTopPEnabled}
              value={topP} onChange={setTopP} min={0} max={1} step={0.05}
              fmt={v => v.toFixed(2)} />
          </div>
        )}
      </div>

      {attachedFiles.length > 0 && (
        <div style={s.fileChipsRow}>
          {attachedFiles.map(f => (
            <span key={f.id} style={s.fileChip}>
              📄 {f.filename.length > 24 ? f.filename.slice(0,22)+'…' : f.filename}
              <span style={s.chipX} onClick={() => detachFile(f.id)} title="Detach">✕</span>
            </span>
          ))}
        </div>
      )}

      <form onSubmit={send} style={s.bar}>
        {voice && (voice.voiceAvailable === true || voice.voiceAvailable === null) && (
          <button type="button"
            onClick={voice.recording ? voice.stopRecording : voice.startRecording}
            disabled={voice.transcribing}
            style={{ ...s.micBtn, ...(voice.recording ? s.micRec : {}) }}>
            {voice.transcribing ? 'BUSY' : voice.recording ? 'REC' : 'MIC'}
          </button>
        )}
        <input value={input} onChange={e => setInput(e.target.value)} placeholder={compareMode ? 'Compare prompt across all models…' : 'Ask anything…'} disabled={loading} style={s.input} />
        <button type="submit" disabled={loading || !input.trim()} style={{ ...s.send, ...(compareMode ? { background:'rgba(61,255,110,0.10)', color:RED, border:`1px solid ${RED}`, textShadow:`0 0 6px rgba(61,255,110,0.5)` } : {}) }}>
          {loading ? '…' : compareMode ? '⊞' : 'Send'}
        </button>
      </form>
    </div>
  )
}
