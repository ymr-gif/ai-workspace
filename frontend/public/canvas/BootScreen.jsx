/* NIM // CANVAS — Boot sequence. Exports window.BootScreen */
(function () {
  const C = window.NIM_CANVAS_C;
  const { buildBootLines, fetchHardware } = window.NIM_CANVAS_DATA;

  const DOTS_COL = 46;
  const fillDots = (label) => '.'.repeat(Math.max(3, DOTS_COL - label.length));

  function BootScreen({ onWake }) {
    const [hwData,   setHwData]   = React.useState(null);
    const [lines,    setLines]    = React.useState([]);
    const [lineIdx,  setLineIdx]  = React.useState(0);
    const [finished, setFinished] = React.useState(false);
    const [allLines, setAllLines] = React.useState(null);

    /* fetch hardware on mount */
    React.useEffect(() => {
      fetchHardware().then(hw => {
        setHwData(hw);
        setAllLines(buildBootLines(hw));
      });
    }, []);

    /* line reveal — one line per tick, avoids iframe timer throttling */
    React.useEffect(() => {
      if (!allLines) return;
      if (lineIdx >= allLines.length) { setFinished(true); return; }
      const id = setTimeout(() => {
        setLines(prev => [...prev, allLines[lineIdx]]);
        setLineIdx(i => i + 1);
      }, lineIdx < 8 ? 60 : 100);
      return () => clearTimeout(id);
    }, [allLines, lineIdx]);

    /* wake on Enter / Space / click when finished */
    React.useEffect(() => {
      if (!finished) return;
      const onKey = (e) => { if (e.key === 'Enter' || e.key === ' ') onWake(); };
      window.addEventListener('keydown', onKey);
      return () => window.removeEventListener('keydown', onKey);
    }, [finished, onWake]);

    const ss = {
      screen: {
        position: 'absolute', inset: 0,
        padding: '7vh 8vw',
        fontFamily: C.TERM,
        color: C.FG1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      },
      header: {
        fontFamily: C.DISP,
        fontSize: 18,
        fontWeight: 700,
        color: C.FG1,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        textShadow: `2px 2px 0 ${C.REDDIM}`,
      },
      sub: {
        fontFamily: C.DISP,
        fontSize: 9,
        color: C.FG4,
        letterSpacing: '0.2em',
        textTransform: 'uppercase',
        marginTop: 6,
      },
      rule: { color: C.FG5, fontSize: 16, marginTop: 12, marginBottom: 12 },
      lineRow: { fontSize: 14, lineHeight: 1.6, color: C.FG3 },
      cursor: {
        display: 'inline-block',
        width: '0.55em',
        height: '1em',
        background: C.RED,
        marginLeft: 2,
        verticalAlign: 'text-bottom',
        boxShadow: `0 0 6px ${C.RED}`,
        animation: 'blink 1s step-end infinite',
      },
      nominal: {
        fontFamily: C.TERM,
        fontSize: 18,
        color: C.GRN,
        textShadow: `0 0 8px rgba(61,255,110,0.5)`,
        marginTop: 8,
      },
      prompt: {
        fontFamily: C.DISP,
        fontSize: 12,
        letterSpacing: '0.12em',
        color: C.FG1,
        marginTop: 12,
        textTransform: 'uppercase',
        animation: 'blink 1.1s step-end infinite',
      },
    };

    return (
      <div style={{...ss.screen, cursor: finished ? 'pointer' : 'default'}} onClick={finished ? onWake : undefined}>
        <div style={ss.header}>NIM // SYSTEM TERMINAL</div>
        <div style={ss.sub}>BIOS REV 2.0 — JARVIS CANVAS ENGINE</div>
        <div style={ss.rule}>{'─'.repeat(50)}</div>

        <div style={{ flex: 1 }}>
          {/* committed lines */}
          {lines.map((ln, i) => (
            <div key={i} style={ss.lineRow}>
              <span style={{ color: C.FG4 }}>&gt; </span>
              <span style={{ color: C.FG2 }}>{ln.label} </span>
              <span style={{ color: C.FG5 }}>{fillDots(ln.label)}</span>
              <span style={{ color: ln.color, textShadow: `0 0 6px ${ln.color}`, marginLeft: 6 }}>
                {ln.status}
              </span>
            </div>
          ))}

          {/* typing indicator */}
          {!finished && allLines && lineIdx < allLines.length && (
            <div style={ss.lineRow}>
              <span style={{ color: C.FG4 }}>&gt; </span>
              <span style={{ color: C.FG5, animation:'blink 0.5s step-end infinite' }}>■</span>
            </div>
          )}
        </div>

        {finished && (
          <div>
            <div style={ss.rule}>{'─'.repeat(50)}</div>
            <div style={ss.nominal}>ALL SYSTEMS NOMINAL.</div>
            <div style={ss.prompt}>
              PRESS{' '}
              <span style={{ color: C.RED, textShadow: `0 0 6px ${C.RED}` }}>[ENTER]</span>
              {' '}TO CONTINUE
            </div>
          </div>
        )}
      </div>
    );
  }

  Object.assign(window, { BootScreen });
})();
