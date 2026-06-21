import { useState, useCallback, useEffect, useRef } from 'react'

export default function useVoice(token, onTranscription) {
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [voiceAvailable, setVoiceAvailable] = useState(null)

  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)

  const authHeaders = { 'Authorization': `Bearer ${token}` }

  useEffect(() => {
    fetch('/api/transcribe', { method: 'POST', headers: authHeaders })
      .then(r => setVoiceAvailable(r.status !== 503))
      .catch(() => setVoiceAvailable(false))
  }, [])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []

      const rec = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      recorderRef.current = rec

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      rec.onstop = async () => {
        setRecording(false)
        setTranscribing(true)

        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const fd = new FormData()
        fd.append('file', blob, 'recording.webm')

        try {
          const r = await fetch('/api/transcribe', {
            method: 'POST', headers: authHeaders, body: fd,
          })
          if (r.ok) {
            const data = await r.json()
            if (data.text) onTranscription(data.text)
          } else if (r.status === 503) {
            setVoiceAvailable(false)
          }
        } catch { /* ignore */ } finally {
          setTranscribing(false)
        }
      }

      rec.start()
      setRecording(true)
    } catch { setVoiceAvailable(false) }
  }, [token])

  const stopRecording = useCallback(() => {
    if (recorderRef.current && recorderRef.current.state === 'recording') {
      recorderRef.current.stop()
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => {
      if (recorderRef.current && recorderRef.current.state === 'recording') {
        recorderRef.current.stop()
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  return { recording, transcribing, voiceAvailable, startRecording, stopRecording }
}
