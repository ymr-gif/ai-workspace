import s from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

export default function FilesPanel() {
  const p = usePanelProps()
  const { filesOpen, setFilesOpen, filesTab, setFilesTab, libFiles, attachedFiles, fileUploading, urlIngest, setUrlIngest, urlIngesting, renameId, setRenameId, renameVal, setRenameVal, fileInputRef, attachedIds, uploadFile, ingestUrl, attachFile, detachFile, viewFile, downloadFile, deleteFile, commitRename, statusColor } = p.files
  const { activeConvId } = p.conv
  return (
    <div style={{ ...s.filePanel, transform: filesOpen ? 'translateX(0)' : 'translateX(100%)' }}>
      <div style={s.filePanelHdr}>
        <div style={s.fileTitleRow}>
          <span style={s.fileTitle}>📎 Files & Knowledge</span>
          <button onClick={() => setFilesOpen(false)} style={s.closeBtn}>✕</button>
        </div>
      </div>

      <div style={s.tabBar}>
        {['library','attached'].map(tab => (
          <button key={tab} onClick={() => setFilesTab(tab)}
            style={{ ...s.tabBtn, ...(filesTab === tab ? s.tabActive : {}) }}>
            {tab === 'library' ? 'Library' : `Attached${attachedFiles.length ? ` (${attachedFiles.length})` : ''}`}
          </button>
        ))}
      </div>

      <div style={s.fileUploadRow}>
        <button onClick={() => fileInputRef.current?.click()} disabled={fileUploading}
          style={{ ...s.ingestBtn, background:'rgba(39,216,255,0.08)', color:'#27d8ff', borderColor:'rgba(39,216,255,0.40)' }}>
          {fileUploading ? 'Uploading…' : '⬆ Upload'}
        </button>
        <input ref={fileInputRef} type="file" style={{ display:'none' }} onChange={uploadFile} />
      </div>

      <div style={s.urlRow}>
        <input value={urlIngest} onChange={e => setUrlIngest(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && ingestUrl()}
          placeholder="https://… ingest URL" style={s.urlInput} />
        <button onClick={ingestUrl} disabled={urlIngesting || !urlIngest.trim()} style={s.ingestBtn}>
          {urlIngesting ? '…' : '⬇ Fetch'}
        </button>
      </div>

      <div style={s.fileList}>
        {filesTab === 'library' && (
          libFiles.length === 0
            ? <p style={s.emptyMem}>No files yet.<br /><span style={{ fontSize:'0.75rem' }}>Upload files or ingest a URL above.</span></p>
            : libFiles.map(f => {
                const sc = statusColor(f.status)
                const isAttached = attachedIds.has(f.id)
                return (
                  <div key={f.id} style={s.fileItem}>
                    <span style={{ ...s.statusBadge, background:sc.bg, color:sc.color }}>{f.status}</span>
                    {renameId === f.id
                      ? <input autoFocus style={s.renameInput} value={renameVal} onChange={e => setRenameVal(e.target.value)}
                          onKeyDown={e => { if (e.key==='Enter') commitRename(f.id); if (e.key==='Escape') setRenameId(null) }}
                          onBlur={() => commitRename(f.id)} />
                      : <span style={s.fileName} title={f.filename}>{f.filename}</span>
                    }
                    <button onClick={() => { setRenameId(f.id); setRenameVal(f.filename) }} style={s.attachBtn} title="Rename">✎</button>
                    <button onClick={() => viewFile(f.id)} style={s.attachBtn} title="View contents">👁</button>
                    <button onClick={() => downloadFile(f.id, f.filename)} style={s.attachBtn} title="Download">⬇</button>
                    {activeConvId && (
                      <button onClick={() => isAttached ? detachFile(f.id) : attachFile(f.id)}
                        style={{ ...s.attachBtn, ...(isAttached ? s.attachedBtn : {}) }}
                        title={isAttached ? 'Detach from conversation' : 'Attach to conversation'}>
                        {isAttached ? '✓' : '+'}
                      </button>
                    )}
                    <button onClick={() => deleteFile(f.id)} style={s.delBtn} title="Delete file">🗑</button>
                  </div>
                )
              })
        )}
        {filesTab === 'attached' && (
          !activeConvId
            ? <p style={s.emptyMem}>Open a conversation to attach files.</p>
            : attachedFiles.length === 0
              ? <p style={s.emptyMem}>No files attached.<br /><span style={{ fontSize:'0.75rem' }}>Switch to Library tab to attach files.</span></p>
              : attachedFiles.map(f => {
                  const sc = statusColor(f.status)
                  return (
                    <div key={f.id} style={s.fileItem}>
                      <span style={{ ...s.statusBadge, background:sc.bg, color:sc.color }}>{f.status}</span>
                      <span style={s.fileName} title={f.filename}>{f.filename}</span>
                      <button onClick={() => viewFile(f.id)} style={s.attachBtn} title="View contents">👁</button>
                      <button onClick={() => detachFile(f.id)} style={s.attachBtn} title="Detach">✕</button>
                    </div>
                  )
                })
        )}
      </div>
    </div>
  )
}
