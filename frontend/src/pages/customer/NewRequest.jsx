import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Send } from 'lucide-react'
import CatalogPicker, { pickerFromParams } from '../../components/CatalogPicker.jsx'
import Recorder from '../../components/Recorder.jsx'
import { Button, Card, ErrorBanner, FieldErrors, Heading, Spinner } from '../../components/ui.jsx'
import { api } from '../../lib/api.js'
import { useCatalog } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'

export default function NewRequest() {
  const { t } = useLang()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { trades, areas, error: catalogError } = useCatalog()
  const [pick, setPick] = useState(() => pickerFromParams(params))
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  const [voice, setVoice] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (catalogError) return <ErrorBanner error={catalogError} />
  if (!trades) return <Spinner />

  const hasContent = description.trim() || voice
  const ready = pick.trade && pick.area && hasContent

  async function submit() {
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('trade', pick.trade)
    form.append('service_area', pick.area)
    if (pick.specialty) form.append('specialty', pick.specialty)
    form.append('description', description.trim())
    form.append('address_details', address.trim())
    if (voice) form.append('voice_note', voice, voice.name || 'voice.webm')
    try {
      const job = await api('/job-requests/', { method: 'POST', form })
      navigate(`/c/requests/${job.id}`, { replace: true })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <Heading speak={t('post_request')}>{t('post_request')}</Heading>
      <CatalogPicker trades={trades} areas={areas} value={pick} onChange={setPick} />
      <Card className="space-y-3">
        <h2 className="font-bold text-brand">{t('describe')}</h2>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={1000}
          aria-label={t('describe')} placeholder={t('describe_hint')} className="w-full rounded-2xl border-2 border-brand/15 p-3 text-lg" />
        <Recorder value={voice} onChange={setVoice} />
      </Card>
      <Card className="space-y-2">
        <h2 className="font-bold text-brand">{t('address_label')} <span className="font-normal text-gray-500">({t('optional')})</span></h2>
        <textarea value={address} onChange={(e) => setAddress(e.target.value)} rows={2} maxLength={300}
          aria-label={t('address_label')} className="w-full rounded-2xl border-2 border-brand/15 p-3" />
        <p className="text-sm text-gray-600">{t('address_hint')}</p>
      </Card>
      {!hasContent && <p className="text-amber-800">{t('need_text_or_voice')}</p>}
      {error?.fields ? <FieldErrors error={error} /> : <ErrorBanner error={error} />}
      <Button variant="sun" icon={Send} busy={busy} disabled={!ready} onClick={submit}>{t('send_request')}</Button>
    </div>
  )
}
