/* NIM // CANVAS — style tokens. Exposed as window.NIM_CANVAS_C and window.NIM_CANVAS_S */

const NIM_CANVAS_C = {
  RED:      '#ff2222',
  REDDIM:   '#b81818',
  GRN:      '#3dff6e',
  AMB:      '#ffb000',
  CYN:      '#27d8ff',
  VIO:      'rgba(139,92,246,0.7)',
  VIO_GLOW: '0 0 8px rgba(139,92,246,0.35)',
  VOID:     '#000000',
  PANEL:    '#0a0a0a',
  INSET:    '#050505',
  FG1:      '#ffffff',
  FG2:      '#c8c8c8',
  FG3:      '#8f8f8f',
  FG4:      '#5a5a5a',
  FG5:      '#383838',
  LINE:     '#262626',
  LINE2:    '#4a4a4a',
  DISP:     "'Chakra Petch', sans-serif",
  TERM:     "'JetBrains Mono', monospace",
};

/* node card base — shared across all node types */
const NIM_CANVAS_S = {
  nodeCard: {
    background: '#141414',
    border: '1px solid #4a4a4a',
    borderLeft: '2px solid #ff2222',
    borderRadius: 0,
    minWidth: '200px',
    fontFamily: "'Chakra Petch', sans-serif",
    overflow: 'hidden',
    boxShadow: '2px 2px 0 #000, inset 1px 0 0 rgba(255,34,34,0.15)',
  },
  nodeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '8px 10px',
    borderBottom: '1px solid #262626',
  },
  nodeLabel: {
    fontSize: 10,
    letterSpacing: '0.12em',
    color: '#8f8f8f',
    textTransform: 'uppercase',
  },
  nodeBody: {
    padding: '10px 12px',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 12,
    color: '#383838',
    lineHeight: 1.4,
  },
  /* handle base (square) */
  handle: {
    background: '#4a4a4a',
    borderRadius: 0,
    width: 8,
    height: 8,
    border: '1px solid #555',
  },
  /* context menu */
  ctxMenu: {
    background: '#0a0a0a',
    border: '1px solid #4a4a4a',
    borderRadius: 0,
    minWidth: '220px',
    overflow: 'hidden',
    boxShadow: '4px 4px 0 #000',
  },
  ctxHeader: {
    padding: '7px 12px',
    borderBottom: '1px solid #262626',
    fontFamily: "'Chakra Petch', sans-serif",
    fontSize: 9,
    letterSpacing: '0.14em',
    color: '#5a5a5a',
    textTransform: 'uppercase',
  },
  ctxItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 9,
    padding: '11px 12px',
    cursor: 'pointer',
    fontFamily: "'Chakra Petch', sans-serif",
    fontSize: 10,
    letterSpacing: '0.08em',
    color: '#8f8f8f',
    transition: 'all 0.08s',
    textTransform: 'uppercase',
    userSelect: 'none',
  },
};

window.NIM_CANVAS_C = NIM_CANVAS_C;
window.NIM_CANVAS_S = NIM_CANVAS_S;
