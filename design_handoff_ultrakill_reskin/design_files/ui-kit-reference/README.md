# NIM // SYSTEM TERMINAL — UI Kit

A high-fidelity, interactive recreation of **NIM AI Gateway**, re-skinned as an **ULTRAKILL-style
machine-diagnostics terminal**. Structure is faithful to the upstream source
(`ymr-gif/ai-workspace`, `frontend/`); the skin is the mod. Logic is a self-contained demo (no
backend, fake streaming, seed data).

## Run it
Open `index.html`. The flow is **boot → menu → terminal**:
1. **Boot** — a typewriter POST/diagnostics log types itself out; press **[ENTER]** (or click) to wake.
2. **Main menu** — `↑/↓` to move, **[ENTER]** to confirm (or click). `NEW SESSION` / `RESUME` /
   `MEMORY CORE` / `DIAGNOSTICS` open the terminal; `CONFIG` is shown disabled; `DISCONNECT` reboots.
3. **Terminal** — the chat app. `◄ EXIT` (header) returns to the menu.

## What's interactive
- **Boot sequence & menu** — keyboard + mouse driven, with the UNIT (mech) slot.
- **Send a message** — your red bubble, then a **fake streaming** AI answer resolving to Markdown
  with telemetry (`tok · $cost · [query_type] · N src`).
- **Compare mode** (`⊞`) — three model cards stream side-by-side.
- **Model pills & params** — switch model; `⚙` expands temp / tokens / top-p sliders.
- **Header panels** — Memory (View/Edit/History/Graph, colored sections, context toggle), Files
  (Library/Attached, attach/detach), Usage, Tool Log, Insights — each slams in from the right edge
  over a scrim, with a red left border.
- **Sidebar** — switch sessions, filter by workspace, search, `+ NEW SESSION`.

## Files
| File | Role |
|------|------|
| `index.html` | Mounts React + Babel + fonts, global CSS (markdown, scrollbars, keyframes), CPU wallpaper + CRT overlay nodes, loads scripts. |
| `styles.js` | `window.NIM_S` token object (re-skinned) + `window.NIM_C` raw color/font constants. |
| `data.js` | `window.NIM_*` model constants + demo seed data. |
| `components.jsx` | Markdown renderer, `Sidebar`, `ChatHeader`. |
| `screens.jsx` | `BootScreen`, `MainMenu`, `MechSlot` (the boot/menu/art-slot flow; IIFE-wrapped). |
| `feed.jsx` | `MessageFeed` (bubbles, streaming, compare, telemetry, proactive), `ModelToolbar`, `ParamSlider`. |
| `panels.jsx` | `MemoryPanel`, `FilesPanel`. |
| `app.jsx` | `App` orchestrator (boot/menu/app phases) + `SidePanelStub` (Usage / Log / Insights). |

## Customising the mech / UNIT slot
`MechSlot` (in `screens.jsx`) is the flexible art frame. Pass one of:
```jsx
<MechSlot src="unit.png" />     // image / pixel sprite (rendered image-rendering: pixelated)
<MechSlot ascii={`...`} />      // your own ASCII art
<MechSlot />                    // default placeholder ASCII — swap it
```
It's used once on the main menu; drop in a real V1/mech sprite to finish the look.

## Shared foundations
The kit pulls the system's `../../colors_and_type.css` tokens conceptually via `styles.js`, and
loads `../../effects.css` (CRT) and `../../assets/cpu-schematic.svg` (wallpaper) from the design-
system root.

## Fidelity notes
- **Markdown** uses a ~20-line demo renderer; the `.md-body` CSS in `index.html` is the real theme.
- Backend, auth, SSE, persistence, and the Settings / Workspace / File-Viewer modals are **omitted**.
- Every component reads `window.NIM_S` / `window.NIM_C`, so the kit stays a faithful mirror of the tokens.
