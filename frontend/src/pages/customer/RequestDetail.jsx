import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { CircleCheck, MapPin } from 'lucide-react'
import WorkerCard from '../../components/WorkerCard.jsx'
import {
  AudioPlayer, Button, Card, Empty, ErrorBanner, LinkButton, Spinner, StatusBadge, TradeIcon,
} from '../../components/ui.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'
import { money, when } from '../../lib/format.js'

export default function RequestDetail() {
  const { id } = useParams()
  const { t, name, lang } = useLang()
  const navigate = useNavigate()
  const { data: job, error, loading, reload } = useApi(`/job-requests/${id}/`, { poll: 8000 })
  const [accepting, setAccepting] = useState(null)
  const [acceptError, setAcceptError] = useState(null)

  if (loading && !job) return <Spinner />
  if (!job) return <ErrorBanner error={error} onRetry={reload} />

  async function accept(quoteId) {
    setAccepting(quoteId)
    setAcceptError(null)
    try {
      const booking = await api(`/quotes/${quoteId}/accept/`, { method: 'POST' })
      navigate(`/c/bookings/${booking.id}`)
    } catch (e) {
      setAcceptError(e)
      reload({ quiet: true })
    } finally {
      setAccepting(null)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-2">
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
          <span className="num">{job.service_area.sector_code}</span>، {job.service_area.city} · {when(job.created_at, lang)}</p>
        {job.description && <p className="text-lg">{job.description}</p>}
        {job.has_voice_note && <AudioPlayer url={job.voice_note_url} />}
        {job.address_details && <p className="rounded-2xl bg-brand-50 p-3">{t('address')}: {job.address_details}</p>}
      </Card>

      {job.booking ? (
        <Card className="space-y-2 ring-2 ring-sun">
          <p className="flex items-center gap-2 font-bold"><CircleCheck className="size-6 text-brand" aria-hidden />{t('booked_with')}</p>
          <p className="num text-2xl font-bold text-brand">{money(job.booking.amount)}</p>
          <LinkButton to={`/c/bookings/${job.booking.id}`} variant="sun">{t('go_to_booking')}</LinkButton>
        </Card>
      ) : (
        <section className="space-y-3" aria-live="polite">
          <h2 className="text-xl font-bold text-brand">{t('quotes')} (<span className="num">{job.quotes.length}</span>)</h2>
          <ErrorBanner error={acceptError} />
          {job.quotes.length === 0 && <Empty>{t('no_quotes')}</Empty>}
          {job.quotes.map((q) => (
            <WorkerCard key={q.id} worker={q.worker}>
              <div className="flex items-center justify-between gap-3 border-t border-brand/10 pt-2">
                <span className="num text-2xl font-bold text-brand" data-testid="quote-amount">{money(q.amount)}</span>
                {q.message && <span className="text-sm">{q.message}</span>}
              </div>
              <Button variant="sun" icon={CircleCheck} busy={accepting === q.id}
                disabled={accepting !== null || !q.worker.is_available || q.worker_eligible === false}
                onClick={() => accept(q.id)}>
                {q.worker_eligible === false ? t('quote_stale') : q.worker.is_available ? t('accept') : t('worker_busy')}
              </Button>
            </WorkerCard>
          ))}
        </section>
      )}
    </div>
  )
}
