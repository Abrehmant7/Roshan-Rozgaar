import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Trash2, Upload } from 'lucide-react'
import { useLang } from '../lib/i18n.jsx'
import { Button } from './ui.jsx'

const MAX_SECONDS = 120
const TYPES = [['audio/webm;codecs=opus', 'webm'], ['audio/webm', 'webm'], ['audio/mp4', 'm4a'], ['audio/ogg;codecs=opus', 'ogg']]

function pickType() {
  if (!window.MediaRecorder?.isTypeSupported) return ['', 'webm']
  return TYPES.find(([type]) => MediaRecorder.isTypeSupported(type)) || ['', 'webm']
}

/**
 * Voice note input. Records with the microphone where allowed; always offers an
 * audio-file fallback, and explains when permission is denied or unsupported.
 */
export default function Recorder({ value, onChange }) {
  const { t } = useLang()
  const supported = Boolean(navigator.mediaDevices?.getUserMedia && window.MediaRecorder)
  const [state, setState] = useState('idle') // idle | recording
  const [seconds, setSeconds] = useState(0)
  const [problem, setProblem] = useState(supported ? null : 'mic_unsupported')
  const [preview, setPreview] = useState(null)
  const recorder = useRef(null)
  const timer = useRef(null)
  const fileInput = useRef(null)

  useEffect(() => {
    if (!value) { setPreview(null); return undefined }
    const url = URL.createObjectURL(value)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [value])

  useEffect(() => () => {
    clearInterval(timer.current)
    recorder.current?.stream?.getTracks().forEach((track) => track.stop())
  }, [])

  async function start() {
    setProblem(null)
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch (e) {
      setProblem(e?.name === 'NotAllowedError' || e?.name === 'SecurityError' ? 'mic_denied' : 'mic_unsupported')
      return
    }
    const [mimeType, ext] = pickType()
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks = []
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data)
    rec.onstop = () => {
      stream.getTracks().forEach((track) => track.stop())
      clearInterval(timer.current)
      setState('idle')
      const blob = new Blob(chunks, { type: rec.mimeType || mimeType || 'audio/webm' })
      if (blob.size) onChange(new File([blob], `voice.${ext}`, { type: blob.type }))
    }
    recorder.current = rec
    rec.start()
    setSeconds(0)
    setState('recording')
    timer.current = setInterval(() => setSeconds((s) => {
      if (s + 1 >= MAX_SECONDS) rec.state === 'recording' && rec.stop()
      return s + 1
    }), 1000)
  }

  const stop = () => recorder.current?.state === 'recording' && recorder.current.stop()
  const mmss = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`

  return (
    <div className="space-y-2" data-testid="recorder">
      {state === 'recording' ? (
        <Button variant="danger" icon={Square} onClick={stop}>
          {t('stop')} · <span className="num">{mmss}</span> <span className="ms-2 inline-block size-3 animate-pulse rounded-full bg-red-600" aria-label={t('recording')} />
        </Button>
      ) : value ? (
        <div className="space-y-2 rounded-2xl bg-sun-100 p-3">
          {preview && <audio controls src={preview} className="w-full" />}
          <Button variant="secondary" icon={Trash2} onClick={() => onChange(null)}>{t('delete_recording')}</Button>
        </div>
      ) : supported && (
        <Button variant="sun" icon={Mic} onClick={start}>{t('record')}</Button>
      )}
      {problem && <p role="alert" className="rounded-2xl bg-amber-50 p-3 text-amber-900">{t(problem)}</p>}
      {!value && state !== 'recording' && (
        <>
          <input ref={fileInput} type="file" accept="audio/*" className="sr-only" data-testid="audio-file"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onChange(f); e.target.value = '' }} />
          <Button variant="ghost" icon={Upload} onClick={() => fileInput.current?.click()}>{t('choose_audio')}</Button>
        </>
      )}
    </div>
  )
}
