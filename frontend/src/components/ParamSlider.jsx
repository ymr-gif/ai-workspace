import s, { RED, FG3, FG4, FG5 } from '../lib/chatStyles.js'

export default function ParamSlider({ label, enabled, onToggle, value, onChange, min, max, step, fmt }) {
  return (
    <div style={s.paramItem}>
      <input type="checkbox" checked={enabled} onChange={e => onToggle(e.target.checked)} style={{ accentColor:RED, cursor:'pointer' }} />
      <span style={{ ...s.paramLabel, color: enabled ? FG3 : FG4 }}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} disabled={!enabled}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ flex:1, accentColor:RED, cursor: enabled ? 'pointer' : 'default' }} />
      <span style={{ ...s.paramVal, color: enabled ? FG3 : FG5 }}>
        {fmt ? fmt(value) : value}
      </span>
    </div>
  )
}
