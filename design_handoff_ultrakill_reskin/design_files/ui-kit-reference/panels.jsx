/* NIM AI Gateway — Memory & Files slide-in panels. Attaches to window. */
const NIM_S3 = window.NIM_S;

/* ---------------------------------------------------------------- Memory */
function MemoryPanel({ open, onClose }) {
  const [tab, setTab] = React.useState('view');
  const tabBtn = (k) => ({ ...NIM_S3.tabBtn, ...(tab === k ? NIM_S3.tabActive : {}) });
  const mem = window.NIM_MEMORY;
  return (
    <div style={{ ...NIM_S3.memPanel, transform: open ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={NIM_S3.memHeader}>
        <div style={NIM_S3.memTitleRow}>
          <span style={NIM_S3.memTitle}><span style={NIM_S3.memDot} /> Memory</span>
          <div style={NIM_S3.memHdrBtns}>
            <button style={NIM_S3.refreshBtn} title="Refresh">↻</button>
            <button style={NIM_S3.closeBtn} onClick={onClose}>✕</button>
          </div>
        </div>
        <div style={NIM_S3.memMeta}>{mem.reduce((n, s) => n + s.pairs.length, 0)} facts · 4 sections</div>
      </div>
      <div style={NIM_S3.tabBar}>
        {['view', 'edit', 'history', 'graph'].map(k => (
          <button key={k} onClick={() => setTab(k)} style={tabBtn(k)}>{k[0].toUpperCase() + k.slice(1)}</button>
        ))}
      </div>
      <div style={NIM_S3.memBody} className="nim-scroll">
        {tab === 'view' && mem.map(sec => (
          <div key={sec.name} style={NIM_S3.section}>
            <span style={{ ...NIM_S3.secLabel, color: sec.color, background: sec.color + '1a' }}>{sec.name}</span>
            {sec.pairs.map(([k, v]) => (
              <div key={k} style={NIM_S3.kv}>
                <span style={NIM_S3.kvKey}>{k}</span>
                <span style={NIM_S3.kvVal}>{v}</span>
              </div>
            ))}
          </div>
        ))}
        {tab === 'edit' && (
          <div>
            <div style={NIM_S3.editLabel}>Raw memory (sectioned)</div>
            <textarea style={{ ...NIM_S3.editArea, minHeight:'220px' }} defaultValue={mem.map(s => `[${s.name}]\n` + s.pairs.map(([k, v]) => `${k}: ${v}`).join('\n')).join('\n\n')} />
            <div style={NIM_S3.editBtns}>
              <button style={NIM_S3.saveBtn}>Save</button>
              <button style={NIM_S3.cancelBtn} onClick={() => setTab('view')}>Cancel</button>
            </div>
          </div>
        )}
        {tab === 'history' && (
          <div style={NIM_S3.historyList}>
            {[['v4', 'added STACK.prefers', '2m ago'], ['v3', 'updated PROJECT.status', '1h ago'], ['v2', 'added GOALS.then', 'Tue']].map(([v, d, t]) => (
              <div key={v} style={NIM_S3.historyItem}>
                <span style={NIM_S3.versionNum}>{v}</span> — {d}
                <div style={NIM_S3.historyMeta}>{t}</div>
              </div>
            ))}
          </div>
        )}
        {tab === 'graph' && (
          <div>
            <div style={NIM_S3.kv}><span style={NIM_S3.kvKey}>available</span><span style={{ ...NIM_S3.kvVal, color:window.NIM_C.GRN }}>yes</span></div>
            <div style={NIM_S3.kv}><span style={NIM_S3.kvKey}>entities</span><span style={NIM_S3.kvVal}>27</span></div>
            <div style={NIM_S3.kv}><span style={NIM_S3.kvKey}>relations</span><span style={NIM_S3.kvVal}>41</span></div>
          </div>
        )}
      </div>
      <div style={NIM_S3.memFooter}>
        <div style={NIM_S3.memToggleRow}>
          <span style={NIM_S3.memToggleLabel}>Context injection</span>
          <button style={{ ...NIM_S3.togglePill, color:window.NIM_C.GRN, borderColor:'rgba(61,255,110,0.5)' }}>◉ ON</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Files */
function FilesPanel({ open, onClose, files, attachedIds, toggleAttach }) {
  const [tab, setTab] = React.useState('library');
  const tabBtn = (k) => ({ ...NIM_S3.tabBtn, ...(tab === k ? NIM_S3.tabActive : {}) });
  const attached = files.filter(f => attachedIds.has(f.id));
  const list = tab === 'library' ? files : attached;
  return (
    <div style={{ ...NIM_S3.filePanel, transform: open ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={NIM_S3.filePanelHdr}>
        <div style={NIM_S3.fileTitleRow}>
          <span style={NIM_S3.fileTitle}>📎 Files &amp; Knowledge</span>
          <button onClick={onClose} style={NIM_S3.closeBtn}>✕</button>
        </div>
      </div>
      <div style={NIM_S3.tabBar}>
        {['library', 'attached'].map(k => (
          <button key={k} onClick={() => setTab(k)} style={tabBtn(k)}>
            {k === 'library' ? 'Library' : `Attached${attached.length ? ` (${attached.length})` : ''}`}
          </button>
        ))}
      </div>
      <div style={NIM_S3.fileUploadRow}>
        <button style={{ ...NIM_S3.ingestBtn, background:'rgba(39,216,255,0.08)', color:window.NIM_C.CYN, borderColor:window.NIM_C.CYN }}>⬆ Upload</button>
      </div>
      <div style={NIM_S3.urlRow}>
        <input placeholder="https://… ingest URL" style={NIM_S3.urlInput} />
        <button style={NIM_S3.ingestBtn}>⬇ Fetch</button>
      </div>
      <div style={NIM_S3.wsRow}>
        <span style={NIM_S3.wsLabel}>WS:</span>
        <button style={{ ...NIM_S3.wsPill, ...NIM_S3.wsPillActive }}>All</button>
        {window.NIM_WORKSPACES.map(ws => <button key={ws.id} style={NIM_S3.wsPill}>{ws.name}</button>)}
      </div>
      <div style={NIM_S3.fileList} className="nim-scroll">
        {list.length === 0 && <p style={NIM_S3.emptyMem}>No files attached.<br /><span style={{ fontSize:'0.75rem' }}>Switch to Library to attach files.</span></p>}
        {list.map(f => {
          const sc = window.nimStatusColor(f.status);
          const isAtt = attachedIds.has(f.id);
          return (
            <div key={f.id} style={NIM_S3.fileItem}>
              <span style={{ ...NIM_S3.statusBadge, background: sc.bg, color: sc.color }}>{f.status}</span>
              <span style={NIM_S3.fileName} title={f.filename}>{f.filename}</span>
              <button style={NIM_S3.attachBtn} title="Rename">✎</button>
              <button style={NIM_S3.attachBtn} title="View">👁</button>
              <button style={NIM_S3.attachBtn} title="Download">⬇</button>
              <button onClick={() => toggleAttach(f.id)} style={{ ...NIM_S3.attachBtn, ...(isAtt ? NIM_S3.attachedBtn : {}) }}
                title={isAtt ? 'Detach' : 'Attach'}>{isAtt ? '✓' : '+'}</button>
              <button style={NIM_S3.delBtn} title="Delete">🗑</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { MemoryPanel, FilesPanel });
