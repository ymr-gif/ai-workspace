import { useEffect } from 'react'
import s from '../../../lib/chatStyles.js'
import { usePanelProps } from '../PanelPropsContext.js'

const isImageMime = (m) => m && m.startsWith('image/')

export default function FileViewer() {
  const p = usePanelProps()
  const { fileViewer, setFileViewer, viewerTab, setViewerTab, viewerEdit, setViewerEdit, viewerSaving, viewerVersions, viewerVerLoading, downloadFile, saveFileEdit, loadFileVersions, restoreFileVersion } = p.files
  const { fmtDate } = p
  if (!fileViewer) return null
  const isImage = isImageMime(fileViewer.mime_type)
  const tabs = isImage ? ['preview','view','edit','versions'] : ['view','edit','versions']

  useEffect(() => {
    if (fileViewer && isImageMime(fileViewer.mime_type) && viewerTab === 'view') {
      setViewerTab('preview')
    }
  }, [fileViewer?.id])
  return (
    <div style={s.viewerOverlay} onClick={() => setFileViewer(null)}>
      <div style={s.viewerModal} onClick={e => e.stopPropagation()}>
        <div style={s.viewerHeader}>
          <span style={s.viewerTitle}>{fileViewer.filename}</span>
          <div style={s.viewerHdrRight}>
            <button onClick={() => downloadFile(fileViewer.id, fileViewer.filename)} style={{ ...s.attachBtn, fontSize:'0.75rem' }} title="Download">⬇ Download</button>
            <button style={s.viewerClose} onClick={() => setFileViewer(null)}>✕</button>
          </div>
        </div>
        <div style={s.tabBar}>
          {tabs.map(tab => (
            <button key={tab} onClick={() => {
              setViewerTab(tab)
              if (tab === 'edit') setViewerEdit(fileViewer.content)
              if (tab === 'versions' && viewerVersions.length === 0) loadFileVersions(fileViewer.id)
            }}
              style={{ ...s.tabBtn, ...(viewerTab === tab ? s.tabActive : {}) }}>
              {tab === 'preview' ? 'Preview' : tab === 'view' ? 'Raw' : tab === 'edit' ? 'Edit' : 'Versions'}
            </button>
          ))}
        </div>
        <div style={s.viewerBody}>
          {viewerTab === 'preview' && (
            <div style={{ padding:8, textAlign:'center' }}>
              <img src={`/api/files/${fileViewer.id}/download`} alt="" style={{ maxWidth:'100%', maxHeight:'65vh', objectFit:'contain' }} />
            </div>
          )}
          {viewerTab === 'view' && <pre style={s.viewerPre}>{fileViewer.content}</pre>}
          {viewerTab === 'edit' && (
            <div>
              <textarea value={viewerEdit} onChange={e => setViewerEdit(e.target.value)} style={s.viewerEditArea} />
              <div style={s.editBtns}>
                <button onClick={() => saveFileEdit(fileViewer.id, viewerEdit)} disabled={viewerSaving} style={s.saveBtn}>
                  {viewerSaving ? 'Saving…' : 'Save'}
                </button>
                <button onClick={() => setViewerTab('view')} style={s.cancelBtn}>Cancel</button>
              </div>
            </div>
          )}
          {viewerTab === 'versions' && (
            <div>
              {viewerVerLoading && <p style={s.emptyMem}>Loading…</p>}
              {!viewerVerLoading && viewerVersions.length === 0 && <p style={s.emptyMem}>No saved versions yet.</p>}
              {!viewerVerLoading && viewerVersions.map(v => (
                <div key={v.id} style={s.versionItem}>
                  <div style={s.versionMeta}>
                    <div style={s.versionNum}>v{v.version}</div>
                    <div style={s.versionDate}>{fmtDate(v.created_at)} · {v.size_chars.toLocaleString()} chars</div>
                  </div>
                  <button onClick={() => restoreFileVersion(fileViewer.id, v.id)} style={s.restoreBtn}>Restore</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
