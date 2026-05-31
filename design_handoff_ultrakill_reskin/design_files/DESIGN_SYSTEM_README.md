# NIM // SYSTEM TERMINAL — Design System

> An **ULTRAKILL-modded** re-skin of the **NIM AI Gateway** web app. The underlying product
> (a personal AI workspace that routes/orchestrates multiple models) is reverse-engineered from
> the **`ymr-gif/ai-workspace`** repo; the *visual language* here is a deliberate creative mod:
> a stark white-on-black, ULTRAKILL-red, pixel-CRT "machine diagnostics terminal."

This system lets design agents produce on-brand NIM interfaces, mocks, slides and prototypes in
the modded aesthetic.

---

## 1. Product Context

**NIM AI Gateway** is the web UI of a *personal AI workspace that routes and orchestrates
multiple language models through one unified API*. You boot the terminal, start a session, and the
gateway either auto-routes your prompt to the best model or runs it across several at once.

It is a single product — a **React + Vite single-page chat application**. The re-skin leans into
the fact that **NIM is literally a CPU**: it routes *instructions* to execution units, so the whole
interface is dressed as a retro 8-bit processor's diagnostics console (boot POST → main menu →
terminal), with a faint CPU block-diagram (Accumulator / ALU / Program Counter / Flags…) as
wallpaper behind everything.

### What it does
- **Multi-model routing** — `Auto`, `LLaMA 8B`, `DeepSeek`, `70B`; or **Compare** runs one prompt
  across all three. Models: `LLaMA 3.1 8B` (*fast*), `DeepSeek V4` (*code*), `LLaMA 3.3 70B`
  (*reasoning*).
- **Streaming chat** with a blinking block cursor, then re-rendered Markdown.
- **Per-answer telemetry** — `{tokens} tok · $cost · [query_type] · N src`.
- **Memory** — sectioned, persistent memory of the user (USER / STACK / PROJECT / GOALS…) with
  View / Edit / History / Graph tabs.
- **Files & Knowledge**, **Workspaces**, **Tool-call log**, **Usage/cost**, **Insights** — all
  right-edge slide-in panels.

### Source
- **`ymr-gif/ai-workspace`** — https://github.com/ymr-gif/ai-workspace
  - Frontend under `frontend/` (imported here into `reference/`). The whole original visual
    language lived in `frontend/src/lib/chatStyles.js`; the component vocabulary is in
    `frontend/src/components/chat/*.jsx`.
  - The backend (FastAPI) is out of scope.

> **Readers with repo access** should explore `frontend/src/components/chat/` to see the real
> feature surface this mod dresses up. The *structure* (sidebar, panels, telemetry, memory) is
> faithful to the source; only the *skin* is ULTRAKILL.

---

## 2. Content Fundamentals — voice & copy

The mod speaks like a **machine boot log talking to its operator**: terse, ALL-CAPS for chrome,
technical, zero marketing. The original product's engineer-to-engineer terseness is preserved and
pushed further into "system terminal" register.

- **Brand name:** **"NIM // SYSTEM TERMINAL"** (boot/menu); **"NIM // GATEWAY"** (chat header);
  the wordmark is just **"NIM"**. Models keep real names (`LLaMA 3.1 8B`, `DeepSeek V4`, `70B`).
- **Casing:** chrome (buttons, labels, menus, tabs, headings) is **ALL-CAPS Silkscreen**
  (`NEW SESSION`, `COMPARE`, `MEMORY CORE`, `DIAGNOSTICS`, `STANDBY`). Body, chat and data are
  sentence/normal case in VT323.
- **Boot/menu tone:** diagnostic. `> POST … OK`, `MODEL BUS [LLAMA · DEEPSEEK · 70B] … ONLINE`,
  `ALL SYSTEMS NOMINAL.`, `STANDBY — PRESS [ENTER] TO WAKE`, `● LINK ONLINE`, `OPERATOR: YUSUF`.
- **Menu wording** maps NIM actions to a game main menu: `NEW SESSION` · `RESUME` · `MEMORY CORE`
  · `DIAGNOSTICS` · `CONFIG` (shown disabled/`OFFLINE` to demo the state) · `DISCONNECT`.
- **Placeholders** stay lowercase & conversational: `Ask anything…`, `Search conversations…`,
  `https://… ingest URL`.
- **Numbers everywhere, earned:** token counts, `$0.00042` (5 decimals), salience, `· 3 src`.
- **Status tags** are ALL-CAPS Silkscreen in a bordered chip: `READY` / `PROCESSING` / `FAILED`,
  `NEEDS CLARIFICATION`, `MEMORY SUGGESTION`, `[USER]` `[STACK]`.
- **Tone:** calm, mechanical, confident. No exclamation, no jokes, no fluff.

### Emoji & glyphs are the icon system (unchanged from source)
NIM uses **emoji + unicode glyphs inline as its entire icon set** — `📎 ⚙ 🔧 💡 $ ◉ ○ ✦ ⚠️ ✓ ✕
🔒 ⊘ ⊞ 📄 👁 ⬇ ⬆ 🗑 ✎ ↺`. One glyph per control, before the label, inheriting its color. Kept as-is
in the mod (they read fine on black). See Iconography.

---

## 3. Visual Foundations

### Color & vibe
A **stark CRT console**. Pure black `#000` canvas, near-black `#0a0a0a` panels, `#050505` insets.
The **only brand accent is ULTRAKILL red `#ff2222`** — primary actions, the user's chat bubble,
selection, active pills/tabs, panel left-edges, and the wordmark's pixel-extrude. Everything else
is a **5-step white→gray ink ramp** (`#ffffff → #383838`). Semantic colors are **arcade-CRT
saturated, distinct but in-theme**: **amber `#ffb000`** (warning/processing), **phosphor green
`#3dff6e`** (ready/success/online), **cyan `#27d8ff`** (info/links/memory). No pastels. See
`colors_and_type.css`.

### Typography
Two pixel fonts (Google Fonts): **Silkscreen** (chunky) for the wordmark, labels, buttons, menus,
tabs and headings — used small & letter-spaced because it's heavy; and **VT323** (readable pixel
terminal) for body, chat, code, and dense data. No other families. Weights 400/700.
`text-rendering` is left crisp (`-webkit-font-smoothing: none`) to keep the pixels sharp.

### Geometry, borders, corners
**Zero border-radius — everything is a hard rectangle.** Borders are crisp 1px (`#262626` quiet,
`#4a4a4a` visible) or 2px for emphasis (red). Pills are rectangles, not capsules.

### Cards & elevation
Cards are **flat**: surface fill + 1px border, often a 2px accent edge (left border on rows/panels,
top border on compare cards). **No soft drop shadows** — elevation is a **hard pixel shadow**
(`4px 4px 0` black or red) on the primary button and user bubble. Slide-in panels sit over a
`rgba(0,0,0,0.78)` scrim and carry a **2px red left edge**. Tinted cards use an `rgba(accent,0.08)`
fill + `rgba(accent,0.40)` border.

### The CRT layer (`effects.css`)
Full CRT treatment, composited as fixed overlays above content: **horizontal scanlines** (with a
fast micro-flicker), a faint **vertical RGB phosphor grille**, a **bright beam** sweeping down every
7s, and a **vignette** with screen-curvature shade. Big text (the wordmark, titles) gets a
**chromatic-aberration** RGB channel split (`.crt-aberrate`); an optional `.crt-glitch` jitter and a
disabled-by-default whole-screen flicker are also provided.

### The CPU wallpaper (`assets/cpu-schematic.svg`)
A faint gray 8-bit CPU block diagram — Clock, Program Counter, MAR, RAM, Instruction Register,
Control Unit, Accumulator, ALU, B Register, Flags flip-flop, Output Register, joined by the W BUS —
sits behind every surface at ~0.7 opacity. Panels use translucent black fills so it shows through.

### Motion
Snappy and mechanical. Panels **slam** in via `translateX` over `0.18s cubic-bezier(.2,.9,.1,1)`;
pills transition `all 0.08s`; **states snap (color change), they don't fade or shrink**. Animations:
`blink` (block cursor), `pulse` (memory dot), `memFlash` (green flash on memory change), plus the
CRT keyframes (scanline flicker, beam sweep), and the **typewriter boot** reveal.

### States
- **Active/selected:** invert or accent-fill — active model pill goes solid red with black text;
  toggled header buttons switch text+border to their semantic color (green Usage/Ctx, cyan
  Log/Insights, amber Files-with-attachments); selected conversation gets a red left edge + raised
  fill; menu selection gets a red `>` caret + glow.
- **Focus:** inputs border to red `#ff2222` + a 1px red ring.
- **Disabled:** drops to `#383838` (e.g. the `CONFIG · offline` menu item).
- **No opacity-dim or press-shrink conventions** — state is communicated by **color**.

### Layout rules
Three-zone chat shell: **fixed 250px left sidebar** · flexible center terminal (header → feed →
toolbar → input) · **right-edge slide-in panels** (one at a time, over scrim). Boot and menu are
full-viewport. App is `height:100vh; overflow:hidden`; panels scroll internally.

---

## 4. Iconography

**No icon font, no SVG set, no raster icons** — the icon system is **emoji + unicode glyphs
rendered inline as text** (unchanged from the source product, and kept because they read well on
black). Reproduce the exact glyphs rather than substituting a stroke-icon library.

| Glyph | Meaning | | Glyph | Meaning |
|---|---|---|---|---|
| `📎` | Files | | `✦` | Last-session recap |
| `⚙` | Settings / params | | `⚠️` | Needs clarification |
| `🔧` | Tool-call log | | `✓ / ✕` | Accept / dismiss · close |
| `💡` | Insights | | `🔒` | Locked model |
| `$` | Usage / cost | | `⊘` | Memory disabled |
| `◉ / ○` | Context on / off | | `⊞` | Compare mode |
| `📄` | File chip | | `👁 ⬇ ⬆ 🗑 ✎` | View · dl · upload · del · rename |

Plus the **box-drawing characters** `─ ▄ █ ▀ ▌` used for the boot rule lines and the placeholder
mech ASCII, and `>` as the menu selection caret. One glyph per control, inheriting its color, never
decorative.

> If a future surface genuinely needs vector icons, the closest match to this flat single-weight
> feel is a thin-stroke set like **Lucide** — but that is a **substitution** outside the documented
> system and should be flagged.

---

## 5. Brand / Logo

The brand is a **pure pixel wordmark**: **"NIM"** in **Silkscreen 700**, white face with a
**red pixel-extrude** drop (stacked `text-shadow` → `#ff2222` then `#b81818` then black), set on
black with a chromatic-aberration fringe. Subtitle: **"AI GATEWAY · ROUTING TERMINAL"** in
letter-spaced Silkscreen. No icon mark or monogram. See `preview/b-wordmark.html`.

The **UNIT slot** (`MechSlot`) is the brand's flexible art frame: a bordered panel with corner
registration ticks and a status line, holding a sprite / image / ASCII figure. It ships with
placeholder ASCII — drop in your own mech art.

---

## 6. Index — files in this system

| Path | What it is |
|------|------------|
| `README.md` | This file. |
| `colors_and_type.css` | All color + type tokens (CSS vars) and semantic type/utility classes. |
| `effects.css` | The CRT overlay stack (scanlines, grille, beam, vignette, aberration, glitch). |
| `assets/cpu-schematic.svg` | The faint 8-bit CPU block-diagram wallpaper. |
| `SKILL.md` | Agent-Skill front-matter so this system is usable in Claude Code. |
| `preview/` | 21 specimen cards powering the Design System tab. |
| `ui_kits/nim-gateway/` | Interactive, pixel-faithful recreation of the modded NIM app. |
| `reference/` | The imported upstream frontend source (read-only; the structural truth). |

### UI kit
- **`ui_kits/nim-gateway/`** — boot diagnostics → main menu (wordmark + UNIT slot) → chat terminal
  (sidebar, streaming feed, compare, telemetry, Memory / Files / Usage / Log / Insights panels),
  full CRT + CPU wallpaper. See its own `README.md`.

### Fonts
Silkscreen + VT323 load from **Google Fonts** (CDN). They are an intentional creative choice for
the mod (the original product used `system-ui`). If you want them self-hosted, or want to swap
either face, say so and I'll wire it up.

> No slide template, deck, or marketing material exists in the source, so `slides/` is intentionally
> absent.
