/* NIM // SYSTEM TERMINAL — style tokens (ULTRAKILL-mod).
   Same key set as the original NIM_S so components keep working;
   every value re-skinned: black/white/red, Silkscreen + VT323,
   zero radius, hard edges, arcade-CRT semantics.
   Exposed as window.NIM_S. */

const DISP = "'Silkscreen', monospace";   // chunky pixel — labels, buttons, headings
const TERM = "'VT323', monospace";         // readable pixel — body, chat, data

const RED = '#ff2222', REDDIM = '#b81818', GRN = '#3dff6e', AMB = '#ffb000', CYN = '#27d8ff';
const VOID = '#000', PANEL = '#0a0a0a', INSET = '#050505';
const FG1 = '#ffffff', FG2 = '#c8c8c8', FG3 = '#8f8f8f', FG4 = '#5a5a5a', FG5 = '#383838';
const LINE = '#262626', LINE2 = '#4a4a4a';

const s = {
  root:        { display:'flex', height:'100vh', background:'transparent', color:FG1, fontFamily:TERM, fontSize:'18px', position:'relative', overflow:'hidden' },

  // ---- sidebar ----
  sidebar:     { width:'250px', display:'flex', flexDirection:'column', borderRight:`1px solid ${LINE}`, flexShrink:0, background:'rgba(0,0,0,0.55)' },
  sideTop:     { padding:'0.85rem', borderBottom:`1px solid ${LINE}` },
  newBtn:      { width:'100%', padding:'0.6rem', borderRadius:0, background:RED, color:'#000', border:'none', cursor:'pointer', fontFamily:DISP, fontWeight:700, fontSize:'11px', letterSpacing:'0.12em', textTransform:'uppercase' },
  convList:    { flex:1, overflowY:'auto', padding:'0.4rem' },
  convItem:    { padding:'0.55rem 0.6rem', borderRadius:0, cursor:'pointer', marginBottom:'2px', fontSize:'16px', lineHeight:1.25, position:'relative', display:'flex', justifyContent:'space-between', alignItems:'flex-start', borderLeft:'2px solid transparent' },
  convMeta:    { flex:1, minWidth:0 },
  convTitle:   { display:'block', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', color:FG2, fontFamily:TERM, fontSize:'17px' },
  convDate:    { display:'block', fontFamily:DISP, fontSize:'9px', color:FG4, marginTop:'4px', letterSpacing:'0.08em', textTransform:'uppercase' },
  convDel:     { flexShrink:0, marginLeft:'4px', marginTop:'1px', background:'none', border:'none', cursor:'pointer', color:FG4, fontSize:'0.85rem', lineHeight:1, padding:'2px 4px', borderRadius:0 },

  // ---- chat column ----
  chat:        { flex:1, display:'flex', flexDirection:'column', minWidth:0 },
  header:      { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.7rem 1.25rem', background:'rgba(0,0,0,0.55)', borderBottom:`1px solid ${LINE}` },
  title:       { fontFamily:DISP, fontWeight:700, fontSize:'15px', color:FG1, letterSpacing:'0.04em', textTransform:'uppercase', textShadow:`2px 2px 0 ${REDDIM}` },
  headerRight: { display:'flex', gap:'0.4rem', alignItems:'center' },
  hdrBtn:      { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', padding:'0.35rem 0.55rem', borderRadius:0, fontFamily:DISP, fontSize:'9px', letterSpacing:'0.1em', textTransform:'uppercase', display:'flex', alignItems:'center', gap:'0.3rem' },
  memDot:      { width:'7px', height:'7px', borderRadius:0, background:CYN, boxShadow:`0 0 5px ${CYN}` },
  logout:      { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', padding:'0.35rem 0.6rem', borderRadius:0, fontFamily:DISP, fontSize:'9px', letterSpacing:'0.1em', textTransform:'uppercase' },

  // ---- feed ----
  feed:        { flex:1, overflowY:'auto', padding:'1.5rem', display:'flex', flexDirection:'column', gap:'1rem' },
  hint:        { color:FG4, textAlign:'center', marginTop:'5rem', fontFamily:TERM, fontSize:'20px', letterSpacing:'0.02em' },
  bubble:      { maxWidth:'74%', padding:'0.7rem 0.95rem', borderRadius:0, lineHeight:1.35, fontSize:'18px' },
  userBubble:  { alignSelf:'flex-end', background:RED, color:'#000', boxShadow:`3px 3px 0 ${REDDIM}` },
  aiBubble:    { alignSelf:'flex-start', background:PANEL, border:`1px solid ${LINE}`, color:FG2, borderLeft:`2px solid ${LINE2}` },
  errBubble:   { alignSelf:'flex-start', background:PANEL, border:`1px solid ${RED}`, color:'#ff7a7a' },

  text:        { margin:0, whiteSpace:'pre-wrap', wordBreak:'break-word' },
  cursor:      { display:'inline-block', width:'0.55em', height:'1.05em', background:RED, marginLeft:'2px', verticalAlign:'text-bottom', boxShadow:`0 0 6px ${RED}`, animation:'blink 1s step-end infinite' },
  tag:         { display:'block', marginTop:'0.3rem', fontFamily:TERM, fontSize:'14px', color:FG4 },

  // ---- compare ----
  compareRow:  { display:'flex', gap:'0.6rem', alignSelf:'stretch' },
  compareCard: { flex:1, minWidth:0, background:PANEL, border:`1px solid ${LINE}`, borderTop:`2px solid ${LINE2}`, borderRadius:0, padding:'0.65rem 0.85rem' },
  cardHeader:  { fontFamily:DISP, fontSize:'10px', color:FG3, marginBottom:'0.5rem', letterSpacing:'0.1em', textTransform:'uppercase' },
  cardModel:   { fontFamily:TERM, fontSize:'14px', color:FG4, marginTop:'0.35rem' },

  // ---- toolbar ----
  toolbarWrap: { background:'rgba(0,0,0,0.55)', borderTop:`1px solid ${LINE}`, padding:'0.5rem 1.25rem 0' },
  toolbar:     { display:'flex', justifyContent:'space-between', alignItems:'center', gap:'0.5rem' },
  modelPills:  { display:'flex', gap:'0.3rem', flexWrap:'wrap' },
  pill:        { padding:'0.3rem 0.6rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'none', color:FG3, cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', transition:'all 0.08s' },
  pillActive:  { background:RED, borderColor:RED, color:'#000' },
  pillCompare: { background:'rgba(61,255,110,0.10)', borderColor:GRN, color:GRN, textShadow:`0 0 6px rgba(61,255,110,0.5)` },
  toolRight:   { display:'flex', gap:'0.3rem' },

  // ---- params ----
  paramsBar:   { display:'flex', gap:'1.5rem', padding:'0.5rem 0', marginTop:'0.35rem', borderTop:`1px solid ${LINE}` },
  paramItem:   { display:'flex', alignItems:'center', gap:'0.4rem', flex:1, minWidth:0 },
  paramLabel:  { fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', minWidth:'42px', flexShrink:0 },
  paramVal:    { fontFamily:TERM, fontSize:'15px', minWidth:'40px', textAlign:'right', flexShrink:0 },

  // ---- input bar ----
  bar:         { display:'flex', gap:'0.5rem', padding:'0.7rem 1.25rem 1rem', background:'rgba(0,0,0,0.55)' },
  input:       { flex:1, padding:'0.6rem 0.85rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'#000', color:FG1, fontFamily:TERM, fontSize:'20px', outline:'none' },
  send:        { padding:'0.6rem 1.1rem', borderRadius:0, background:RED, color:'#000', border:'none', cursor:'pointer', fontFamily:DISP, fontWeight:700, fontSize:'11px', letterSpacing:'0.1em', textTransform:'uppercase' },

  // ---- overlay + slide-in panels (red left edge) ----
  overlay:     { position:'absolute', inset:0, background:'rgba(0,0,0,0.78)', zIndex:10 },
  memPanel:    { position:'absolute', top:0, right:0, bottom:0, width:'390px', maxWidth:'92vw', background:'#070707', borderLeft:`2px solid ${RED}`, zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.18s cubic-bezier(.2,.9,.1,1)' },
  memHeader:   { padding:'0.9rem 1.1rem 0.7rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  memTitleRow: { display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'0.3rem' },
  memTitle:    { fontFamily:DISP, fontSize:'13px', color:FG1, letterSpacing:'0.1em', textTransform:'uppercase', display:'flex', alignItems:'center', gap:'0.5rem' },
  memMeta:     { fontFamily:TERM, fontSize:'14px', color:FG4 },
  memHdrBtns:  { display:'flex', gap:'0.4rem', alignItems:'center' },
  refreshBtn:  { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'0.9rem', padding:'0.15rem 0.45rem', borderRadius:0, lineHeight:1 },
  closeBtn:    { background:'none', border:`1px solid ${LINE2}`, color:FG3, cursor:'pointer', fontSize:'0.85rem', padding:'0.1rem 0.4rem', borderRadius:0, lineHeight:1.2 },
  tabBar:      { display:'flex', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  tabBtn:      { flex:1, padding:'0.5rem 0.3rem', background:'none', border:'none', cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', color:FG4, borderBottom:'2px solid transparent' },
  tabActive:   { color:RED, borderBottomColor:RED, textShadow:`0 0 6px ${RED}` },
  memBody:     { flex:1, overflowY:'auto', padding:'0.9rem 1.1rem' },
  emptyMem:    { color:FG4, fontFamily:TERM, fontSize:'18px', textAlign:'center', marginTop:'3rem', lineHeight:1.5 },
  section:     { marginBottom:'1.2rem' },
  secLabel:    { fontFamily:DISP, fontSize:'10px', letterSpacing:'0.1em', marginBottom:'0.5rem', padding:'0.2rem 0.45rem', borderRadius:0, display:'inline-block', textTransform:'uppercase', border:'1px solid currentColor' },
  kv:          { display:'flex', gap:'0.5rem', fontFamily:TERM, fontSize:'17px', lineHeight:1.35, padding:'0.2rem 0', borderBottom:`1px solid #161616` },
  kvKey:       { color:FG4, minWidth:'92px', flexShrink:0 },
  kvVal:       { color:FG2, wordBreak:'break-word', flex:1 },
  divider:     { borderTop:`1px solid ${LINE}`, margin:'1rem 0 0.75rem', display:'flex', alignItems:'center', gap:'0.5rem' },
  divLabel:    { fontFamily:DISP, fontSize:'8px', letterSpacing:'0.2em', color:FG5, whiteSpace:'nowrap', textTransform:'uppercase' },
  memFooter:   { padding:'0.7rem 1.1rem', borderTop:`1px solid ${LINE}`, flexShrink:0, display:'flex', flexDirection:'column', gap:'0.5rem' },
  memToggleRow:   { display:'flex', alignItems:'center', justifyContent:'space-between' },
  memToggleLabel: { fontFamily:DISP, fontSize:'9px', letterSpacing:'0.1em', textTransform:'uppercase', color:FG4 },
  togglePill:     { display:'flex', alignItems:'center', gap:'0.35rem', background:'none', border:`1px solid ${LINE2}`, borderRadius:0, padding:'0.2rem 0.55rem', cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase' },
  editArea:    { width:'100%', background:'#000', border:`1px solid ${LINE2}`, borderRadius:0, color:FG2, fontFamily:TERM, fontSize:'17px', lineHeight:1.4, padding:'0.6rem', resize:'vertical', outline:'none', boxSizing:'border-box' },
  editLabel:   { fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', color:FG4, marginBottom:'0.35rem', marginTop:'0.75rem' },
  editBtns:    { display:'flex', gap:'0.5rem', marginTop:'1rem' },
  saveBtn:     { padding:'0.4rem 1rem', borderRadius:0, background:RED, color:'#000', border:'none', cursor:'pointer', fontFamily:DISP, fontSize:'10px', letterSpacing:'0.08em', textTransform:'uppercase', fontWeight:700 },
  cancelBtn:   { padding:'0.4rem 0.75rem', borderRadius:0, background:'none', color:FG3, border:`1px solid ${LINE2}`, cursor:'pointer', fontFamily:DISP, fontSize:'10px', letterSpacing:'0.08em', textTransform:'uppercase' },
  historyList: { display:'flex', flexDirection:'column', gap:'0.5rem' },
  historyItem: { padding:'0.5rem 0.7rem', borderRadius:0, border:`1px solid ${LINE}`, cursor:'pointer', fontFamily:TERM, fontSize:'16px', background:INSET },
  versionNum:  { color:RED, fontWeight:700 },
  historyMeta: { color:FG4, fontFamily:DISP, fontSize:'8px', letterSpacing:'0.08em', textTransform:'uppercase', marginTop:'0.3rem' },

  // ---- files panel ----
  filePanel:     { position:'absolute', top:0, right:0, bottom:0, width:'410px', maxWidth:'92vw', background:'#070707', borderLeft:`2px solid ${RED}`, zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.18s cubic-bezier(.2,.9,.1,1)' },
  filePanelHdr:  { padding:'0.9rem 1.1rem 0.7rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  fileTitleRow:  { display:'flex', justifyContent:'space-between', alignItems:'center' },
  fileTitle:     { fontFamily:DISP, fontSize:'13px', color:FG1, letterSpacing:'0.1em', textTransform:'uppercase' },
  fileUploadRow: { display:'flex', gap:'0.4rem', padding:'0.7rem 1.1rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, flexWrap:'wrap' },
  urlRow:        { display:'flex', gap:'0.4rem', padding:'0 1.1rem 0.7rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  urlInput:      { flex:1, padding:'0.35rem 0.55rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'#000', color:FG1, fontFamily:TERM, fontSize:'16px', outline:'none' },
  ingestBtn:     { padding:'0.3rem 0.7rem', borderRadius:0, background:'rgba(61,255,110,0.08)', color:GRN, border:`1px solid ${GRN}`, cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.06em', textTransform:'uppercase', whiteSpace:'nowrap' },
  wsRow:         { display:'flex', gap:'0.3rem', padding:'0.5rem 1.1rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, flexWrap:'wrap', alignItems:'center' },
  wsLabel:       { fontFamily:DISP, fontSize:'9px', letterSpacing:'0.08em', textTransform:'uppercase', color:FG4, marginRight:'0.15rem' },
  wsPill:        { padding:'0.2rem 0.5rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'none', color:FG3, cursor:'pointer', fontFamily:DISP, fontSize:'9px', letterSpacing:'0.06em', textTransform:'uppercase' },
  wsPillActive:  { background:'rgba(255,34,34,0.10)', borderColor:RED, color:RED },
  fileList:      { flex:1, overflowY:'auto', padding:'0.5rem 1.1rem' },
  fileItem:      { display:'flex', alignItems:'center', gap:'0.4rem', padding:'0.45rem 0.55rem', borderRadius:0, marginBottom:'4px', border:`1px solid ${LINE}`, background:INSET },
  fileName:      { flex:1, minWidth:0, fontFamily:TERM, fontSize:'16px', color:FG2, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' },
  fileMeta:      { fontFamily:TERM, fontSize:'13px', color:FG4, whiteSpace:'nowrap' },
  statusBadge:   { fontFamily:DISP, fontSize:'8px', padding:'0.15rem 0.35rem', borderRadius:0, letterSpacing:'0.06em', textTransform:'uppercase', whiteSpace:'nowrap', border:'1px solid currentColor' },
  attachBtn:     { padding:'0.15rem 0.4rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'none', cursor:'pointer', fontSize:'0.8rem', color:FG3, whiteSpace:'nowrap', lineHeight:1.2 },
  attachedBtn:   { background:'rgba(255,34,34,0.10)', borderColor:RED, color:RED },
  delBtn:        { padding:'0.15rem 0.35rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'none', cursor:'pointer', fontSize:'0.8rem', color:RED, lineHeight:1.2 },
  fileChipsRow:  { display:'flex', gap:'0.35rem', padding:'0 1.25rem 0.4rem', flexWrap:'wrap' },
  fileChip:      { display:'flex', alignItems:'center', gap:'0.3rem', padding:'0.2rem 0.5rem', borderRadius:0, background:PANEL, border:`1px solid ${LINE2}`, fontFamily:TERM, fontSize:'15px', color:CYN },
  chipX:         { cursor:'pointer', color:FG4, fontSize:'0.85rem', lineHeight:1 },

  // ---- workspace gear/plus ----
  wsGearBtn:    { background:'none', border:'none', color:FG4, cursor:'pointer', fontSize:'0.6rem', padding:'0 1px', lineHeight:1, marginLeft:'1px' },
  wsPlusBtn:    { padding:'0.18rem 0.45rem', borderRadius:0, border:`1px dashed ${LINE2}`, background:'none', color:FG4, cursor:'pointer', fontFamily:DISP, fontSize:'9px', lineHeight:1.2 },

  // ---- sidebar search ----
  sideSearchWrap:  { padding:'0.4rem 0.5rem', borderBottom:`1px solid ${LINE}`, flexShrink:0 },
  sideSearchInput: { width:'100%', padding:'0.35rem 0.55rem', borderRadius:0, border:`1px solid ${LINE2}`, background:'#000', color:FG1, fontFamily:TERM, fontSize:'16px', outline:'none', boxSizing:'border-box' },

  // ---- proactive / ask cards ----
  proactiveCard: { display:'flex', gap:'0.55rem', alignItems:'flex-start', background:'rgba(39,216,255,0.08)', border:`1px solid rgba(39,216,255,0.40)`, borderRadius:0, padding:'0.6rem 0.8rem', margin:'0 1.25rem 0.5rem' },
  proactiveLabel:{ fontFamily:DISP, fontSize:'9px', color:CYN, marginBottom:'0.3rem', letterSpacing:'0.1em', textTransform:'uppercase' },
  proactiveTxt:  { fontFamily:TERM, fontSize:'17px', color:FG2, lineHeight:1.35, flex:1 },
  proactiveDismiss: { background:'none', border:'none', color:FG4, cursor:'pointer', fontSize:'0.95rem', padding:'0 2px', lineHeight:1, flexShrink:0 },
  askCard:       { display:'flex', gap:'0.55rem', alignItems:'flex-start', background:'rgba(255,176,0,0.08)', border:`1px solid rgba(255,176,0,0.40)`, borderRadius:0, padding:'0.6rem 0.8rem', marginTop:'0.5rem' },
  askIcon:       { fontSize:'1rem', flexShrink:0, marginTop:'1px' },
  askLabel:      { fontFamily:DISP, fontSize:'9px', color:AMB, marginBottom:'0.25rem', letterSpacing:'0.1em', textTransform:'uppercase' },
  askQuestion:   { fontFamily:TERM, fontSize:'17px', color:'#ffd98a', lineHeight:1.35 },

  // ---- tool log panel ----
  toolLogPanel:  { position:'absolute', top:0, right:0, bottom:0, width:'480px', maxWidth:'95vw', background:'#070707', borderLeft:`2px solid ${RED}`, zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.18s cubic-bezier(.2,.9,.1,1)' },
  toolLogRow:    { display:'flex', flexDirection:'column', gap:'3px', padding:'0.5rem 0.6rem', borderRadius:0, marginBottom:'4px', border:`1px solid ${LINE}`, background:INSET },
  toolLogMeta:   { display:'flex', gap:'0.5rem', alignItems:'center', justifyContent:'space-between' },
  toolLogName:   { color:CYN, fontFamily:DISP, fontSize:'10px', letterSpacing:'0.06em' },
  toolLogTime:   { color:FG4, fontFamily:TERM, fontSize:'14px' },
  toolLogArgs:   { color:FG4, fontFamily:TERM, fontSize:'14px', whiteSpace:'pre-wrap', wordBreak:'break-all' },
  toolLogResult: { color:FG3, fontFamily:TERM, fontSize:'15px', whiteSpace:'pre-wrap', wordBreak:'break-word' },

  // ---- insights panel ----
  insightsPanel: { position:'absolute', top:0, right:0, bottom:0, width:'410px', maxWidth:'92vw', background:'#070707', borderLeft:`2px solid ${RED}`, zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.18s cubic-bezier(.2,.9,.1,1)' },
  insightRow:    { display:'flex', gap:'0.5rem', alignItems:'flex-start', padding:'0.6rem 0.7rem', borderRadius:0, marginBottom:'6px', border:`1px solid ${LINE}`, background:INSET, fontFamily:TERM, fontSize:'17px', cursor:'pointer', transition:'border-color 0.08s' },
  insightDot:    { width:'8px', height:'8px', borderRadius:0, background:CYN, boxShadow:`0 0 5px ${CYN}`, flexShrink:0, marginTop:'6px' },
  insightContent:{ flex:1, color:FG2, lineHeight:1.35 },
  insightMeta:   { fontFamily:DISP, fontSize:'8px', letterSpacing:'0.06em', textTransform:'uppercase', color:FG4, marginTop:'0.3rem' },
  insightDel:    { background:'none', border:'none', color:FG4, cursor:'pointer', fontSize:'0.85rem', padding:'2px 4px', borderRadius:0, flexShrink:0, lineHeight:1 },
  unreadBadge:   { display:'inline-flex', alignItems:'center', justifyContent:'center', minWidth:'15px', height:'14px', borderRadius:0, background:RED, color:'#000', fontFamily:DISP, fontSize:'8px', fontWeight:700, padding:'0 3px', marginLeft:'3px' },

  // ---- token meta + usage panel ----
  tokMeta:       { display:'block', marginTop:'0.25rem', fontFamily:TERM, fontSize:'14px', color:FG4 },
  usagePanel:    { position:'absolute', top:0, right:0, bottom:0, width:'360px', maxWidth:'92vw', background:'#070707', borderLeft:`2px solid ${RED}`, zIndex:11, display:'flex', flexDirection:'column', transition:'transform 0.18s cubic-bezier(.2,.9,.1,1)' },
  usageHdr:      { padding:'0.9rem 1.1rem 0.7rem', borderBottom:`1px solid ${LINE}`, flexShrink:0, display:'flex', justifyContent:'space-between', alignItems:'center' },
  usageTitle:    { fontFamily:DISP, fontSize:'13px', color:FG1, letterSpacing:'0.1em', textTransform:'uppercase' },
  usageBody:     { flex:1, overflowY:'auto', padding:'0.9rem 1.1rem' },
  usageStat:     { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'0.5rem 0', borderBottom:`1px solid ${LINE}`, fontFamily:TERM, fontSize:'18px' },
  usageKey:      { color:FG4 },
  usageVal:      { color:FG1, fontFamily:TERM, fontWeight:400 },
}

window.NIM_S = s
window.NIM_C = { RED, REDDIM, GRN, AMB, CYN, VOID, PANEL, INSET, FG1, FG2, FG3, FG4, FG5, LINE, LINE2, DISP, TERM };
