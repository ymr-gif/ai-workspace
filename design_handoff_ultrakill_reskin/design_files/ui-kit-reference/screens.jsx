/* NIM // SYSTEM TERMINAL — boot + main-menu + mech-slot screens.
   Attaches to window: BootScreen, MainMenu, MechSlot. */
(function () {
const { RED, REDDIM, GRN, AMB, CYN, FG1, FG2, FG3, FG4, FG5, LINE, LINE2, DISP, TERM } = window.NIM_C;

/* ---------------------------------------------------------------- shared chrome */
const scr = {
  screen: { position:'absolute', inset:0, display:'flex', flexDirection:'column', color:FG1, fontFamily:TERM, overflow:'hidden' },
  tag:    { fontFamily:DISP, fontSize:'9px', letterSpacing:'0.2em', color:FG4, textTransform:'uppercase' },
};

/* ================================================================ BOOT */
const BOOT_LINES = [
  { t: 'POWER-ON SELF TEST', s: 'OK', c: GRN },
  { t: 'CLOCK  φ @ 4.77 MHZ', s: 'OK', c: GRN },
  { t: 'ACCUMULATOR / ALU', s: 'OK', c: GRN },
  { t: 'PROGRAM COUNTER', s: 'OK', c: GRN },
  { t: 'RANDOM ACCESS MEM  16 x 8', s: 'OK', c: GRN },
  { t: 'INSTRUCTION REGISTER', s: 'OK', c: GRN },
  { t: 'MODEL BUS  [LLAMA · DEEPSEEK · 70B]', s: 'ONLINE', c: GRN },
  { t: 'MEMORY CORE / CONTEXT', s: 'MOUNTED', c: CYN },
  { t: 'FLAG FLIP-FLOP  CF · ZF', s: 'OK', c: GRN },
  { t: 'ROUTING SEQUENCER', s: 'READY', c: AMB },
];

function BootScreen({ onWake }) {
  const [done, setDone] = React.useState([]);     // committed lines
  const [typed, setTyped] = React.useState('');   // current line label, partial
  const [idx, setIdx] = React.useState(0);
  const [finished, setFinished] = React.useState(false);

  React.useEffect(() => {
    if (idx >= BOOT_LINES.length) { setFinished(true); return; }
    const full = BOOT_LINES[idx].t;
    if (typed.length < full.length) {
      const id = setTimeout(() => setTyped(full.slice(0, typed.length + 1)), 14);
      return () => clearTimeout(id);
    }
    const id = setTimeout(() => {
      setDone(d => [...d, BOOT_LINES[idx]]);
      setTyped('');
      setIdx(i => i + 1);
    }, 70);
    return () => clearTimeout(id);
  }, [typed, idx]);

  React.useEffect(() => {
    if (!finished) return;
    const onKey = (e) => { if (e.key === 'Enter' || e.key === ' ') onWake(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [finished, onWake]);

  const dots = (t) => '.'.repeat(Math.max(3, 40 - t.length));

  return (
    <div style={{ ...scr.screen, padding:'8vh 8vw', cursor: finished ? 'pointer' : 'default' }} onClick={finished ? onWake : undefined}>
      <div style={{ marginBottom:'1.4rem' }}>
        <div style={{ fontFamily:DISP, fontSize:'18px', letterSpacing:'0.12em', color:FG1, textShadow:`2px 2px 0 ${REDDIM}` }}>NIM // SYSTEM TERMINAL</div>
        <div style={{ ...scr.tag, marginTop:'0.5rem' }}>BIOS REV 1.0 — CENTRAL PROCESSING GATEWAY</div>
        <div style={{ color:FG5, marginTop:'0.4rem', fontSize:'18px' }}>{'─'.repeat(48)}</div>
      </div>

      <div style={{ fontSize:'19px', lineHeight:1.5, color:FG2, flex:1 }}>
        {done.map((l, i) => (
          <div key={i}>
            <span style={{ color:FG3 }}>&gt; {l.t} </span>
            <span style={{ color:FG5 }}>{dots(l.t)}</span>
            <span style={{ color:l.c, textShadow:`0 0 6px ${l.c}`, marginLeft:'0.5rem' }}>{l.s}</span>
          </div>
        ))}
        {!finished && (
          <div>
            <span style={{ color:FG3 }}>&gt; {typed}</span>
            <span style={{ display:'inline-block', width:'0.55em', height:'1em', background:RED, marginLeft:'2px', verticalAlign:'text-bottom', boxShadow:`0 0 6px ${RED}`, animation:'blink 1s step-end infinite' }} />
          </div>
        )}
      </div>

      {finished && (
        <div style={{ marginTop:'1.4rem' }}>
          <div style={{ color:FG5, fontSize:'18px' }}>{'─'.repeat(48)}</div>
          <div style={{ color:GRN, fontSize:'20px', marginTop:'0.6rem', textShadow:`0 0 6px ${GRN}` }}>ALL SYSTEMS NOMINAL.</div>
          <div style={{ marginTop:'0.8rem', fontFamily:DISP, fontSize:'12px', letterSpacing:'0.14em', color:FG1, animation:'blink 1.1s step-end infinite' }}>
            STANDBY — PRESS <span style={{ color:RED, textShadow:`0 0 6px ${RED}` }}>[ENTER]</span> TO WAKE
          </div>
        </div>
      )}
    </div>
  );
}

/* ================================================================ MECH SLOT
   Flexible art frame. Pass one of:
     <MechSlot src="unit.png" />        image / sprite
     <MechSlot ascii={`...`} />         ASCII art
   With nothing passed it renders the default placeholder ASCII below —
   replace it with your own sprite or art. */
const DEFAULT_ASCII =
`        ▄█████▄
      ▄█▀     ▀█▄
     ██   ▄ ▄   ██
     ██  ███████ ██
     ██   ▀▀▀▀▀  ██
      ▀█▄▄███▄▄█▀
     ▄██▀█████▀██▄
    ██▀  █████  ▀██
   ██    █████    ██
   ▀▀   ██   ██   ▀▀
        ██   ██
       ▄██   ██▄
      ████   ████
      ▀▀▀     ▀▀▀`;

function MechSlot({ src, ascii, label = 'UNIT 01', status = 'STANDBY' }) {
  const frame = {
    width:'320px', maxWidth:'34vw', aspectRatio:'3 / 4', border:`1px solid ${LINE2}`,
    background:'rgba(0,0,0,0.5)', display:'flex', flexDirection:'column', position:'relative',
  };
  const corner = (pos) => ({ position:'absolute', width:'10px', height:'10px', borderColor:RED, borderStyle:'solid', ...pos });
  return (
    <div style={frame} data-mech-slot="true">
      {/* registration corners */}
      <span style={corner({ top:-1, left:-1, borderWidth:'2px 0 0 2px' })} />
      <span style={corner({ top:-1, right:-1, borderWidth:'2px 2px 0 0' })} />
      <span style={corner({ bottom:-1, left:-1, borderWidth:'0 0 2px 2px' })} />
      <span style={corner({ bottom:-1, right:-1, borderWidth:'0 2px 2px 0' })} />

      <div style={{ display:'flex', justifyContent:'space-between', padding:'0.4rem 0.6rem', borderBottom:`1px solid ${LINE}` }}>
        <span style={{ fontFamily:DISP, fontSize:'9px', letterSpacing:'0.1em', color:FG3 }}>{label}</span>
        <span style={{ fontFamily:DISP, fontSize:'9px', letterSpacing:'0.1em', color:AMB, textShadow:`0 0 6px ${AMB}` }}>{status}</span>
      </div>

      <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', overflow:'hidden', padding:'0.6rem' }}>
        {src
          ? <img src={src} alt={label} style={{ maxWidth:'100%', maxHeight:'100%', imageRendering:'pixelated' }} />
          : <pre style={{ margin:0, fontFamily:TERM, fontSize:'15px', lineHeight:1.0, color:FG3, textShadow:`0 0 6px rgba(255,255,255,0.18)`, whiteSpace:'pre' }}>{ascii || DEFAULT_ASCII}</pre>}
      </div>

      <div style={{ padding:'0.35rem 0.6rem', borderTop:`1px solid ${LINE}`, fontFamily:TERM, fontSize:'13px', color:FG5, textAlign:'center', letterSpacing:'0.05em' }}>
        {src || ascii ? 'SIGNAL LOCKED' : 'PLACEHOLDER · DROP SPRITE / IMG / ASCII'}
      </div>
    </div>
  );
}

/* ================================================================ MAIN MENU */
function MainMenu({ items, onSelect, operator = 'YUSUF' }) {
  const [sel, setSel] = React.useState(0);
  const enabled = items.filter(i => !i.disabled);

  React.useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSel(s => (s + 1) % items.length); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setSel(s => (s - 1 + items.length) % items.length); }
      else if (e.key === 'Enter') { const it = items[sel]; if (it && !it.disabled) onSelect(it.id); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [sel, items, onSelect]);

  return (
    <div style={{ ...scr.screen, padding:'0' }}>
      {/* top status strip */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'1rem 1.6rem', borderBottom:`1px solid ${LINE}` }}>
        <span style={scr.tag}>NIM // SYSTEM TERMINAL</span>
        <span style={{ ...scr.tag, color:GRN, textShadow:`0 0 6px ${GRN}` }}>● LINK ONLINE</span>
      </div>

      <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0 6vw', gap:'4vw' }}>
        {/* left: wordmark + menu */}
        <div style={{ maxWidth:'560px' }}>
          <div className="nim-wordmark crt-aberrate" style={{ fontFamily:DISP, fontWeight:700, fontSize:'72px', color:FG1, lineHeight:1,
            textShadow:`2px 0 ${RED}, 4px 0 ${RED}, 2px 2px ${RED}, 4px 4px ${REDDIM}, 6px 6px ${REDDIM}, 8px 8px #000` }}>NIM</div>
          <div style={{ fontFamily:DISP, fontSize:'13px', letterSpacing:'0.22em', color:FG3, marginTop:'0.8rem', textTransform:'uppercase' }}>AI GATEWAY · ROUTING TERMINAL</div>

          <div style={{ marginTop:'2.6rem', display:'flex', flexDirection:'column', gap:'0.1rem' }}>
            {items.map((it, i) => {
              const active = i === sel;
              return (
                <button key={it.id}
                  onMouseEnter={() => setSel(i)}
                  onClick={() => !it.disabled && onSelect(it.id)}
                  disabled={it.disabled}
                  style={{ display:'flex', alignItems:'center', gap:'0.7rem', background:'none', border:'none',
                    padding:'0.5rem 0', cursor: it.disabled ? 'not-allowed' : 'pointer', textAlign:'left',
                    fontFamily:DISP, fontSize:'17px', letterSpacing:'0.1em', textTransform:'uppercase',
                    color: it.disabled ? FG5 : active ? RED : FG2,
                    textShadow: active && !it.disabled ? `0 0 10px ${RED}` : 'none' }}>
                  <span style={{ width:'1.1em', color:RED, opacity: active && !it.disabled ? 1 : 0 }}>&gt;</span>
                  <span>{it.label}</span>
                  {it.note && <span style={{ fontFamily:TERM, fontSize:'15px', letterSpacing:0, color:FG4, textTransform:'none' }}>{it.note}</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* right: mech / unit slot */}
        <MechSlot />
      </div>

      {/* bottom bar */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.9rem 1.6rem', borderTop:`1px solid ${LINE}` }}>
        <span style={scr.tag}>OPERATOR: <span style={{ color:FG2 }}>{operator}</span></span>
        <span style={scr.tag}>[↑↓] SELECT &nbsp; [ENTER] CONFIRM</span>
        <span style={scr.tag}>REV 1.0</span>
      </div>
    </div>
  );
}

Object.assign(window, { BootScreen, MainMenu, MechSlot });
})();
