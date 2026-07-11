// Flight Ops B+ design tokens — mission-control calm.
// Rule of the system: mono = data (telemetry, labels, ids, timestamps), sans = prose.
// TRACK cyan is reserved for provenance traces only — never reuse it.

export const MONO = "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace"
export const SANS = "'IBM Plex Sans', -apple-system, 'Segoe UI', system-ui, sans-serif"
// Legacy aliases (pre-B+ components import these names): DISP = label/chrome font, TERM = body font.
export const DISP = MONO
export const TERM = SANS

// Palette — see frontend/CLAUDE.md token table.
export const AMBER = '#f2a33c'   // THE accent: primary actions, active states, selection, focus
export const NOMINAL = '#55d67c' // success / grounding-high / memory confirm
export const ALERT = '#e5534b'   // errors, delete, breaker-open
export const TRACK = '#5cc8f0'   // provenance trace ONLY
export const INFOBLUE = '#4f9cf0'// info accents: tool names, insight dots, calendar confirm

// Legacy aliases (semantic mapping from the old skin's names)
export const RED = ALERT, REDDIM = '#a63d38', GRN = NOMINAL, AMB = AMBER, CYN = INFOBLUE

export const VOID = '#0a0f16', PANEL = '#0f1622', INSET = '#0d131d', RAISE = '#13202f'
export const FG1 = '#e9f1f9', FG2 = '#d7e1ec', FG3 = '#8ba3bd', FG4 = '#4d647e', FG5 = '#33465e'
export const LINE = '#1d2a3a', LINE2 = '#2a4160'

export const LAYERS = { overlay: 10, panel: 11, settingsModal: 20, palette: 30, viewer: 50, onboarding: 60 }

// mono micro-label shorthand
const lbl = { fontFamily: MONO, letterSpacing: '0.1em', textTransform: 'uppercase' }
const nums = { fontVariantNumeric: 'tabular-nums' }

// Dock panes replace the old absolutely-positioned slide-in panels: panels render
// inside the Dock body and fill it. One pane visible at a time (Dock decides).
// position:relative anchors the Goals/Automations form overlays (absolute inset:0),
// which used to anchor on the absolutely-positioned panelBase.
const dockPane = { flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', background: 'transparent', position: 'relative' }

const s = {
  root:        { display:'flex', height:'100vh', background:VOID, color:FG1, fontFamily:SANS, fontSize:'15px', position:'relative', overflow:'hidden' },
  shellBody:   { flex:1, display:'flex', minHeight:0 },

  // ---- telemetry strip (replaces the old header) ----
  teleStrip:   { display:'flex', alignItems:'center', gap:'1.1rem', padding:'0.45rem 1rem', background:INSET, borderBottom:`1px solid ${LINE}`, flexShrink:0, overflow:'hidden' },
  teleBrand:   { ...lbl, fontSize:'11px', color:FG1, fontWeight:600, letterSpacing:'0.16em', whiteSpace:'nowrap' },
  teleItem:    { ...lbl, ...nums, fontSize:'10px', color:FG3, whiteSpace:'nowrap', display:'flex', alignItems:'center', gap:'0.35rem' },
  teleVal:     { color:AMBER, fontWeight:600 },
  teleOk:      { color:NOMINAL },
  teleBad:     { color:ALERT },
  teleDot:     { width:'6px', height:'6px', borderRadius:'50%', background:NOMINAL, boxShadow:`0 0 5px rgba(85,214,124,0.6)`, flexShrink:0 },
  teleDotBad:  { background:ALERT, boxShadow:`0 0 5px rgba(229,83,75,0.6)` },
  teleRight:   { marginLeft:'auto', display:'flex', gap:'0.4rem', alignItems:'center' },
  teleBtn:     { ...lbl, background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', padding:'0.25rem 0.55rem', borderRadius:'3px', fontSize:'9px' },
  teleBtnOn:   { color:AMBER, borderColor:'rgba(242,163,60,0.5)' },

  // ---- sidebar / rail ----
  sidebar:     { width:'250px', display:'flex', flexDirection:'column', borderRight:`1px solid ${LINE}`, flexShrink:0, background:INSET },
  sideTop:     { padding:'0.75rem', borderBottom:`1px solid ${LINE}` },
  newBtn:      { ...lbl, width:'100%', padding:'0.55rem', borderRadius:'3px', background:'rgba(242,163,60,0.12)', color:AMBER, border:`1px solid ${AMBER}`, cursor:'pointer', fontWeight:600, fontSize:'10px' },
  convList:    { flex:1, overflowY:'auto', padding:'0.4rem' },
  convItem:    { padding:'0.5rem 0.6rem', borderRadius:'3px', cursor:'pointer', marginBottom:'2px', fontSize:'13px', lineHeight:1.3, position:'relative', display:'flex', justifyContent:'space-between', alignItems:'flex-start', boxShadow:'inset 2px 0 0 transparent' },
  convMeta:    { flex:1, minWidth:0 },
  convTitle:   { display:'block', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', color:FG2, fontSize:'13px' },
  convDate:    { ...lbl, ...nums, display:'block', fontSize:'8.5px', color:FG4, marginTop:'3px' },
  convDel:     { flexShrink:0, marginLeft:'4px', marginTop:'1px', background:'none', border:'none', cursor:'pointer', color:FG4, fontSize:'0.8rem', lineHeight:1, padding:'2px 4px', borderRadius:'3px' },

  // ---- chat column ----
  chat:        { flex:1, display:'flex', flexDirection:'column', minWidth:0 },

  // ---- feed ----
  feed:        { flex:1, overflowY:'auto', padding:'1.25rem', display:'flex', flexDirection:'column', gap:'0.9rem' },
  hint:        { color:FG4, textAlign:'center', marginTop:'5rem', fontSize:'15px' },
  bubble:      { maxWidth:'74%', padding:'0.65rem 0.9rem', lineHeight:1.5, fontSize:'15px' },
  userBubble:  { alignSelf:'flex-end', background:RAISE, border:`1px solid ${LINE2}`, color:FG1, borderRadius:'6px 6px 2px 6px' },
  aiBubble:    { alignSelf:'flex-start', background:PANEL, border:`1px solid ${LINE}`, color:FG2, borderRadius:'2px 6px 6px 6px' },
  errBubble:   { alignSelf:'flex-start', background:PANEL, border:`1px solid ${ALERT}`, color:'#f0867f', borderRadius:'2px 6px 6px 6px' },
  text:        { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' },
  cursor:      { display:'inline-block', width:'0.5em', height:'1em', background:AMBER, marginLeft:'2px', verticalAlign:'text-bottom', animation:'blink 1s step-end infinite' },
  tag:         { ...lbl, ...nums, display:'block', marginTop:'0.35rem', fontSize:'9px', color:FG4 },
  tokMeta:     { ...lbl, ...nums, display:'block', marginTop:'0.2rem', fontSize:'9px', color:FG4 },

  // grounding gauge (replaces the dot badge)
  gaugeRow:    { ...lbl, ...nums, display:'inline-flex', alignItems:'center', gap:'0.45rem', marginTop:'0.4rem', fontSize:'9px', color:FG3, userSelect:'none' },
  gaugeBar:    { width:'64px', height:'4px', background:LINE, borderRadius:'2px', overflow:'hidden', flexShrink:0 },
  gaugeFill:   { display:'block', height:'100%', borderRadius:'2px' },

  // provenance trace (B+ signature — TRACK cyan only)
  traceRow:    { ...lbl, display:'flex', alignItems:'center', flexWrap:'wrap', rowGap:'3px', marginTop:'0.4rem', fontSize:'8.5px' },
  traceLbl:    { color:FG4, marginRight:'0.5rem' },
  traceNode:   { display:'inline-flex', alignItems:'center', gap:'4px', color:'#9fd9f2', cursor:'pointer', textTransform:'none', letterSpacing:'0.02em' },
  traceDia:    { width:'5px', height:'5px', transform:'rotate(45deg)', background:TRACK, boxShadow:'0 0 4px rgba(92,200,240,0.55)', flexShrink:0 },
  traceLink:   { width:'14px', height:'1px', background:'rgba(92,200,240,0.4)', margin:'0 5px', flexShrink:0 },
  traceChip:   { ...lbl, ...nums, display:'inline-block', marginTop:'0.4rem', fontSize:'8.5px', color:TRACK, border:'1px solid rgba(92,200,240,0.35)', borderRadius:'3px', padding:'1px 6px', cursor:'pointer', userSelect:'none' },

  // reasoning-steps timeline (kept from before, retinted)
  toolPill:    { ...lbl, ...nums, display:'inline-flex', alignItems:'center', gap:'4px', fontSize:'9px', color:INFOBLUE, background:INSET, border:`1px solid ${LINE}`, borderRadius:'3px', padding:'2px 8px', marginBottom:'4px', cursor:'pointer' },
  toolResult:  { ...nums, fontSize:'12px', fontFamily:MONO, color:FG4, background:INSET, borderRadius:'3px', padding:'6px 8px', marginBottom:'6px', whiteSpace:'pre-wrap', wordBreak:'break-word', maxHeight:'120px', overflowY:'auto' },

  // compare
  compareRow:  { display:'flex', gap:'0.6rem', alignSelf:'stretch' },
  compareCard: { flex:1, minWidth:0, background:PANEL, border:`1px solid ${LINE}`, borderTop:`2px solid ${LINE2}`, borderRadius:'0 0 6px 6px', padding:'0.65rem 0.85rem' },
  cardHeader:  { ...lbl, fontSize:'9px', color:FG3, marginBottom:'0.5rem' },
  cardModel:   { ...lbl, fontSize:'8.5px', color:FG4, marginTop:'0.35rem', display:'block' },

  // toolbar
  toolbarWrap: { background:INSET, borderTop:`1px solid ${LINE}`, padding:'0.5rem 1.1rem 0' },
  toolbar:     { display:'flex', justifyContent:'space-between', alignItems:'center', gap:'0.5rem' },
  modelPills:  { display:'flex', gap:'0.3rem', flexWrap:'wrap' },
  pill:        { ...lbl, padding:'0.3rem 0.6rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', color:FG3, cursor:'pointer', fontSize:'9px', transition:'all 0.12s' },
  pillActive:  { background:AMBER, borderColor:AMBER, color:VOID, fontWeight:700 },
  pillCompare: { background:'rgba(85,214,124,0.10)', borderColor:NOMINAL, color:NOMINAL },
  toolRight:   { display:'flex', gap:'0.3rem' },

  // params expander
  paramsBar:   { display:'flex', gap:'1.5rem', padding:'0.5rem 0', marginTop:'0.35rem', borderTop:`1px solid ${LINE}` },
  paramItem:   { display:'flex', alignItems:'center', gap:'0.4rem', flex:1, minWidth:0 },
  paramLabel:  { ...lbl, fontSize:'9px', minWidth:'42px', flexShrink:0, color:FG3 },
  paramVal:    { ...nums, fontFamily:MONO, fontSize:'11px', minWidth:'40px', textAlign:'right', flexShrink:0, color:FG2 },

  // input bar
  bar:         { display:'flex', gap:'0.5rem', padding:'0.7rem 1.1rem 0.9rem', background:INSET },
  input:       { flex:1, padding:'0.55rem 0.8rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:VOID, color:FG1, fontFamily:SANS, fontSize:'14px', outline:'none' },
  send:        { ...lbl, padding:'0.55rem 1rem', borderRadius:'3px', background:'rgba(242,163,60,0.12)', color:AMBER, border:`1px solid ${AMBER}`, cursor:'pointer', fontWeight:600, fontSize:'10px' },
  micBtn:      { ...lbl, padding:'0.45rem 0.65rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', cursor:'pointer', fontSize:'9px', color:FG3, lineHeight:1, flexShrink:0 },
  micRec:      { color:ALERT, borderColor:ALERT },
  fileChipsRow:{ display:'flex', gap:'0.35rem', padding:'0 1.1rem 0.4rem', flexWrap:'wrap', background:INSET },
  fileChip:    { ...nums, display:'flex', alignItems:'center', gap:'0.3rem', padding:'0.15rem 0.5rem', borderRadius:'3px', background:PANEL, border:`1px solid ${LINE2}`, fontFamily:MONO, fontSize:'11px', color:INFOBLUE },
  chipX:       { cursor:'pointer', color:FG4, fontSize:'0.8rem', lineHeight:1 },

  // ---- dock (right inspector zone) ----
  dock:        { width:'360px', maxWidth:'40vw', display:'flex', flexDirection:'column', borderLeft:`1px solid ${LINE}`, background:INSET, flexShrink:0, minHeight:0 },
  dockTabs:    { display:'flex', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  dockTab:     { ...lbl, flex:1, padding:'0.55rem 0.2rem', background:'none', border:'none', borderBottom:'2px solid transparent', cursor:'pointer', fontSize:'9px', color:FG4 },
  dockTabOn:   { color:AMBER, borderBottomColor:AMBER },
  dockSubs:    { display:'flex', gap:'0.25rem', padding:'0.45rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, flexWrap:'wrap' },
  dockSub:     { ...lbl, padding:'0.2rem 0.5rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', color:FG3, cursor:'pointer', fontSize:'8.5px' },
  dockSubOn:   { color:AMBER, borderColor:'rgba(242,163,60,0.5)', background:'rgba(242,163,60,0.08)' },
  dockPane,
  // legacy panel keys → all render as dock panes now
  memPanel: dockPane, toolLogPanel: dockPane, filePanel: dockPane,
  invitePanel: dockPane, insightsPanel: dockPane, usagePanel: dockPane,

  // shared panel innards (headers, tabs, lists — used by pane content)
  memHeader:   { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  memTitleRow: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.3rem' },
  memTitle:    { ...lbl, fontSize:'10px', color:FG1, display:'flex', alignItems:'center', gap:'0.5rem' },
  memMeta:     { ...lbl, ...nums, fontSize:'9px', color:FG4, textTransform:'none' },
  memHdrBtns:  { display:'flex', gap:'0.4rem', alignItems:'center' },
  refreshBtn:  { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'0.8rem', padding:'0.1rem 0.4rem', borderRadius:'3px', lineHeight:1 },
  closeBtn:    { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'0.8rem', padding:'0.1rem 0.4rem', borderRadius:'3px', lineHeight:1.2 },
  tabBar:      { display:'flex', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  tabBtn:      { ...lbl, flex:1, padding:'0.45rem 0.3rem', background:'none', border:'none', cursor:'pointer', fontSize:'8.5px', color:FG4, borderBottom:'2px solid transparent' },
  tabActive:   { color:AMBER, borderBottomColor:AMBER },
  memBody:     { flex:1, overflowY:'auto', padding:'0.75rem 0.9rem' },
  emptyMem:    { color:FG4, fontSize:'13px', textAlign:'center', marginTop:'3rem', lineHeight:1.5 },
  section:     { marginBottom:'1.1rem' },
  secLabel:    { ...lbl, fontSize:'8.5px', marginBottom:'0.5rem', padding:'0.15rem 0.45rem', borderRadius:'3px', display:'inline-block', border:'1px solid currentColor' },
  kv:          { display:'flex', gap:'0.5rem', fontSize:'13px', lineHeight:1.4, padding:'0.2rem 0', borderBottom:`1px solid ${RAISE}` },
  kvKey:       { color:FG4, minWidth:'92px', flexShrink:0, fontFamily:MONO, fontSize:'11px' },
  kvVal:       { color:FG2, wordBreak:'break-word', flex:1 },
  divider:     { borderTop:`1px solid ${LINE}`, margin:'1rem 0 0.75rem', display:'flex', alignItems:'center', gap:'0.5rem' },
  divLabel:    { ...lbl, fontSize:'7.5px', letterSpacing:'0.2em', color:FG5, whiteSpace:'nowrap' },
  memFooter:   { padding:'0.6rem 0.9rem', borderTop:`1px solid ${LINE}`, flexShrink:0, display:'flex', flexDirection:'column', gap:'0.5rem' },
  footerRow:   { ...lbl, display:'flex', justifyContent:'space-between', alignItems:'center', fontSize:'8.5px' },
  footerActions: { display:'flex', gap:'0.4rem' },
  actionBtn:   { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'12px', padding:'0.2rem 0.5rem', borderRadius:'3px' },
  footerStats: { ...nums, fontFamily:MONO, fontSize:'10px', color:FG5 },
  memToggleRow:   { display:'flex', alignItems:'center', justifyContent:'space-between' },
  memToggleLabel: { ...lbl, fontSize:'8.5px', color:FG4 },
  togglePill:     { ...lbl, display:'flex', alignItems:'center', gap:'0.35rem', background:'none', border:`1px solid ${LINE2}`, borderRadius:'3px', padding:'0.2rem 0.55rem', cursor:'pointer', fontSize:'8.5px' },
  editArea:    { width:'100%', background:VOID, border:`1px solid ${LINE2}`, borderRadius:'3px', color:FG2, fontFamily:MONO, fontSize:'12px', lineHeight:1.5, padding:'0.6rem', resize:'vertical', outline:'none', boxSizing:'border-box' },
  editLabel:   { ...lbl, fontSize:'8.5px', color:FG4, marginBottom:'0.35rem', marginTop:'0.75rem' },
  editBtns:    { display:'flex', gap:'0.5rem', marginTop:'1rem' },
  saveBtn:     { ...lbl, padding:'0.4rem 1rem', borderRadius:'3px', background:AMBER, color:VOID, border:'none', cursor:'pointer', fontSize:'9px', fontWeight:700 },
  cancelBtn:   { ...lbl, padding:'0.4rem 0.75rem', borderRadius:'3px', background:'none', color:FG3, border:`1px solid ${LINE2}`, cursor:'pointer', fontSize:'9px' },
  historyList: { display:'flex', flexDirection:'column', gap:'0.5rem' },
  historyItem: { padding:'0.5rem 0.7rem', borderRadius:'3px', border:`1px solid ${LINE}`, cursor:'pointer', fontSize:'13px', background:PANEL },
  historyMeta: { ...lbl, ...nums, color:FG4, fontSize:'8px', marginTop:'0.3rem' },
  diffBox:     { marginTop:'1rem', padding:'0.75rem', background:PANEL, border:`1px solid ${LINE}`, borderRadius:'3px' },
  diffTitle:   { ...lbl, fontSize:'8.5px', color:FG3, marginBottom:'0.5rem' },
  diffLine:    { ...nums, fontSize:'12px', fontFamily:MONO, lineHeight:1.6, padding:'0.05rem 0.4rem', marginBottom:'1px', wordBreak:'break-word' },
  diffAdded:   { background:'rgba(85,214,124,0.12)', color:NOMINAL },
  diffRemoved: { background:'rgba(229,83,75,0.12)', color:ALERT },
  diffSame:    { color:FG4 },
  updatingDot: { width:'7px', height:'7px', borderRadius:'50%', background:NOMINAL, boxShadow:`0 0 5px rgba(85,214,124,0.6)`, animation:'pulse 1s ease-in-out infinite' },
  flashBody:   { animation:'memFlash 1.5s ease-out' },
  memDot:      { width:'6px', height:'6px', borderRadius:'50%', background:INFOBLUE, boxShadow:`0 0 4px rgba(79,156,240,0.6)` },
  unreadBadge: { ...lbl, ...nums, display:'inline-flex', alignItems:'center', justifyContent:'center', minWidth:'15px', height:'14px', borderRadius:'7px', background:AMBER, color:VOID, fontSize:'8px', fontWeight:700, padding:'0 4px', marginLeft:'3px' },

  // settings modal (kept as modal)
  settingsModal:  { position:'absolute', top:'50%', left:'50%', transform:'translate(-50%,-50%)', width:'440px', maxWidth:'92vw', background:INSET, border:`1px solid ${LINE2}`, borderRadius:'6px', zIndex:LAYERS.settingsModal, display:'flex', flexDirection:'column' },
  settingsHeader: { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.8rem 1rem', borderBottom:`1px solid ${LINE}` },
  settingsTitle:  { ...lbl, fontSize:'10px', color:FG1 },
  settingsBody:   { padding:'1.1rem', overflowY:'auto' },
  settingsFooter: { display:'flex', justifyContent:'flex-end', gap:'0.5rem', padding:'0.7rem 1.1rem', borderTop:`1px solid ${LINE}` },
  notifSection:  { borderTop:`1px solid ${LINE}`, margin:'1.1rem 0 0.75rem', paddingTop:'0.75rem' },
  notifLabel:    { ...lbl, fontSize:'8.5px', color:FG4, marginBottom:'0.5rem' },
  notifRow:      { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'0.35rem 0', borderBottom:`1px solid ${RAISE}` },
  notifText:     { fontSize:'13px', color:FG2 },

  // ask_user card
  askCard:       { display:'flex', gap:'0.55rem', alignItems:'flex-start', background:'rgba(242,163,60,0.08)', border:`1px solid rgba(242,163,60,0.40)`, borderRadius:'4px', padding:'0.6rem 0.8rem', marginTop:'0.5rem' },
  askIcon:       { fontSize:'0.95rem', flexShrink:0, marginTop:'1px' },
  askLabel:      { ...lbl, fontSize:'8.5px', color:AMBER, marginBottom:'0.25rem' },
  askQuestion:   { fontSize:'13.5px', color:'#f5c98a', lineHeight:1.4 },

  // tool log rows
  toolLogHdr:    { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', justifyContent:'space-between', alignItems:'center' },
  toolLogTitle:  { ...lbl, fontSize:'10px', color:FG1 },
  toolLogBody:   { flex:1, overflowY:'auto', padding:'0.6rem 0.9rem' },
  toolLogRow:    { display:'flex', flexDirection:'column', gap:'3px', padding:'0.5rem 0.6rem', borderRadius:'3px', marginBottom:'4px', border:`1px solid ${LINE}`, background:PANEL },
  toolLogMeta:   { display:'flex', gap:'0.5rem', alignItems:'center', justifyContent:'space-between' },
  toolLogName:   { ...nums, color:INFOBLUE, fontFamily:MONO, fontSize:'11px' },
  toolLogTime:   { ...nums, color:FG4, fontFamily:MONO, fontSize:'10px' },
  toolLogArgs:   { ...nums, color:FG4, fontFamily:MONO, fontSize:'10.5px', whiteSpace:'pre-wrap', wordBreak:'break-all' },
  toolLogResult: { color:FG3, fontSize:'12px', whiteSpace:'pre-wrap', wordBreak:'break-word' },

  // files pane
  filePanelHdr:  { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  fileTitleRow:  { display:'flex', justifyContent:'space-between', alignItems:'center' },
  fileTitle:     { ...lbl, fontSize:'10px', color:FG1 },
  fileUploadRow: { display:'flex', gap:'0.4rem', padding:'0.6rem 0.9rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, flexWrap:'wrap' },
  urlRow:        { display:'flex', gap:'0.4rem', padding:'0 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  urlInput:      { flex:1, padding:'0.3rem 0.55rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:VOID, color:FG1, fontFamily:MONO, fontSize:'11px', outline:'none' },
  ingestBtn:     { ...lbl, padding:'0.25rem 0.6rem', borderRadius:'3px', background:'rgba(85,214,124,0.08)', color:NOMINAL, border:`1px solid rgba(85,214,124,0.5)`, cursor:'pointer', fontSize:'8.5px', whiteSpace:'nowrap' },
  wsPill:        { ...lbl, padding:'0.2rem 0.5rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', color:FG3, cursor:'pointer', fontSize:'8.5px' },
  wsPillActive:  { background:'rgba(242,163,60,0.10)', borderColor:'rgba(242,163,60,0.5)', color:AMBER },
  fileList:      { flex:1, overflowY:'auto', padding:'0.5rem 0.9rem' },
  fileItem:      { display:'flex', alignItems:'center', gap:'0.5rem', padding:'0.45rem 0.55rem', marginBottom:'4px', border:`1px solid ${LINE}`, borderRadius:'3px', background:PANEL },
  fileName:      { flex:1, minWidth:0, fontFamily:MONO, fontSize:'11.5px', color:FG2, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' },
  fileMeta:      { ...nums, fontFamily:MONO, fontSize:'10px', color:FG4, whiteSpace:'nowrap' },
  imgThumb:      { width:36, height:36, objectFit:'cover', borderRadius:'3px', flexShrink:0 },
  statusBadge:   { ...lbl, fontSize:'7.5px', padding:'0.15rem 0.35rem', borderRadius:'3px', whiteSpace:'nowrap', border:'1px solid currentColor' },
  attachBtn:     { padding:'0.15rem 0.4rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', cursor:'pointer', fontSize:'0.75rem', color:FG3, whiteSpace:'nowrap', lineHeight:1.2 },
  attachedBtn:   { background:'rgba(242,163,60,0.10)', borderColor:'rgba(242,163,60,0.5)', color:AMBER },
  delBtn:        { padding:'0.15rem 0.35rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:'none', cursor:'pointer', fontSize:'0.75rem', color:ALERT, lineHeight:1.2 },
  renameInput:   { flex:1, padding:'0.15rem 0.4rem', border:`1px solid ${AMBER}`, borderRadius:'3px', background:VOID, color:FG1, fontSize:'12px', outline:'none' },

  // file viewer modal
  viewerOverlay: { position:'fixed', inset:0, background:'rgba(4,8,14,0.75)', zIndex:LAYERS.viewer, display:'flex', alignItems:'center', justifyContent:'center' },
  viewerModal:   { background:INSET, border:`1px solid ${LINE2}`, borderRadius:'6px', width:'700px', maxWidth:'95vw', maxHeight:'80vh', display:'flex', flexDirection:'column' },
  viewerHeader:  { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.9rem 1.1rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  viewerTitle:   { fontFamily:MONO, fontSize:'12px', color:FG1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', flex:1, marginRight:'0.5rem' },
  viewerHdrRight:{ display:'flex', gap:'0.35rem', alignItems:'center', flexShrink:0 },
  viewerClose:   { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'0.9rem', lineHeight:1, padding:'2px 6px', borderRadius:'3px' },
  viewerBody:    { flex:1, overflowY:'auto', padding:'1rem 1.1rem' },
  viewerPre:     { margin:0, fontFamily:MONO, fontSize:'12px', color:FG3, whiteSpace:'pre-wrap', wordBreak:'break-word', lineHeight:1.6 },
  viewerEditArea:{ width:'100%', background:VOID, border:`1px solid ${LINE2}`, borderRadius:'3px', color:FG2, fontSize:'12px', lineHeight:1.6, padding:'0.6rem', resize:'vertical', outline:'none', fontFamily:MONO, boxSizing:'border-box', minHeight:'300px' },
  versionItem:   { display:'flex', alignItems:'center', gap:'0.5rem', padding:'0.5rem 0.6rem', marginBottom:'4px', border:`1px solid ${LINE}`, borderRadius:'3px', background:PANEL, fontSize:'13px' },
  versionMeta:   { flex:1, minWidth:0 },
  versionNum:    { color:AMBER, fontWeight:600, fontFamily:MONO },
  versionDate:   { ...nums, color:FG4, fontSize:'11px', marginTop:'1px', fontFamily:MONO },
  restoreBtn:    { ...lbl, padding:'0.15rem 0.5rem', border:`1px solid rgba(85,214,124,0.5)`, borderRadius:'3px', background:'rgba(85,214,124,0.10)', color:NOMINAL, cursor:'pointer', fontSize:'8.5px', whiteSpace:'nowrap' },

  // sidebar search
  sideSearchWrap:  { padding:'0.4rem 0.5rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  sideSearchInput: { width:'100%', padding:'0.3rem 0.55rem', borderRadius:'3px', border:`1px solid ${LINE2}`, background:VOID, color:FG1, fontFamily:SANS, fontSize:'12px', outline:'none', boxSizing:'border-box' },

  // invites pane
  inviteHdr:    { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', justifyContent:'space-between', alignItems:'center' },
  inviteTitle:  { ...lbl, fontSize:'10px', color:FG1 },
  inviteBody:   { flex:1, overflowY:'auto', padding:'0.9rem 0.9rem' },
  inviteRow:    { padding:'0.6rem 0.75rem', marginBottom:'6px', border:`1px solid ${LINE}`, borderRadius:'3px', background:PANEL, fontSize:'13px' },
  tokenBox:     { background:'rgba(79,156,240,0.08)', border:`1px solid rgba(79,156,240,0.40)`, borderRadius:'4px', padding:'0.75rem', marginBottom:'1rem' },
  tokenText:    { ...nums, fontFamily:MONO, fontSize:'12px', color:INFOBLUE, wordBreak:'break-all', cursor:'pointer', userSelect:'all' },

  // proactive card
  proactiveCard: { display:'flex', gap:'0.55rem', alignItems:'flex-start', background:'rgba(79,156,240,0.08)', border:`1px solid rgba(79,156,240,0.40)`, borderRadius:'4px', padding:'0.6rem 0.8rem', margin:'0 1.1rem 0.5rem' },
  proactiveLabel:{ ...lbl, fontSize:'8.5px', color:INFOBLUE, marginBottom:'0.3rem' },
  proactiveTxt:  { fontSize:'13.5px', color:FG2, lineHeight:1.4, flex:1 },
  proactiveDismiss: { background:'none', border:'none', color:FG4, cursor:'pointer', fontSize:'0.9rem', padding:'0 2px', lineHeight:1, flexShrink:0 },

  // insights rows
  insightsHdr:   { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', justifyContent:'space-between', alignItems:'center' },
  insightsTitle: { ...lbl, fontSize:'10px', color:FG1 },
  insightsBody:  { flex:1, overflowY:'auto', padding:'0.75rem 0.9rem' },
  insightRow:    { display:'flex', gap:'0.5rem', alignItems:'flex-start', padding:'0.6rem 0.7rem', borderRadius:'3px', marginBottom:'6px', border:`1px solid ${LINE}`, background:PANEL, fontSize:'13px', cursor:'pointer', transition:'border-color 0.12s' },
  insightDot:    { width:'7px', height:'7px', borderRadius:'50%', background:INFOBLUE, boxShadow:`0 0 4px rgba(79,156,240,0.6)`, flexShrink:0, marginTop:'6px' },
  insightContent:{ flex:1, color:FG2, lineHeight:1.4 },
  insightMeta:   { ...lbl, ...nums, fontSize:'7.5px', color:FG4, marginTop:'0.3rem' },
  insightDel:    { background:'none', border:'none', color:FG4, cursor:'pointer', fontSize:'0.8rem', padding:'2px 4px', borderRadius:'3px', flexShrink:0, lineHeight:1 },

  // usage pane
  usageHdr:      { padding:'0.75rem 0.9rem 0.6rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', justifyContent:'space-between', alignItems:'center' },
  usageTitle:    { ...lbl, fontSize:'10px', color:FG1 },
  usageBody:     { flex:1, overflowY:'auto', padding:'0.75rem 0.9rem' },
  usageStat:     { ...nums, display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.5rem 0', borderBottom:`1px solid ${LINE}`, fontSize:'13px' },
  usageKey:      { color:FG4, fontFamily:MONO, fontSize:'11px' },
  usageVal:      { color:FG1, fontFamily:MONO },

  // command palette
  paletteOverlay: { position:'fixed', inset:0, background:'rgba(4,8,14,0.7)', zIndex:LAYERS.palette, display:'flex', alignItems:'flex-start', justifyContent:'center', paddingTop:'14vh' },
  palette:        { width:'560px', maxWidth:'92vw', maxHeight:'60vh', background:INSET, border:`1px solid ${LINE2}`, borderRadius:'6px', display:'flex', flexDirection:'column', overflow:'hidden', boxShadow:'0 12px 40px rgba(0,0,0,0.5)' },
  paletteInput:   { padding:'0.75rem 1rem', border:'none', borderBottom:`1px solid ${LINE}`, background:'transparent', color:FG1, fontFamily:SANS, fontSize:'15px', outline:'none' },
  paletteBody:    { flex:1, overflowY:'auto', padding:'0.4rem' },
  paletteGroup:   { ...lbl, fontSize:'8px', color:FG5, padding:'0.5rem 0.7rem 0.25rem' },
  paletteRow:     { display:'flex', alignItems:'center', gap:'0.6rem', padding:'0.45rem 0.7rem', borderRadius:'4px', cursor:'pointer', fontSize:'13.5px', color:FG2 },
  paletteRowOn:   { background:RAISE, boxShadow:`inset 2px 0 0 ${AMBER}` },
  paletteSrc:     { ...lbl, ...nums, fontSize:'8px', marginLeft:'auto', flexShrink:0 },
  paletteScore:   { ...nums, fontFamily:MONO, fontSize:'10px', color:FG5, flexShrink:0 },
  paletteHint:    { ...lbl, ...nums, display:'flex', gap:'1rem', padding:'0.45rem 1rem', borderTop:`1px solid ${LINE}`, fontSize:'8px', color:FG5 },
}

export default s
