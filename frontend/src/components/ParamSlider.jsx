import s from '../lib/chatStyles.js'

export default function ParamSlider({ label, enabled, onToggle, value, onChange, min, max, step, fmt }) {
  return (
    <div style={s.paramItem}>
      <input type="checkbox" checked={enabled} onChange={e => onToggle(e.target.checked)} style={{ accentColor:'#6366f1', cursor:'pointer' }} />
      <span style={{ ...s.paramLabel, color: enabled ? '#94a3b8' : '#475569' }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={!enabled}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex:1, accentColor:'#6366f1', cursor: enabled ? 'pointer' : 'default' }} />
      <span style={{ ...s.paramVal, color: enabled ? '#94a3b8' : '#334155' }}>
        {fmt ? fmt(value) : value}
      </span>
    </div>
  )
}
