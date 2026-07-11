import { useEffect } from 'react'
import s from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

import MemoryPanel from '../MemoryPanel'
import GoalsPanel from '../GoalsPanel'
import InsightsPanel from '../InsightsPanel'
import FilesPanel from '../FilesPanel'
import UsagePanel from '../UsagePanel'
import ToolLogPanel from '../ToolLogPanel'
import AutomationsPanel from '../AutomationsPanel'
import IntegrationsPanel from '../IntegrationsPanel'
import InvitePanel from '../InvitePanel'

// Persistent right inspector. One group tab active; one sub-pane visible.
// Panels keep their per-hook open flags (data-load-on-open effects depend on
// them) — this component is the single writer of those flags.
export const DOCK_GROUPS = {
  mind:  [['memory', 'Memory'], ['goals', 'Goals'], ['insights', 'Insights']],
  files: [['files', 'Library']],
  ops:   [['usage', 'Usage'], ['toolLog', 'Tool log'], ['auto', 'Automations'], ['integ', 'Integrations']],
  admin: [['invites', 'Invites']],
}

const PANES = {
  memory: MemoryPanel, goals: GoalsPanel, insights: InsightsPanel,
  files: FilesPanel, usage: UsagePanel, toolLog: ToolLogPanel,
  auto: AutomationsPanel, integ: IntegrationsPanel, invites: InvitePanel,
}

export default function Dock({ tab, sub, setTab, setSub, userRole }) {
  const p = usePanelProps()

  // sync legacy open flags to the active pane
  useEffect(() => {
    const flag = {
      memory: p.mem.setMemOpen, goals: p.goals.setGoalsOpen, insights: p.insights.setInsightsOpen,
      files: p.files.setFilesOpen, usage: p.usage.setUsageOpen, toolLog: p.toolLog.setToolLogOpen,
      auto: p.auto.setAutoOpen, integ: p.integ.setIntegOpen, invites: p.admin.setInviteOpen,
    }
    const active = tab ? sub : null
    for (const [key, set] of Object.entries(flag)) set(key === active)
  }, [tab, sub])

  if (!tab) return null
  const groups = Object.keys(DOCK_GROUPS).filter(g => g !== 'admin' || userRole === 'admin')
  const subs = DOCK_GROUPS[tab] || []
  const Pane = PANES[sub]

  return (
    <div style={s.dock}>
      <div style={s.dockTabs}>
        {groups.map(g => (
          <button key={g} onClick={() => { setTab(g); setSub(DOCK_GROUPS[g][0][0]) }}
            style={{ ...s.dockTab, ...(tab === g ? s.dockTabOn : {}) }}>
            {g}
          </button>
        ))}
        <button onClick={() => setTab(null)} style={{ ...s.dockTab, flex:'0 0 34px' }} title="Close dock">✕</button>
      </div>
      {subs.length > 1 && (
        <div style={s.dockSubs}>
          {subs.map(([id, label]) => (
            <button key={id} onClick={() => setSub(id)}
              style={{ ...s.dockSub, ...(sub === id ? s.dockSubOn : {}) }}>
              {label}
            </button>
          ))}
        </div>
      )}
      {Pane ? <Pane /> : null}
    </div>
  )
}
