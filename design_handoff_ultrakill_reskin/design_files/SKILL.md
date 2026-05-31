---
name: nim-design
description: Use this skill to generate well-branded interfaces and assets for NIM // SYSTEM TERMINAL (an ULTRAKILL-modded re-skin of the NIM AI Gateway), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, CRT effects, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Key references in this skill:
- `README.md` — product context, content/voice rules, visual foundations, iconography, manifest.
- `colors_and_type.css` — all color + type tokens as CSS vars, plus semantic utility classes.
- `effects.css` — the CRT overlay stack (scanlines, grille, beam, vignette, aberration). Drop the four overlay nodes as the last children of `<body>` and add class `crt`.
- `assets/cpu-schematic.svg` — the faint 8-bit CPU block-diagram wallpaper (place behind content at ~0.7 opacity, use translucent black panel fills so it shows through).
- `ui_kits/nim-gateway/` — interactive, pixel-faithful recreation (boot → menu → terminal); `styles.js` there is the re-skinned token object to reuse.
- `preview/` — specimen cards for colors, type, spacing, components, and brand.

Core aesthetic in one line: an **ULTRAKILL-modded CRT system terminal** — pure black (`#000`) canvas, near-black panels, a single ULTRAKILL-red accent (`#ff2222`), a white→gray ink ramp, arcade-CRT semantics (amber/green/cyan), **zero border-radius**, hard 1–2px borders, hard pixel shadows (no soft blur), **Silkscreen** (chunky, for chrome/labels) + **VT323** (readable, for body), emoji-as-icons, a faint CPU block-diagram wallpaper, and a full CRT overlay (scanlines · beam · vignette · channel split). State changes snap via color, never fade or dim.

Fonts load from Google Fonts: `Silkscreen` (400/700) + `VT323`.
