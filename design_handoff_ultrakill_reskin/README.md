# Handoff: NIM // SYSTEM TERMINAL — ULTRAKILL Re-skin

## Overview
This package re-skins the **NIM AI Gateway** frontend (`ymr-gif/ai-workspace`, the `frontend/`
React + Vite app) into an **ULTRAKILL-styled machine-diagnostics terminal**: stark white-on-black,
a single ULTRAKILL-red accent, pixel fonts (Silkscreen + VT323), zero border-radius, hard edges, a
full CRT overlay (scanlines / beam / vignette / chromatic aberration), a faint 8-bit CPU
block-diagram wallpaper, and an optional **boot → main-menu → terminal** entry flow.

**Nothing about the app's features or structure changes** — only the skin. The original visual
language lived almost entirely in one file (`frontend/src/lib/chatStyles.js`), and this re-skin keeps
**the exact same style-object keys**, so the change is mostly a value swap plus a few support files.

## About the Design Files
The files in `design_files/` are **design references created in HTML**, not production code to ship
verbatim. In particular, `design_files/ui-kit-reference/` is a standalone demo built with plain
`<script>` globals and a toy markdown renderer. **Your task is to port these styles into the real
`frontend/` app**, which uses **ES modules** and **react-markdown** — i.e. take the *values, CSS, and
component structure* and apply them with the codebase's existing patterns. Do **not** replace the real
React components with the demo's globals-based ones.

Map of reference files → what to use them for:
| Reference file | Use it as the source of truth for |
|---|---|
| `design_files/colors_and_type.css` | All design tokens (colors, type, geometry, motion) as CSS vars. |
| `design_files/effects.css` | The CRT overlay stack — copy into the app as-is. |
| `design_files/assets/cpu-schematic.svg` | The CPU wallpaper — copy into the app as-is. |
| `design_files/ui-kit-reference/styles.js` | The re-skinned **`chatStyles.js`** token object (identical keys to the original). |
| `design_files/ui-kit-reference/screens.jsx` | The new **BootScreen / MainMenu / MechSlot** components to port to ES modules. |
| `design_files/ui-kit-reference/index.html` | The global CSS (markdown body, scrollbars, keyframes), CRT/wallpaper node setup, and font links. |
| `design_files/ui-kit-reference/components.jsx`, `feed.jsx`, `panels.jsx`, `app.jsx` | Reference for the per-component color/style edits + the boot/menu phase wiring. |

## Fidelity
**High-fidelity (hifi).** Exact colors, fonts, sizes, borders, and interactions are specified below
and in the reference files. Recreate them precisely using the app's existing components.

---

## Implementation — step by step

### STEP 0 — Fonts
Add to `frontend/index.html` `<head>` (or self-host the two families and `@font-face` them):
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&family=VT323&display=swap" rel="stylesheet">
```
- **Silkscreen** (400/700) → all chrome: wordmark, labels, buttons, menu items, tabs, headings, badges, status chips. It is heavy — always use it **small and letter-spaced, usually UPPERCASE**.
- **VT323** (400) → all body/readable text: chat messages, markdown, code, file names, key/value data, meta lines, inputs.
- **Important:** VT323's glyph metrics render ~20–25% smaller than a normal sans at the same `px`, which is why every body size below is **bumped up** relative to the original. Keep `-webkit-font-smoothing: none; font-smooth: never;` on `body` so the pixels stay crisp.

### STEP 1 — Swap the token object (`frontend/src/lib/chatStyles.js`)
This is the bulk of the re-skin. Open `design_files/ui-kit-reference/styles.js`, copy the **`const s = { … }`** object's values into your `chatStyles.js`, **keeping your file's `export default s`** (delete the demo's `window.NIM_S = s` / `window.NIM_C = …` lines — but DO re-export the raw constants too; see below). Keys are identical to the original, so every component that reads `s.foo` keeps working.

At the top of `styles.js`, the demo defines reusable constants — keep these and **export them** so components can reference the palette directly:
```js
export const DISP = "'Silkscreen', monospace";   // chrome / labels
export const TERM = "'VT323', monospace";          // body / data
export const RED='#ff2222', REDDIM='#b81818', GRN='#3dff6e', AMB='#ffb000', CYN='#27d8ff';
export const VOID='#000', PANEL='#0a0a0a', INSET='#050505';
export const FG1='#fff', FG2='#c8c8c8', FG3='#8f8f8f', FG4='#5a5a5a', FG5='#383838';
export const LINE='#262626', LINE2='#4a4a4a';
```
> Note: in the demo, `s.root` has `background:'transparent'` (so the CPU wallpaper shows through). If your real app's root is the only full-screen element, set it to `background:'transparent'` and put the wallpaper behind it (Step 4). Panels/header/sidebar/toolbar/input use `rgba(0,0,0,0.55)` fills on purpose — keep that so the schematic shows faintly through.

### STEP 2 — Replace per-component hardcoded colors
Some colors live **inside components/constants**, not in `chatStyles.js`. Apply this exact mapping wherever these hexes appear in `frontend/src/`:

| Old (source) | New | Role |
|---|---|---|
| `#6366f1` (indigo-500) | `#ff2222` | primary action / user bubble / active / selection |
| `#818cf8` (indigo-400) | `#27d8ff` | secondary accent / links / memory dot / tool-log names |
| `#4338ca` / `#312e81` / `#1e1b4b` | `#27d8ff` / `rgba(39,216,255,.5)` / `rgba(39,216,255,.08)` | indigo borders/fills → cyan |
| `#34d399` / `#10b981` / `#6ee7b7` | `#3dff6e` | success / ready / sources≥3 / accept / context-ON |
| `#1e4e3a` / `#0f4c3a` | `rgba(61,255,110,.5)` / `rgba(61,255,110,.08)` | green borders/fills |
| `#fbbf24` / `#f59e0b` / `#fde68a` | `#ffb000` / `#ffd98a` | warning / processing / attached-files / ask_user |
| `#78350f` | `rgba(255,176,0,.5)` | amber border |
| `#38bdf8` (sky) | `#27d8ff` | info |
| `#f87171` / `#ef4444` / `#fca5a5` | `#ff5a5a` / `#ff2222` / `#ff7a7a` | error / delete / error-bubble text |
| `#f1f5f9` | `#ffffff` | primary text |
| `#e2e8f0` / `#cbd5e1` | `#c8c8c8` | body / values |
| `#94a3b8` | `#8f8f8f` | secondary / idle labels |
| `#64748b` / `#475569` | `#5a5a5a` | meta / placeholders |
| `#334155` | `#4a4a4a` (border) **or** `#383838` (faint text) — pick by context | visible borders / disabled |
| `#0f172a` | `#000000` | app bg / inputs |
| `#1e293b` | `#0a0a0a` (surface) **or** `#262626` (hairline border) — pick by context | surfaces vs dividers |
| `#0a1220` | `#050505` | deep insets / fields / code |

> ⚠️ **Two ambiguous tokens.** `#1e293b` was used in the source for *both* surfaces and borders, and `#334155` for *both* borders and disabled text. After swapping `chatStyles.js` wholesale (where the demo already disambiguates them), **audit any remaining `#1e293b`/`#334155` in components** and choose surface (`#0a0a0a`) vs border (`#262626`) / border (`#4a4a4a`) vs faint-text (`#383838`) by how each is used. All the *accent* hexes above are unambiguous and safe to global-replace.

**Known specific spots to hit** (from the source structure):
- `frontend/src/lib/chatConstants.js` — the memory **section colors**. Set: `USER → #27d8ff`, `STACK → #3dff6e`, `PROJECT → #ffb000`, `GOALS → #ff2222` (and any others to a value from the palette). Memory section labels should render as a **bordered chip**: `border: 1px solid currentColor; border-radius: 0; padding: 0.2rem 0.45rem; font-family: Silkscreen; font-size: 10px; text-transform: uppercase`.
- Header toggle buttons (in your `Chat.jsx` / header): Context-ON and `$ Usage` → green `#3dff6e` (border `rgba(61,255,110,.5)`); `🔧 Log` and `💡 Insights` → cyan `#27d8ff` (border `rgba(39,216,255,.5)`); `📎 Files` when attachments exist → amber `#ffb000` (border `rgba(255,176,0,.5)`).
- `MessageList.jsx` src-count: `≥3 → #3dff6e`, `1–2 → #ffb000`. Query-type tag `[factual]` → `#5a5a5a`, VT323, UPPERCASE.
- Selected conversation row: background `#121212` + **`border-left: 2px solid #ff2222`** (replaces the old fill-only highlight). Set `convItem` base `border-left: 2px solid transparent`.

### STEP 3 — Markdown styles (`frontend/src/components/Chat.jsx` `<style>` block)
Replace the `.md-body` rules wholesale with these (already themed):
```css
.md-body { font-family:'VT323',monospace; font-size:18px; line-height:1.35; color:#c8c8c8; word-break:break-word; }
.md-body p { margin:0 0 0.55em; } .md-body p:last-child { margin-bottom:0; }
.md-body h1,.md-body h2,.md-body h3,.md-body h4 { margin:0.7em 0 0.3em; font-weight:700; line-height:1.2; color:#fff; }
.md-body h1{font-size:1.3em} .md-body h2{font-size:1.18em} .md-body h3{font-size:1.05em}
.md-body ul,.md-body ol { margin:0.35em 0 0.55em 1.3em; padding:0; }
.md-body li { margin-bottom:0.15em; } .md-body li::marker { color:#ff2222; }
.md-body code { background:#050505; border:1px solid #262626; padding:0 0.35em; font-family:'VT323',monospace; font-size:0.95em; color:#27d8ff; }
.md-body pre { background:#000; border:1px solid #262626; border-left:2px solid #4a4a4a; padding:0.6em 0.9em; overflow-x:auto; margin:0.5em 0; }
.md-body pre code { background:none; border:none; padding:0; color:#8f8f8f; }
.md-body blockquote { border-left:2px solid #ff2222; margin:0.5em 0; padding:0.1em 0.7em; color:#8f8f8f; }
.md-body a { color:#27d8ff; text-decoration:underline; }
.md-body strong { color:#fff; font-weight:700; } .md-body em { color:#c8c8c8; }
.md-body hr { border:none; border-top:1px solid #262626; margin:0.7em 0; }
```

### STEP 4 — CPU wallpaper + CRT overlay
1. Copy `design_files/assets/cpu-schematic.svg` → `frontend/public/cpu-schematic.svg` (or `src/assets/`).
2. Copy `design_files/effects.css` → `frontend/src/` and `import './effects.css'` in your root (`main.jsx`/`App.jsx`). Also add (global CSS):
   ```css
   .cpu-bg { position:fixed; inset:0; z-index:0; pointer-events:none;
     background:#000 url('/cpu-schematic.svg') center/cover no-repeat; opacity:0.7; }
   #root { position:relative; z-index:1; height:100%; }  /* root must be transparent (Step 1) */
   ```
3. Render these nodes **once at the app root** — `.cpu-bg` BEFORE your app tree, the four `crt-*` overlays AFTER it (and put `class="crt"` on `<html>`/`<body>`):
   ```html
   <div class="cpu-bg"></div>
   <!-- app here -->
   <div class="crt-grille"></div>
   <div class="crt-scanlines"></div>
   <div class="crt-beam"></div>
   <div class="crt-vignette"></div>
   ```
   In React, render the overlay `<div>`s as siblings of your app inside the root component. They're `position:fixed; pointer-events:none`, so they never block clicks.
4. Also bring over the **global CSS** from `ui-kit-reference/index.html`'s `<style>`: the `blink`/`pulse`/`memFlash` keyframes, the thin pixel `::-webkit-scrollbar` rules, `input:focus{ border-color:#ff2222; box-shadow:0 0 0 1px rgba(255,34,34,.4) }`, `input[type=range]{accent-color:#ff2222}`, `input[type=checkbox]{accent-color:#ff2222}`, and `::selection{ background:#ff2222; color:#000 }`.

### STEP 5 (optional) — Boot → Menu entry flow
The original app goes login → Chat. To add the full experience, port `design_files/ui-kit-reference/screens.jsx` (`BootScreen`, `MainMenu`, `MechSlot`) to ES-module React components and gate the app behind a `phase` state. See **State Management** and **Screens** below. This is additive — skip it and the chat terminal still looks fully re-skinned.

---

## Screens / Views

### A. Boot (new, optional) — `BootScreen`
- **Purpose:** retro POST/diagnostics splash; sets the tone, then user wakes into the menu.
- **Layout:** full viewport, `padding: 8vh 8vw`, left-aligned, transparent bg (wallpaper shows).
- **Content/behavior:** header `NIM // SYSTEM TERMINAL` (Silkscreen 18px, white, `text-shadow:2px 2px 0 #b81818`) + `BIOS REV 1.0 — CENTRAL PROCESSING GATEWAY` (Silkscreen 9px, `#5a5a5a`, letter-spacing .2em) + a `─`×48 rule (`#383838`). Then **10 diagnostic lines type out character-by-character** (`~14ms/char`, `70ms` pause between lines), each `> LABEL ……… STATUS` where dots fill to ~40 cols and STATUS is colored: `OK`/`ONLINE` green `#3dff6e`, `MOUNTED` cyan `#27d8ff`, `READY` amber `#ffb000`, each with a matching `text-shadow` glow. The currently-typing line ends with a red block cursor (`0.55em×1em`, `#ff2222`, `box-shadow:0 0 6px #ff2222`, `blink 1s step-end`). When done: a `─` rule, `ALL SYSTEMS NOMINAL.` (green 20px, glow), and a blinking `STANDBY — PRESS [ENTER] TO WAKE` (Silkscreen 12px; `[ENTER]` in red). **Enter, Space, or click → menu.**
- The 10 lines (label → status): `POWER-ON SELF TEST→OK`, `CLOCK φ @ 4.77 MHZ→OK`, `ACCUMULATOR / ALU→OK`, `PROGRAM COUNTER→OK`, `RANDOM ACCESS MEM 16 x 8→OK`, `INSTRUCTION REGISTER→OK`, `MODEL BUS [LLAMA · DEEPSEEK · 70B]→ONLINE`, `MEMORY CORE / CONTEXT→MOUNTED`, `FLAG FLIP-FLOP CF · ZF→OK`, `ROUTING SEQUENCER→READY`.

### B. Main menu (new, optional) — `MainMenu`
- **Layout:** full viewport. Top strip: `NIM // SYSTEM TERMINAL` (left) · `● LINK ONLINE` (right, green, glow), `1px #262626` bottom border. Center row (`padding:0 6vw`, space-between): **left** = wordmark + menu; **right** = `MechSlot`. Bottom bar: `OPERATOR: YUSUF` · `[↑↓] SELECT [ENTER] CONFIRM` · `REV 1.0` (Silkscreen 9px `#5a5a5a`), `1px #262626` top border.
- **Wordmark:** `NIM`, Silkscreen 700, 72px, white face with stacked red pixel-extrude `text-shadow: 2px 0 #ff2222, 4px 0 #ff2222, 2px 2px #ff2222, 4px 4px #b81818, 6px 6px #b81818, 8px 8px #000`, plus `.crt-aberrate`. Subtitle `AI GATEWAY · ROUTING TERMINAL` (Silkscreen 13px, `#8f8f8f`, letter-spacing .22em).
- **Menu items** (Silkscreen 17px, letter-spacing .1em, UPPERCASE): each row is `> LABEL note`. Idle `#c8c8c8`; **selected** `#ff2222` + `text-shadow:0 0 10px #ff2222` and the `>` caret visible (caret hidden when not selected); disabled `#383838`, `cursor:not-allowed`. Items: `NEW SESSION` · `RESUME · <last session title>…` · `MEMORY CORE` · `DIAGNOSTICS` · `CONFIG · offline` (disabled) · `DISCONNECT`. Mouse hover selects; `↑/↓` cycle; `Enter`/click confirms (no-op on disabled).
- **Actions:** `NEW SESSION`→new conversation + enter app; `RESUME`→open last conversation + app; `MEMORY CORE`→app + open Memory panel; `DIAGNOSTICS`→app + open Usage panel; `DISCONNECT`→back to boot.

### C. Mech / UNIT slot (new) — `MechSlot`
- **Purpose:** flexible art frame on the menu for a sprite/image/ASCII figure.
- **Layout:** `width:320px; max-width:34vw; aspect-ratio:3/4; border:1px solid #4a4a4a; background:rgba(0,0,0,.5)`; **red 2px L-shaped registration ticks** at all four corners (10px). Header row: `UNIT 01` (left, Silkscreen 9px `#8f8f8f`) · `STANDBY` (right, Silkscreen 9px amber `#ffb000`, glow), `1px #262626` divider. Body: centered, `overflow:hidden`. Footer: caption (VT323 13px `#383838`), `1px #262626` top divider.
- **Props:** `src` (image → `max-width/height:100%; image-rendering:pixelated`, footer `SIGNAL LOCKED`), or `ascii` (VT323 15px `#8f8f8f`, `white-space:pre`, faint white glow), or **neither** → default placeholder ASCII + footer `PLACEHOLDER · DROP SPRITE / IMG / ASCII`. **Action item for the dev/user:** supply a real mech sprite via `src`.

### D. Chat terminal (re-skinned existing app)
This is the original three-zone shell, restyled. **All of this is driven by the swapped `chatStyles.js`** plus the per-component color edits in Step 2. Zones:
- **Sidebar** (250px, `border-right:1px #262626`, `rgba(0,0,0,.55)` fill): `+ NEW SESSION` primary button (red fill `#ff2222`, black text, Silkscreen 11px UPPERCASE), workspace pills (square; active = red text/border + `rgba(255,34,34,.1)` fill), search input, conversation list (selected = `#121212` + red left edge; date line Silkscreen 9px; `🔒`/`⊘` glyphs).
- **Header** (`rgba(0,0,0,.55)`, `border-bottom:1px #262626`): wordmark `NIM // GATEWAY` (Silkscreen 15px, `text-shadow:2px 2px 0 #b81818`) + toggle buttons (Silkscreen 9px UPPERCASE, `1px #4a4a4a` border, semantic colors when active per Step 2) + `◄ EXIT` (returns to menu, if Step 5 used). Memory button has a cyan `7px` square dot.
- **Feed:** message bubbles — **user = red `#ff2222` fill, black text, `box-shadow:3px 3px 0 #b81818`**, right-aligned; **AI = `#0a0a0a` + `1px #262626` + `2px #4a4a4a` left border**, VT323 18px `#c8c8c8`, model tag (VT323 14px `#5a5a5a`) + token meta + `[query_type]` + `· N src`; **error = `#0a0a0a` + `1px #ff2222`, `#ff7a7a` text**. Streaming uses the red block cursor. Compare mode = 3 cards (`#0a0a0a`, `2px #4a4a4a` top border) side by side. Proactive card = cyan-tinted; ask_user = amber-tinted; memory-suggestion = green-tinted (all `rgba(accent,.08)` fill + `rgba(accent,.4)` border, square, Silkscreen label).
- **Toolbar:** model pills (square; active = solid red, black text; Compare = green-tinted/green border/green text+glow); `⚙` params expander with 3 sliders (`accent-color:#ff2222`, labels Silkscreen 9px). Attached-file chips above input (cyan text, `📄 name ✕`).
- **Input bar:** text input (`#000`, `1px #4a4a4a`, VT323 20px, focus→red border+ring) + `SEND` button (red fill, black text, Silkscreen 11px).
- **Slide-in panels** (Memory / Files / Usage / Tool Log / Insights): right-edge, `#070707` fill, **`border-left:2px solid #ff2222`**, slide via `transform: translateX()` over `0.18s cubic-bezier(.2,.9,.1,1)`, above a `rgba(0,0,0,.78)` scrim. Tabs = Silkscreen 9px, active = red text + red bottom border. Memory sections = bordered chips in their section color. Status badges = bordered Silkscreen chips (READY green / PROCESSING amber / FAILED red).

---

## Interactions & Behavior
- **Navigation:** boot→menu (Enter/Space/click); menu→app (Enter/click on an enabled item; ↑/↓ to select); app→menu (`◄ EXIT`); menu `DISCONNECT`→boot.
- **Streaming:** user message appends instantly; AI reply streams in (block cursor), then re-renders as markdown and reveals telemetry. Compare streams three columns with staggered completion.
- **Panels:** open one at a time (opening one closes others); scrim click closes. Slam-in `0.18s`.
- **State changes SNAP via color — never fade or shrink.** No opacity-dim hover, no press-scale. Pills/buttons transition `all 0.08s` (color/border only).
- **Focus:** inputs/textarea → red border + `0 0 0 1px rgba(255,34,34,.4)` ring.
- **Animations:** `blink` (cursor, 1s step-end), `pulse` (memory-updating dot), `memFlash` (1.5s green→transparent on memory change), CRT `crt-flicker` (scanlines, 90ms steps), `crt-sweep` (beam, 7s linear), typewriter boot reveal. `prefers-reduced-motion` disables beam/flicker (keeps static scanlines) — already in `effects.css`.

## State Management
Existing chat state is unchanged. **New (only if doing Step 5):**
- `phase: 'boot' | 'menu' | 'app'` (start `'boot'`). Render `<BootScreen onWake={()=>setPhase('menu')} />`, `<MainMenu items=… onSelect=… />`, or the chat shell accordingly.
- `BootScreen` internal: committed lines array, current partial line, line index, `finished` flag (drives the typewriter + the Enter listener).
- `MainMenu` internal: `sel` index (keyboard/hover); `onSelect(id)` dispatches to existing handlers (new conversation / select conversation / open panel) + `setPhase('app')`.
- The menu's color/disabled state is data-driven via an `items` array (`{id,label,note?,disabled?}`).

## Design Tokens (complete)
**Surfaces:** void `#000` · panel `#0a0a0a` · inset `#050505` · raise `#121212` · scrim `rgba(0,0,0,.78)` · translucent panel fill `rgba(0,0,0,.55)`.
**Ink:** `#ffffff` `#c8c8c8` `#8f8f8f` `#5a5a5a` `#383838`.
**Lines:** quiet `#262626` · visible `#4a4a4a` · emphasis `#ffffff`.
**Red (accent):** `#ff2222` · dim `#b81818` · bright `#ff5a5a` · glow `rgba(255,34,34,.55)` · soft fill `rgba(255,34,34,.10)` · soft border `rgba(255,34,34,.40)`.
**Semantic:** amber `#ffb000` · green `#3dff6e` · cyan `#27d8ff` (each with `rgba(x,.08/.10)` fills and `rgba(x,.40/.50)` borders).
**Glows:** white `0 0 6px rgba(255,255,255,.35)` · red `0 0 8px rgba(255,34,34,.55)` · green `0 0 8px rgba(61,255,110,.5)`.
**Type:** display `'Silkscreen',monospace` (400/700) · terminal `'VT323',monospace` (400). Display sizes: wordmark 64–72px, title 28px, heading 16px, button/menu 11–17px, label 9–10px, micro 8px. Terminal sizes: panel title 22px, input 20px, body/chat 18px, small 16px, meta 14px, micro 13px. Letter-spacing: labels .1–.12em, dividers .2–.22em. Line-height: body 1.35, headings 1.2.
**Geometry:** `border-radius: 0` everywhere. Borders 1px (quiet/visible) or 2px (emphasis/accent edges).
**Elevation:** no soft shadows. Hard pixel shadow `3–4px 3–4px 0 <#000 or #b81818>` (primary button, user bubble). Panel scrim `rgba(0,0,0,.78)`.
**Motion:** panel `transform .18s cubic-bezier(.2,.9,.1,1)`; pills/buttons `all .08s`; cursor `blink 1s step-end`; beam `crt-sweep 7s linear`.

## Assets
- `assets/cpu-schematic.svg` — original to this design (diagrammatic 8-bit CPU block diagram; no third-party rights). Ship it.
- **Fonts:** Silkscreen + VT323 — Google Fonts (Open Font License); CDN link above, or self-host.
- **Icons:** none to bundle — the icon system is **inline emoji + unicode glyphs** (`📎 ⚙ 🔧 💡 $ ◉ ○ ✦ ⚠️ ✓ ✕ 🔒 ⊘ ⊞ 📄 👁 ⬇ ⬆ 🗑 ✎ ↺`) plus box-drawing chars (`─ ▄ █ ▀`) for boot rules and placeholder ASCII. Keep them; do not substitute an icon library.
- **Mech sprite:** NOT included — `MechSlot` ships placeholder ASCII. Supply a real pixel sprite via `src` to finish the menu.

## Files in this bundle
- `design_files/colors_and_type.css` — token source of truth (CSS vars + utility classes).
- `design_files/effects.css` — CRT overlay (copy as-is).
- `design_files/assets/cpu-schematic.svg` — wallpaper (copy as-is).
- `design_files/ui-kit-reference/` — the full standalone reference implementation (`styles.js`=new chatStyles values, `screens.jsx`=boot/menu/mech, `index.html`=global CSS + node setup, plus `components.jsx`/`feed.jsx`/`panels.jsx`/`app.jsx` for styling reference and the boot/menu wiring, and its own `README.md`).
- `design_files/DESIGN_SYSTEM_README.md` — the full written design system (voice, foundations, iconography).
- `design_files/SKILL.md` — one-line aesthetic summary + token pointers.

## Target repo paths (quick reference)
- Tokens: `frontend/src/lib/chatStyles.js` ← Step 1
- Constants/section colors: `frontend/src/lib/chatConstants.js` ← Step 2
- Markdown + root styles: `frontend/src/components/Chat.jsx` ← Step 3
- Per-component colors: `frontend/src/components/chat/*.jsx`, `frontend/src/components/*.jsx` ← Step 2
- Global CSS / fonts / CRT nodes: `frontend/index.html` + `frontend/src/main.jsx`/`App.jsx` ← Steps 0 & 4
- New screens: add `frontend/src/components/BootScreen.jsx`, `MainMenu.jsx`, `MechSlot.jsx` ← Step 5
