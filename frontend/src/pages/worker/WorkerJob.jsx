import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { MapPin, Minus, Plus, Send } from 'lucide-react'
import { AudioPlayer, Button, Card, Chip, ErrorBanner, Heading, LinkButton, Spinner, StatusBadge, TradeIcon } from '../../components/ui.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'
import { money } from '../../lib/format.js'

const PRESETS = [500, 1000, 1500, 2000, 3000, 5000]
const MESSAGES = ['msg_today', 'msg_hour', 'msg_tomorrow', 'msg_materials']

/** Quote with taps: preset amounts, +/- 100 steps, and preset messages. Typing is optional. */
function QuoteForm({ jobId, onSent }) {
  const { t } = useLang()
  const [amount, setAmount] = useState(1500)
  const [msgKey, setMsgKey] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function send() {
    setBusy(true)
    setError(null)
    try {
      await api(`/job-requests/${jobId}/quotes/`, { method: 'POST',
        json: { amount: amount.toFixed(2), message: msgKey ? t(msgKey) : '' } })
      onSent()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-4">
      <Heading speak={t('quote_amount')}>{t('quote_amount')}</Heading>
      <div className="flex items-center justify-between gap-3" dir="ltr">
        <button type="button" aria-label="-100" onClick={() => setAmount((a) => Math.max(100, a - 100))}
          className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 ring-1 ring-brand/20"><Minus className="size-6" /></button>
        <label className="flex-1">
          <span className="sr-only">PKR</span>
          <input inputMode="numeric" value={amount} aria-label="PKR" data-testid="quote-amount"
            onChange={(e) => setAmount(Number(e.target.value.replace(/\D/g, '')) || 0)}
            className="num w-full rounded-2xl border-2 border-brand/15 py-2 text-center text-3xl font-bold" />
        </label>
        <button type="button" aria-label="+100" onClick={() => setAmount((a) => a + 100)}
          className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 ring-1 ring-brand/20"><Plus className="size-6" /></button>
      </div>
      <div className="grid grid-cols-3 gap-2" dir="ltr">
        {PRESETS.map((p) => <Chip key={p} selected={amount === p} onClick={() => setAmount(p)}><span className="num">{p}</span></Chip>)}
      </div>
      <p className="font-bold text-brand">{t('quote_message')}</p>
      <div className="flex flex-wrap gap-2">
        {MESSAGES.map((k) => <Chip key={k} selected={msgKey === k} onClick={() => setMsgKey(msgKey === k ? null : k)}>{t(k)}</Chip>)}
      </div>
      <ErrorBanner error={error} />
      {error?.field('amount') && <p className="text-red-700">{error.field('amount')}</p>}
      <Button variant="sun" icon={Send} busy={busy} disabled={amount < 1} onClick={send}>
        {t('send_quote')} · <span className="num">{money(amount)}</span>
      </Button>
    </Card>
  )
}

export default function WorkerJob() {
  const { id } = useParams()
  const { t, name } = useLang()
  const { data: job, error, loading, reload } = useApi(`/job-requests/${id}/`, { poll: 15000 })

  if (loading && !job) return <Spinner />
  if (!job) return <ErrorBanner error={error} onRetry={reload} />

  return (
    <div className="space-y-4">
      <Card className="space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <TradeIcon iconKey={job.trade.icon_key} className="size-9 text-brand" />
            <div>
              <p className="text-lg font-bold">{name(job.trade)}</p>
              {job.specialty && <p>{name(job.specialty)}</p>}
            </div>
          </div>
          <StatusBadge status={job.status} />
        </div>
        <p className="flex items-center gap-1 text-gray-600"><MapPin className="size-5" aria-hidden />
          <span className="num">{job.service_area.sector_code}</span>، {job.service_area.city}</p>
        {job.description && <p className="text-lg">{job.description}</p>}
        {job.has_voice_note && <AudioPlayer url={job.voice_note_url} />}
        {job.address_details && <p className="rounded-2xl bg-brand-50 p-3">{t('address')}: {job.address_details}</p>}
      </Card>

      {job.my_quote ? (
        <Card className="space-y-2">
          <p className="font-bold">{t('your_quote')}</p>
          <p className="num text-3xl font-bold text-brand">{money(job.my_quote.amount)}</p>
          {job.my_quote.message && <p>{job.my_quote.message}</p>}
          <p>{t(`q_${job.my_quote.status}`)}</p>
        </Card>
      ) : job.status === 'OPEN' && <QuoteForm jobId={job.id} onSent={() => reload()} />}

      {job.booking && job.viewer === 'assigned_worker' && (
        <LinkButton to={`/w/bookings/${job.booking.id}`} variant="sun">{t('go_to_booking')}</LinkButton>
      )}
    </div>
  )
}
