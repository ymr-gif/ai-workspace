import { useState, useRef, useEffect, useCallback, useMemo } from 'react'

export default function useFiles(token, activeConvId) {
  const [filesOpen, setFilesOpen] = useState(false)
  const [filesTab, setFilesTab] = useState('library')
  const [fileViewer, setFileViewer] = useState(null)
  const [libFiles, setLibFiles] = useState([])
  const [attachedFiles, setAttachedFiles] = useState([])
  const [fileUploading, setFileUploading] = useState(false)
  const [urlIngest, setUrlIngest] = useState('')
  const [urlIngesting, setUrlIngesting] = useState(false)
  const [renameId, setRenameId] = useState(null)
  const [renameVal, setRenameVal] = useState('')
  const [viewerTab, setViewerTab] = useState('view')
  const [viewerEdit, setViewerEdit] = useState('')
  const [viewerSaving, setViewerSaving] = useState(false)
  const [viewerVersions, setViewerVersions] = useState([])
  const [viewerVerLoading, setViewerVerLoading] = useState(false)
  const fileInputRef = useRef(null)
  const statusStreamsRef = useRef({})

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  const loadLibFiles = useCallback(async () => {
    try {
      const r = await fetch('/api/files', { headers: authHeaders })
      if (r.ok) setLibFiles(await r.json())
    } catch { /* ignore */ }
  }, [token])

  const loadAttachedFiles = useCallback(async () => {
    if (!activeConvId) { setAttachedFiles([]); return }
    try {
      const r = await fetch(`/api/conversations/${activeConvId}/files`, { headers: authHeaders })
      if (r.ok) setAttachedFiles(await r.json())
    } catch { /* ignore */ }
  }, [token, activeConvId])

  useEffect(() => {
    if (!filesOpen) return
    loadLibFiles(); loadAttachedFiles()
  }, [filesOpen])

  useEffect(() => { if (activeConvId) loadAttachedFiles() }, [activeConvId])

  async function uploadFile(e) {
    const file = e.target.files?.[0]; if (!file) return
    setFileUploading(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await fetch('/api/files/upload', { method:'POST', headers: authHeaders, body: fd })
      if (r.ok) { await loadLibFiles() }
    } catch { /* ignore */ } finally { setFileUploading(false); e.target.value = '' }
  }

  async function ingestUrl() {
    const url = urlIngest.trim(); if (!url) return
    setUrlIngesting(true)
    try {
      const r = await fetch('/api/files/ingest-url', { method:'POST', headers:{...authHeaders,'Content-Type':'application/json'}, body:JSON.stringify({url}) })
      if (r.ok) { setUrlIngest(''); await loadLibFiles() }
    } catch { /* ignore */ } finally { setUrlIngesting(false) }
  }

  async function attachFile(fileId) {
    if (!activeConvId) return
    try {
      await fetch(`/api/conversations/${activeConvId}/files`, { method:'POST', headers:{...authHeaders,'Content-Type':'application/json'}, body:JSON.stringify({file_id:fileId}) })
      await loadAttachedFiles()
    } catch { /* ignore */ }
  }

  async function detachFile(fileId) {
    if (!activeConvId) return
    try {
      await fetch(`/api/conversations/${activeConvId}/files/${fileId}`, { method:'DELETE', headers: authHeaders })
      await loadAttachedFiles()
    } catch { /* ignore */ }
  }

  async function deleteFile(fileId) {
    try {
      await fetch(`/api/files/${fileId}`, { method:'DELETE', headers: authHeaders })
      setAttachedFiles(prev => prev.filter(f => f.id !== fileId))
      await loadLibFiles()
    } catch { /* ignore */ }
  }

  async function viewFile(fileId) {
    try {
      const r = await fetch(`/api/files/${fileId}/content`, { headers: authHeaders })
      if (r.ok) { setFileViewer({ ...(await r.json()), id: fileId }); setViewerTab('view'); setViewerVersions([]) }
    } catch { /* ignore */ }
  }

  async function downloadFile(fileId, filename) {
    try {
      const r = await fetch(`/api/files/${fileId}/download`, { headers: authHeaders })
      if (!r.ok) return
      const blob = await r.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  async function saveFileEdit(fileId, content) {
    setViewerSaving(true)
    try {
      const r = await fetch(`/api/files/${fileId}/content`, {
        method:'PUT', headers:{...authHeaders,'Content-Type':'application/json'},
        body: JSON.stringify({ content }),
      })
      if (r.ok) {
        setFileViewer(prev => ({ ...prev, content }))
        setViewerTab('view')
        await loadLibFiles()
      }
    } catch { /* ignore */ } finally { setViewerSaving(false) }
  }

  async function loadFileVersions(fileId) {
    setViewerVerLoading(true)
    try {
      const r = await fetch(`/api/files/${fileId}/versions`, { headers: authHeaders })
      if (r.ok) setViewerVersions(await r.json())
    } catch { /* ignore */ } finally { setViewerVerLoading(false) }
  }

  async function restoreFileVersion(fileId, versionId) {
    try {
      const r = await fetch(`/api/files/${fileId}/versions/${versionId}/restore`, { method:'POST', headers: authHeaders })
      if (!r.ok) return
      const content_r = await fetch(`/api/files/${fileId}/content`, { headers: authHeaders })
      if (content_r.ok) { const d = await content_r.json(); setFileViewer(prev => ({ ...prev, content: d.content })) }
      setViewerTab('view')
      await loadFileVersions(fileId)
    } catch { /* ignore */ }
  }

  async function commitRename(fileId) {
    const name = renameVal.trim(); if (!name) { setRenameId(null); return }
    try {
      const r = await fetch(`/api/files/${fileId}/rename`, {
        method:'PATCH', headers:{...authHeaders,'Content-Type':'application/json'},
        body: JSON.stringify({ filename: name }),
      })
      if (r.ok) await loadLibFiles()
    } catch { /* ignore */ } finally { setRenameId(null) }
  }

  function startStatusStream(fileId) {
    if (statusStreamsRef.current[fileId]) return
    const ctrl = new AbortController()
    statusStreamsRef.current[fileId] = ctrl
    ;(async () => {
      try {
        const res = await fetch(`/api/files/${fileId}/status/stream`, { headers: authHeaders, signal: ctrl.signal })
        if (!res.ok) return
        const reader = res.body.getReader()
        const dec = new TextDecoder()
        let buf = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n'); buf = lines.pop()
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const { id, status } = JSON.parse(line.slice(6))
              setLibFiles(prev => prev.map(f => f.id === id ? { ...f, status } : f))
            } catch { /* ignore malformed */ }
          }
        }
      } catch { /* aborted or network error */ } finally {
        delete statusStreamsRef.current[fileId]
      }
    })()
  }

  useEffect(() => {
    if (!filesOpen) {
      Object.values(statusStreamsRef.current).forEach(ctrl => ctrl.abort())
      statusStreamsRef.current = {}
      return
    }
    libFiles.filter(f => f.status === 'processing').forEach(f => startStatusStream(f.id))
  }, [filesOpen, libFiles])

  const attachedIds = useMemo(() => new Set(attachedFiles.map(f => f.id)), [attachedFiles])

  function statusColor(s) {
    if (s === 'ready')      return { bg:'rgba(52,211,153,0.15)', color:'#34d399' }
    if (s === 'processing') return { bg:'rgba(251,191,36,0.15)',  color:'#fbbf24' }
    if (s === 'error')      return { bg:'rgba(248,113,113,0.15)', color:'#f87171' }
    return { bg:'rgba(100,116,139,0.15)', color:'#64748b' }
  }

  return {
    filesOpen, setFilesOpen,
    filesTab, setFilesTab,
    fileViewer, setFileViewer,
    libFiles,
    attachedFiles, setAttachedFiles,
    fileUploading,
    urlIngest, setUrlIngest,
    urlIngesting,
    renameId, setRenameId,
    renameVal, setRenameVal,
    viewerTab, setViewerTab,
    viewerEdit, setViewerEdit,
    viewerSaving,
    viewerVersions,
    viewerVerLoading,
    fileInputRef,
    statusStreamsRef,
    attachedIds,
    startStatusStream,
    uploadFile,
    ingestUrl,
    attachFile,
    detachFile,
    deleteFile,
    viewFile,
    downloadFile,
    saveFileEdit,
    loadFileVersions,
    restoreFileVersion,
    commitRename,
    loadLibFiles,
    loadAttachedFiles,
    statusColor,
  }
}
