# NIM // CANVAS — Build Plan
> Jarvis-style node-graph canvas for the NIM AI Gateway.
> This is the original build checklist (all 5 stages complete). Some of it is now
> historical — see **Current State** below for what's actually true today.

---

## ⚠ Current State (supersedes this plan where they differ)

The canvas shipped, then evolved. Authoritative deltas vs. the checklist below:

- **Workspace layer removed** (migration 037 — collapsed to sessions only). There is **no Workspace
  node**, no `workspace_id`, no `/api/workspaces`. The registry is **11 node types**:
  `input, session, memory, files, logs, usage, config, insights, goals, automations, mech`.
- **Session node label** = **`SESSION | <title>`** (the conversation's auto-title, enriched onto
  `/api/canvas/graph` by `api/canvas.py`). The permanent JARVIS session shows
  `GLOBAL SESSION / JARVIS // PERSISTENT`. Global vs user is keyed off `config.kind`
  (`global`/`user`), not a `conversation_id` presence check.
- **Per-session chat:** the chat is a single right-edge drawer (`SessionOutputPanel`, a portal on
  the static `session` node) that **follows the active conversation**. The active conversation is
  set by (a) the **Input→Session wire** and (b) **clicking a session node** (click-to-focus; opens
  the drawer). Whichever happened last wins; both display and send-routing follow it.
- **Single global card:** the backend `kind="global"` session node is filtered out of the canvas
  render (the static `session` node represents global). No duplicate global card.
- **Core-node protection:** `input` + the global session are `protected`; the AI tool / REST can't
  delete them. Sessions dedup + reconcile (orphan reaping) run periodically.

Everything below documents the original design; treat the bullets above as current truth.

---

## Vision
Replace the flat chat UI with a **draggable node-graph canvas** where NIM's cognitive pipeline
(memory, routing, files, context, output) is visualized as an interactive graph. Feels like a
JARVIS HUD — the AI's internal state is visible and manipulable. Built on top of the existing
NIM AI Gateway backend (`ymr-gif/ai-workspace`, frontend at `/frontend`).

---

## Design Decisions (locked)

### Visual
| Token | Value |
|-------|-------|
| Canvas bg | `#000` + CPU schematic (0.7 opacity) + dot grid overlay (very faint `#1a1a1a`) |
| Node bg | `#0a0a0a` |
| Node border | `1px solid #4a4a4a`, left accent `2px solid #ff2222` |
| Primary accent | `#ff2222` (ULTRAKILL red) |
| Active wire | `rgba(139,92,246,0.7)` + glow `0 0 8px rgba(139,92,246,0.35)` (violet) |
| Idle wire | `#555555` 1.5px bezier |
| User-drawn wire | `#808080` dashed 1px |
| Border radius | `0px` — everything square |
| CRT effects | scanlines + beam + vignette (from `effects.css`) |

### Fonts (both replacing Silkscreen + VT323)
| Role | Font | Sizes |
|------|------|-------|
| Chrome: labels, headers, buttons, menu | **Chakra Petch** (400/600/700) | 9–24px |
| Body: chat, data, code, terminal | **JetBrains Mono** (400/500) | 12–18px |

### Icons
**Lucide** (CDN) — replaces all emoji. No emoji anywhere in the UI.
Key mappings:
- Memory → `Brain` · Files → `FolderOpen` · Logs → `ScrollText`
- Usage → `BarChart2` · Config → `Settings`
- Input → `Terminal` · Session → `MessageSquare` · Add node → `Plus`

### Wire system
| State | Style |
|-------|-------|
| Idle | `#555555`, 1.5px, bezier |
| Active/processing | violet `rgba(139,92,246,0.7)`, animated dash flow, glow |
| User-drawn | `#808080` dashed 1px, appears while dragging |
| Handles | Small squares on node edges (not circles) |

### Node inventory (core types)  *(Workspace row removed — see Current State)*
| Node | Type | Behavior |
|------|------|----------|
| Input | Singleton | Draggable, wire/click routes to a session |
| Session | Multi | One per conversation; the static node hosts the chat drawer |
| Memory | Singleton | Radial child nodes: Edit / History / Graph |
| Files | Singleton | File library + attach |
| Logs | Singleton | Click → popup |
| Usage | Singleton | Click → popup |
| Config | Singleton | Model/params/mech slot |

> **Note:** Backend node registry also defines `insights`, `goals`, `automations`, `mech` as types — these are **not standalone canvas nodes**. They live inside their respective nodes (insights = ghost card above Input; goals/automations = Config node info section; mech = UNIT slot in Config). `create_canvas_node` calls with these types must be rejected by a backend guard.

### Entry flow
`Boot (PC hardware stats + canvas lines)` → `Canvas` (no menu)

### Session targeting (Input node)  *(see Current State for shipped behavior)*
- Active conversation = the **Input→Session wire** target, or a **clicked** session node (last wins)
- Default (unwired) → JARVIS global conversation
- Send routing + the chat drawer both follow the active conversation

### Conversation history
- Each session = one **Session node** on canvas; label `SESSION | <title>`
- Output: one right-edge chat drawer (`SessionOutputPanel`) that follows the active session,
  with per-conversation history cached + fetched from `/api/conversations/{id}/messages`

### Memory branching (radial, real canvas nodes)
- Click Memory → 3 child nodes spawn radially from parent
- Each child connected with animated violet wire
- Children independently draggable, persist until dismissed (X button)
- Children: **Edit** (raw textarea + save), **History** (version list + diff), **Graph** (Neo4j viz)

### Insights
- Ghost suggestion card floats above Input node
- Shows insight text (JetBrains Mono, dimmed)
- Buttons: `Insert` (fills input) + `Dismiss`
- Auto-dismisses after 10s
- AI automates insight generation in backend (no manual node)

### Goals + Automations
- Both backend-automated — no canvas nodes
- Backend note: expose goal/automation status in session output or Config node info panel

### Mech / UNIT slot
- Lives inside Config node (bottom section)
- Flexible: accepts `src` (image), `ascii` string, or default placeholder
- Status label: "STANDBY" in amber

---

## File Structure
```
ui_kits/nim-canvas/
├── index.html          — root HTML, fonts, CRT overlays, canvas mount
├── styles.js           — NIM_S token object (canvas-specific)
├── data.js             — seed/mock data + constants
├── BootScreen.jsx      — typewriter boot with PC hardware stats
├── Canvas.jsx          — React Flow canvas shell, background, wire config
├── nodes/
│   ├── InputNode.jsx
│   ├── SessionNode.jsx
│   ├── MemoryNode.jsx
│   ├── MemoryEditNode.jsx
│   ├── MemoryHistoryNode.jsx
│   ├── MemoryGraphNode.jsx
│   ├── FilesNode.jsx
│   ├── LogsNode.jsx
│   ├── UsageNode.jsx
│   └── ConfigNode.jsx
├── panels/
│   ├── SessionOutputPanel.jsx   — floating message feed
│   ├── SessionListPanel.jsx     — expandable session list
│   └── InsightCard.jsx          — ghost suggestion above Input
├── menus/
│   └── ContextMenu.jsx          — right-click add-node menu
└── app.jsx                      — orchestrator, phase state (boot → canvas)
```

---

## Backend Specs (for Claude Code — Stage 5)

### New endpoint required: `GET /api/system/hardware`
```python
# Dependencies: psutil (already common), pynvml (for NVIDIA GPU)
# pip install psutil pynvml
# No auth required (or read-only)
# Graceful fallback if GPU not available (try/except pynvml)

Response JSON:
{
  "cpu": {
    "name": str,          # e.g. "Intel Core i9-13900K"
    "freq_ghz": float,    # current max freq
    "cores": int,         # physical cores
    "threads": int,       # logical cores
    "usage_pct": float    # current usage %
  },
  "ram": {
    "total_gb": float,
    "used_gb": float,
    "available_gb": float
  },
  "gpu": {                # null if no NVIDIA GPU
    "name": str,
    "vram_total_gb": float,
    "vram_used_gb": float,
    "temp_c": int,
    "load_pct": float
  },
  "disk": {
    "total_tb": float,
    "free_tb": float
  },
  "uptime": str,          # e.g. "3d 14h 22m"
  "hostname": str
}
```

### Wire → backend mapping (implement in Stage 5)
| Wire connection | Backend effect |
|-----------------|----------------|
| File → Session | adds `file_ids: list[str]` to ChatRequest (new field); backend merges with conversation-attached files |
| Input → Session | routes the message to that session's conversation (the drawer follows it) |
| Memory → Session | visual only — memory always-on, no API param |

### ~~Backend note: extensible Workspace nodes~~  *(REMOVED — workspace layer dropped, migration 037)*

---

## Stage Checklist

---

### Stage 1 — Foundation ✅ COMPLETE
**Goal:** Boot sequence + canvas shell with background and wire system. No real nodes yet.

#### 1A — Boot sequence
- [x] Chakra Petch + JetBrains Mono fonts loaded (Google Fonts CDN)
- [x] Lucide icons CDN loaded
- [x] CRT effects layer (effects.css) applied
- [x] ULTRAKILL red block cursor (0.55em wide, glow, blink 1s step-end)
- [x] Typewriter reveal: char-by-char, ~14ms/char, 70ms pause between lines
- [x] Hardware section: `fetch('/api/system/hardware')` with mock fallback
- [x] Mock hardware data structure (CPU / RAM / GPU / disk / uptime / hostname)
- [x] Hardware lines typed out with real or mock values:
  - `> HOSTNAME: {hostname}`
  - `> CPU: {name} @ {freq}GHz`
  - `> CORES: {cores} physical / {threads} logical`
  - `> RAM: {used}GB / {total}GB`
  - `> GPU: {name} {vram_total}GB` (or `NO GPU DETECTED` if null)
  - `> VRAM: {vram_used}GB / {vram_total}GB used`
  - `> DISK: {free}TB free / {total}TB`
  - `> UPTIME: {uptime}`
- [x] Canvas-specific lines (after hardware, same typewriter):
  - `> CANVAS ENGINE .............. INITIALIZED`
  - `> NODE GRAPH RENDERER ........ READY`
  - `> REACT FLOW ................. ONLINE`
  - `> PULLING SESSION DATA ........ OK`
  - `> MEMORY CORE ................ MOUNTED`
  - `> ROUTING SEQUENCER .......... STANDBY`
- [x] "ALL SYSTEMS NOMINAL." line (green + glow, JetBrains Mono 20px)
- [x] Blinking prompt: "PRESS [ENTER] TO CONTINUE" (Chakra Petch, [ENTER] in red)
- [x] Enter / Space / click transitions to canvas

#### 1B — Canvas shell
- [x] React Flow initialized (full viewport, pan enabled, zoom enabled)
- [x] Minimap (bottom-right, dark theme, `#0a0a0a` bg, very small)
- [x] Zoom controls (fit/in/out, top-right, Chakra Petch labels, no border radius)
- [x] Background layer 1: CPU schematic SVG (`../../assets/cpu-schematic.svg`, fixed, 0.7 opacity)
- [x] Background layer 2: dot grid overlay (`#1a1a1a` dots, 20px spacing, faint)
- [x] CRT overlays persist on canvas (grille/scanlines/beam/vignette z-index above canvas)
- [x] Global canvas font: Chakra Petch for chrome, JetBrains Mono for data
- [x] `-webkit-font-smoothing: antialiased` (JetBrains Mono renders better with AA unlike VT323)
- [x] `::selection { background: #ff2222; color: #000 }`
- [x] `input:focus { border-color: #ff2222; box-shadow: 0 0 0 1px rgba(255,34,34,.4) }`
- [x] `input[type=range] { accent-color: #ff2222 }`
- [x] Scrollbars: 4px, `#4a4a4a` thumb, `#ff2222` on hover
- [x] Right-click context menu skeleton (shows node type list, non-functional, visual only)
  - Header: "ADD NODE" (Chakra Petch 9px uppercase, `#5a5a5a`)
  - Items with Lucide icons: Input, Session, Memory, Files, Logs, Usage, Config
  - Hover state: red text + `rgba(255,34,34,.08)` bg
  - No border radius, ULTRAKILL styled, dismisses on Escape/click outside

#### 1C — Wire system
- [x] Default React Flow edge type overridden: bezier, custom styled
- [x] Idle edge: `stroke: #555555`, `strokeWidth: 1.5`, no animation
- [x] Active edge: `stroke: rgba(139,92,246,0.7)`, `strokeWidth: 2`, animated dash (`stroke-dasharray: 6 3`, offset animation), `filter: drop-shadow(0 0 6px rgba(139,92,246,0.35))`
- [x] User-drawn edge (connecting): `stroke: #808080`, `strokeWidth: 1`, `stroke-dasharray: 4 4`
- [x] Connection handles: square (`borderRadius: 0`), 8×8px, `#4a4a4a` default, `#ff2222` on hover
- [x] Edge drop on empty canvas cancels (no dangling wires)

---

### Stage 2 — Core nodes ✅ COMPLETE (visual shells, mock data)
**Goal:** All 4 core node types rendered correctly with mock data. No real branching or animation yet.

#### 2A — Input node
- [x] Card dimensions: ~280px wide, auto height
- [x] Header: Lucide `Terminal` (14px, `#5a5a5a`) + "INPUT" (Chakra Petch 10px uppercase)
- [x] Left border accent: `2px solid #ff2222`
- [x] Session targeting pill: shows session name (Chakra Petch 9px, red text, red border)
  - [x] Click pill → inline dropdown with session list (max 4 visible, scroll)
  - [x] Auto-targets last-interacted session on mount
- [x] Text area: JetBrains Mono 14px, `#000` bg, `1px #4a4a4a` border, placeholder "route query..."
- [x] Send button: red fill `#ff2222`, black text, Chakra Petch 10px, "SEND"
- [x] Insight ghost card slot: hidden `div` above card (visible in Stage 4)
- [x] Output handle: right edge, square, connects to Session nodes
- [x] Drag: freely repositionable anywhere on canvas

#### 2B — Session node
- [x] Card dimensions: ~300px wide
- [x] Header: `SESSION | <title>` (JetBrains Mono 13px), conversation_id prefix below
- [x] Last message preview: JetBrains Mono 12px, `#8f8f8f`, truncated 2 lines
- [x] Timestamp: Chakra Petch 8px, `#5a5a5a`, right-aligned
- [x] "LAST INTERACTED" label (Chakra Petch 8px, `#383838`, uppercase)
- [x] 2 recent sessions list (compact rows, 1px `#262626` divider between)
- [x] Corner expand button (Lucide `ChevronDown`, `#5a5a5a`) → floating session list panel
  - [x] Floating panel: `#0a0a0a` bg, `1px #4a4a4a` border, positioned near node
  - [x] Scrollable list of all sessions (JetBrains Mono 13px)
  - [x] Each row: session name + timestamp
  - [x] Click row → pull that session onto canvas as new Session node
  - [x] Close button (X, `#5a5a5a`)
- [x] Status dot: 6px square, idle `#4a4a4a`, active violet `rgba(139,92,246,0.8)` + pulse
- [x] Floating output panel (mock, non-functional in this stage):
  - [x] `position: fixed`, top-right area, `~400px` wide, `~500px` tall
  - [x] Header: session name + Lucide `X` close
  - [x] Message feed area (placeholder "No messages yet")
  - [x] Input wire connection point (left handle, square)
- [x] Input handle: left edge (receives from Input node)
- [x] Output handle: right edge (to Memory, Files nodes)

#### 2C — Config node
- [x] Card dimensions: ~280px wide
- [x] Header: Lucide `Settings` + "CONFIG" (Chakra Petch 10px)
- [x] Section: "MODEL" label (Chakra Petch 8px uppercase, `#5a5a5a`)
  - [x] Model pills: AUTO / LLAMA 8B / DEEPSEEK / 70B (square, active = red fill black text)
- [x] Section: "PARAMS" (collapsible, Lucide `ChevronRight`/`ChevronDown`)
  - [x] Temperature slider (JetBrains Mono value label, `accent-color: #ff2222`)
  - [x] Max tokens slider
  - [x] Top-p slider
- [x] Section: "COST" — limit display (JetBrains Mono 12px, `#8f8f8f`)
- [x] Divider (`1px #262626`)
- [x] UNIT slot (bottom section):
  - [x] Header row: "UNIT 01" (Chakra Petch 8px, `#8f8f8f`) + "STANDBY" (amber `#ffb000`)
  - [x] Frame: `1px #4a4a4a`, red corner registration ticks (2px, 10px L-shaped)
  - [x] Default: placeholder ASCII in JetBrains Mono 11px `#5a5a5a`
  - [x] Footer: "PLACEHOLDER · SWAP SPRITE / IMG" (Chakra Petch 8px, `#383838`)
- [x] No connection handles (Config is a standalone configuration node)

#### 2D — Memory node (card only, no branches)
- [x] Card dimensions: ~260px wide
- [x] Header: Lucide `Brain` + "MEMORY" (Chakra Petch 10px)
- [x] Fact count: "11 facts · 4 sections" (JetBrains Mono 13px, `#8f8f8f`)
- [x] Section color indicators (4 small squares: cyan/green/amber/red with section names)
  - [x] USER (cyan `#27d8ff`) · STACK (green `#3dff6e`) · PROJECT (amber `#ffb000`) · GOALS (red `#ff2222`)
  - [x] Each: 6px square + label (Chakra Petch 8px)
- [x] Salience bar: thin 3px bar, most-active fact score, colored by section
- [x] Status dot: animated pulse when memory updating
- [x] "CLICK TO EXPAND" hint (Chakra Petch 8px, `#383838`, bottom of card)
- [x] Click handler: placeholder (logs to console, triggers Stage 3)
- [x] Output handle: right edge (connects to Session nodes)

---

### Stage 3 — Memory branching + node activation animation
**Goal:** Memory spawns child nodes radially. Request triggers pulse sequence across nodes.

#### 3A — Memory radial branches
- [x] Click Memory node → 3 child nodes added to React Flow graph programmatically
- [x] Default radial positions: Edit (top-right), History (right), Graph (bottom-right), ~200px from parent
- [x] Animated wires connect Memory → each child (violet, active style)
- [x] Children independently draggable (no parent lock)
- [x] Each child has X button (Chakra Petch 8px, `#5a5a5a`) → removes that child node + wire
- [x] Collapse all: re-clicking Memory node removes all children + wires

- [x] **Edit child node** (~260px):
  - [x] Header: Lucide `Pencil` + "MEMORY · EDIT"
  - [x] Section selector (Chakra Petch pills: USER/STACK/PROJECT/GOALS)
  - [x] Textarea: JetBrains Mono 13px, `#000` bg, `1px #4a4a4a` border, auto-height
  - [x] Save button (red fill, Chakra Petch "SAVE") + Cancel (ghost)
  - [x] Pre-filled with mock memory content per selected section

- [x] **History child node** (~280px):
  - [x] Header: Lucide `History` + "MEMORY · HISTORY"
  - [x] Version list: rows of v1/v2/v3... (JetBrains Mono 12px)
    - [x] Each row: version number (red) + description + timestamp (Chakra Petch 8px)
  - [x] Expandable diff view per version (added lines green, removed red, same gray)
  - [x] Restore button per version (Chakra Petch 9px, green border `#3dff6e`)
  - [x] Scrollable if many versions (nim-scroll styling)

- [x] **Graph child node** (~320px, taller):
  - [x] Header: Lucide `GitBranch` + "MEMORY · GRAPH"
  - [x] Neo4j visualization area (D3.js circle layout, mock data):
    - [x] Entity nodes: circles, colored by type (user/project/preference/stack)
    - [x] Relation edges: labeled arrows between entities
    - [x] Click entity → small tooltip showing properties (JetBrains Mono 11px)
    - [x] Entity type filter: Chakra Petch pills (ALL / USER / PROJECT / STACK)
    - [x] Drag entities within graph area to reposition
  - [x] "LIVE DATA UNAVAILABLE · CONNECT BACKEND" badge (Chakra Petch 8px, `#5a5a5a`, bottom)
  - [x] Mock data: 8-10 entity nodes, 12-15 relations, realistic types

#### 3B — Node activation animation sequence
- [x] Animation state per node: `idle` | `activating` | `processing` | `done` | `error`
- [x] Visual per state:
  - `idle`: normal card, `#555` handles
  - `activating`: left border pulses red (CSS keyframe `0→ff2222→base`)
  - `processing`: animated violet wire from this node outward, subtle card glow
  - `done`: brief green flash (`#3dff6e`) on card header, fades in 800ms
  - `error`: red border pulse + shake (translate ±2px, 3x)
- [x] Sequence on mock "SEND" (timed, no real backend):
  - 0ms: Input → `activating` (red pulse)
  - 200ms: Config → `activating` (routing indicator)
  - 400ms: Memory → `processing` (reading context, pulse dot spins)
  - 600ms: Session node → `processing` (violet wire animates, output panel opens)
  - 800ms+: Session output panel streams mock text char-by-char (JetBrains Mono)
  - On complete: all nodes → `done` flash, then → `idle`
- [x] Mock send button (for demo, inside Input node, labeled "DEMO SEND")
- [x] Files node activates in sequence if a file wire is connected
- [x] Tool call indicator: inside Session output panel, brief Lucide `Zap` flash per tool

---

### Stage 4 — Secondary nodes + full interactions
**Goal:** All 8 node types complete. Right-click menu functional. Wire drawing works. Insight card live.

#### 4A — Files node
- [x] Header: Lucide `FolderOpen` + "FILES"
- [x] Upload status chips (Chakra Petch 8px, bordered): READY `#3dff6e` / PROCESSING `#ffb000` / FAILED `#ff2222`
- [x] File list (compact rows, JetBrains Mono 12px):
  - [x] Each row: status chip + filename + attach toggle (square checkbox, `accent-color: #ff2222`)
  - [x] Lucide icons: `Eye` (view) + `Download` + `Trash2` (delete)
- [x] URL ingest input: JetBrains Mono 12px, placeholder "https://... ingest URL"
- [x] Fetch button: green border `#3dff6e` + green text, Chakra Petch 9px
- [x] Upload button: cyan border `#27d8ff` + cyan text
- [x] Connection handle: output (right, wire to Session = attach to chat)
- [x] Click attached wire File→Session: visual indicator that file is scoped to that session

#### 4B — Logs node
- [x] Header: Lucide `ScrollText` + "LOGS"
- [x] Click → floating popup near node (`#0a0a0a`, `1px #4a4a4a`, no border radius)
- [x] Popup content: tool call rows
  - [x] Tool name: cyan `#27d8ff`, Chakra Petch 9px
  - [x] Timestamp: JetBrains Mono 11px, `#5a5a5a`
  - [x] Args: JetBrains Mono 11px, `#5a5a5a`, collapsed (click to expand)
  - [x] Result: JetBrains Mono 12px, `#8f8f8f`
- [x] Session filter: Chakra Petch pills at top of popup
- [x] Close on click outside or Escape

#### 4C — Usage node
- [x] Header: Lucide `BarChart2` + "USAGE"
- [x] Click → floating popup near node
- [x] Popup stats (JetBrains Mono 14px):
  - [x] Total tokens + cost (large, white)
  - [x] Per-model breakdown (table: model / tokens / cost)
  - [x] Cost window: "rolling 30d" (Chakra Petch 8px, `#5a5a5a`)
  - [x] Request count + avg/req
- [x] Close on click outside

#### ~~4D — Workspace node~~  *(REMOVED — workspace layer dropped, migration 037)*

#### 4E — Insight ghost card
- [x] Positioned: 8px above Input node, same width, floating (`position: absolute`)
- [x] Background: `rgba(39,216,255,0.06)`, border `1px solid rgba(39,216,255,0.3)`
- [x] Content: JetBrains Mono 13px, `#8f8f8f` (ghost/dimmed)
- [x] Buttons: `Insert` (Chakra Petch 9px, cyan border) + `Dismiss` (ghost)
- [x] Insert: fills insight text into Input textarea
- [x] Dismiss: hides card
- [x] Auto-dismiss: 10s timer (countdown dot visible)
- [x] Slide-in: `transform: translateY(-8px)` → `translateY(0)`, 150ms ease
- [x] Mock trigger: button inside Input node "TRIGGER INSIGHT" for demo

#### 4F — Right-click context menu (functional)
- [x] Renders at cursor position on canvas right-click
- [x] `position: fixed`, `z-index: 9999`, `#0a0a0a` bg, `1px #4a4a4a` border
- [x] Header: "ADD NODE" (Chakra Petch 9px, `#5a5a5a`, uppercase, `1px #262626` bottom border)
- [x] Items (Chakra Petch 10px, full-width, `42px` height):
  - [x] Lucide icon (16px, `#5a5a5a`, left) + node type label
  - [x] Hover: red text + `rgba(255,34,34,0.08)` bg
  - [x] Disabled items (if singleton already exists): `#383838` text, `cursor: not-allowed`
- [x] Click item → adds node at cursor position with default position
- [x] Dismiss: Escape key or click outside

#### 4G — Wire drawing (interactive)
- [x] Drag from output handle → dashed gray wire follows cursor
- [x] Valid drop target (input handle): handle highlights red on hover
- [x] Drop on valid handle → wire connects, style switches to idle gray
- [x] Drop on canvas → wire cancels (no dangling wires)
- [x] Right-click wire → small context menu: "Delete connection" (Chakra Petch 9px, red text)
- [x] Wire tooltip on hover: "SOURCE NODE → TARGET NODE" (JetBrains Mono 11px, `#5a5a5a`)
- [x] Visual feedback for semantic connections:
  - [x] File → Session: Files node gets "ATTACHED" badge (Chakra Petch 8px, green)
  - [x] Memory → Session: Memory status dot turns violet (context injection ON indicator)

---

### Stage 5 — Backend hookup (Claude Code handoff)
**Goal:** Replace all mock data with real API calls. Wire node animations to real SSE events.
Note: This stage is for Claude Code to implement in the real `frontend/` codebase.

#### 5A — Hardware boot endpoint
- [x] Backend: `GET /api/system/hardware` — already exists in `backend/api/system.py` (psutil + pynvml)
- [x] Frontend boot: replace mock data with `fetch('/api/system/hardware')`
- [x] Graceful: if endpoint 404s or errors, falls back to mock data silently
- [x] GPU section: omit GPU lines entirely if `gpu` field is null

#### 5B — Node data (real API)
- [x] Memory node: `GET /api/memory` → real fact count, sections, salience
- [x] Memory Edit child: load real content, `PATCH /api/memory` on save
- [x] Memory History child: `GET /api/memory/history` → real versions + diffs
- [x] Memory Graph child: `GET /api/graph/sample` → real Neo4j entities/relations
- [x] Files node: `GET /api/files` → real file list with status
- [x] Files node upload: `POST /api/files/upload`
- [x] Files node ingest: `POST /api/files/ingest-url`
- [x] Usage node: `GET /api/usage` → real token/cost stats
- [x] Logs node: `GET /api/tool-logs` → real tool call history
- [x] Session list: `GET /api/conversations` → real conversation list

#### 5C — Real-time SSE → node animations
- [x] Session node connects to `POST /api/chat/stream` (SSE)
- [x] SSE `token` event → streams into Session output panel
- [x] SSE `tool_call` event → Lucide `Zap` flash in output panel + Logs node pulse
- [x] SSE `tool_result` event → result appended to tool section in output
- [x] SSE `ask_user` event → amber card in output panel
- [x] SSE `confirm_write_memory` event → green card in output + Memory node pulse
- [x] SSE `proactive` event → Insight ghost card appears above Input
- [x] SSE `done` event → all nodes → done state; `last_session` updates Session node; telemetry displayed
- [x] SSE `error` event → Session node → error state (red border + shake)
- [x] Node activation sequence driven by real events (not setTimeout mock)

#### 5D — Wire → API params
- [x] File → Session wire: adds `file_ids: list[str]` to ChatRequest — files are global, recalled when prompted; backend merges with conversation-attached files; requires new `file_ids` field in `api/chat/schemas.py`
- [x] Input → Session wire: routes the message to that session's conversation (drawer follows it)
- [x] Memory → Session wire: **visual indicator only** — memory is always-on, no toggle, no API param; wire just shows the persistent memory connection

#### 5E — Auth
- [x] Login gate before boot: `nim_token` in localStorage (existing auth flow)
- [x] If no token: show minimal login form (Chakra Petch, ULTRAKILL style) before boot
- [x] On login success: boot sequence plays, then canvas

---

## Notes for Claude Code
- Do not edit: `.env`, `.env.example`, root `CLAUDE.md`, `ROADMAP.md`
- New frontend code goes in `frontend/src/` following existing patterns (hooks, components)
- React Flow: use community version (`@xyflow/react`) — MIT licensed
- All API calls use `/api/` prefix (Vite proxy → port 8000)
- Auth: read `nim_token` from localStorage, pass as `Authorization: Bearer {token}`
- Do not break existing `Chat/index.jsx` and sub-components — new canvas lives alongside, toggled by route or phase
- Add `psutil` and `pynvml` to `backend/requirements.txt` or equivalent

---

*Last updated: planning phase complete. Stage 1 ready to build.*

---

## Post-Stage-5 Enhancements

### Smart Handle Routing (2026-06-01)
- `AllHandles()` expanded to 8 ports (full compass: top/right/bot/left × source/target)
- `pickHandles()` scores all 16 combinations; penalises occupied handles at 80px equivalent
- Applied at: initial edge stamp (`SMART_INITIAL_EDGES`), `onConnect`, memory branch expansion

### Real-time Drag Re-routing (2026-06-01)
- Edges auto-reroute to closest handle while node is dragged
- RAF-throttled (≤60fps); `nodesRef` ref avoids stale closure; `setEdges` skipped if no handle changed
