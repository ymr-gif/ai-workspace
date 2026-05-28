export function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso), now = new Date(), diffH = (now - d) / 3600000
  if (diffH < 24)  return d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
  if (diffH < 168) return d.toLocaleDateString([], { weekday:'short', hour:'2-digit', minute:'2-digit' })
  return d.toLocaleDateString([], { month:'short', day:'numeric' })
}

export function parseMemory(content) {
  if (!content) return []
  const sections = []; let current = null
  for (const raw of content.split('\n')) {
    const line = raw.trim(); if (!line) continue
    const hm = line.match(/^\[([A-Z]+)\]$/)
    if (hm) { current = { name: hm[1], pairs: [] }; sections.push(current); continue }
    if (current) {
      const ci = line.indexOf(':')
      if (ci > 0) current.pairs.push({ key: line.slice(0, ci).trim(), val: line.slice(ci + 1).trim() })
    }
  }
  return sections
}

export function computeDiff(oldText, newText) {
  const ol = (oldText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const nl = (newText || '').split('\n').map(l => l.trim()).filter(Boolean)
  const os = new Set(ol), ns = new Set(nl), result = []
  for (const l of nl) result.push({ type: os.has(l) ? 'same' : 'added',   line: l })
  for (const l of ol) if (!ns.has(l)) result.push({ type: 'removed', line: l })
  return result
}
