import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { CircleCheck, Flag, KeyRound, MapPin, ShieldCheck } from 'lucide-react'
import {
  AudioPlayer, Button, Card, Chip, ErrorBanner, FieldErrors, Heading, PinPad, RatingLine, Spinner, Stars,
  StatusBadge, TradeIcon, VerifiedBadge, cx,
} from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { cached, useApi } from '../lib/hooks.js'
import { useLang } from '../lib/i18n.jsx'
import { money, timeOnly } from '../lib/format.js'

const STEPS = [['BOOKED', 'step_booked'], ['IN_PROGRESS', 'step_arrived'], ['COMPLETED', 'step_done']]

function Steps({ status }) {
  const { t } = useLang()
  const at = STEPS.findIndex(([s]) => s === status)
  return (
    <ol className="grid grid-cols-3 gap-2 text-center text-sm">
      {STEPS.map(([s, label], i) => (
        <li key={s} className={cx('rounded-2xl p-2', i <= at ? 'bg-brand text-white' : 'bg-white text-gray-500 ring-1 ring-brand/10')}>
          {i < at ? <CircleCheck className="mx-auto size-5" aria-hidden /> : <span className="num">{i + 1}</span>}
          <span className="block">{t(label)}</span>
        </li>
      ))}
    </ol>
  )
}

function IssuePin({ bookingId, activePin, onDone }) {
  const { t, lang } = useLang()
  const [pin, setPin] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function issue() {
    setBusy(true)
    setError(null)
    try {
      const res = await api(`/bookings/${bookingId}/pin/`, { method: 'POST' })
      setPin(res)
      onDone()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  return (
    <Card className="space-y-3">
      {pin ? (
        <div className="space-y-2 text-center" data-testid="issued-pin">
          <p className="font-bold">{t('pin_title')}</p>
          <p className="num text-5xl font-bold tracking-[0.3em] text-brand">{pin.pin}</p>
          <p className="text-sm text-gray-600">{t('pin_expires')}: <span className="num">{timeOnly(pin.expires_at, lang)}</span></p>
        </div>
      ) : activePin ? (
        <p className="text-brand">{t('pin_active')} · {t('pin_expires')}: <span className="num">{timeOnly(activePin.expires_at, lang)}</span></p>
      ) : null}
      <ErrorBanner error={error} />
      <Button variant={pin ? 'secondary' : 'sun'} icon={KeyRound} busy={busy} onClick={issue}>
        {pin || activePin ? t('new_pin') : t('issue_pin')}
      </Button>
    </Card>
  )
}

function CheckIn({ bookingId, onDone }) {
  const { t } = useLang()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  return (
    <Card className="space-y-3">
      <Heading speak={t('enter_pin')}>{t('check_in')}</Heading>
      <p>{t('enter_pin')}</p>
      <PinPad busy={busy} label={t('check_in')} onSubmit={async (pin, clear) => {
        setBusy(true)
        setError(null)
        try {
          await api(`/bookings/${bookingId}/check-in/`, { method: 'POST', json: { pin } })
          onDone()
        } catch (e) { setError(e); clear() } finally { setBusy(false) }
      }} />
      <ErrorBanner error={error} />
    </Card>
  )
}

function Complete({ bookingId, onDone }) {
  const { t } = useLang()
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  return (
    <Card className="space-y-3">
      {confirm && <p className="text-lg font-bold">{t('confirm_complete')}</p>}
      <ErrorBanner error={error} />
      <Button variant="sun" icon={CircleCheck} busy={busy} onClick={async () => {
        if (!confirm) { setConfirm(true); return }
        setBusy(true)
        setError(null)
        try { await api(`/bookings/${bookingId}/complete/`, { method: 'POST' }); onDone() } catch (e) { setError(e) } finally { setBusy(false) }
      }}>{t('complete_job')}</Button>
      {confirm && <Button variant="secondary" onClick={() => setConfirm(false)}>{t('cancel')}</Button>}
    </Card>
  )
}

function ReviewForm({ bookingId, onDone }) {
  const { t, name } = useLang()
  const [tags, setTags] = useState([])
  const [form, setForm] = useState({ rating: 0, tags: [], text: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => { cached('/reviews/tags/').then(setTags).catch(() => {}) }, [])
  return (
    <Card className="space-y-3">
      <Heading speak={t('review_title')}>{t('review_title')}</Heading>
      <Stars value={form.rating} onChange={(rating) => setForm({ ...form, rating })} size="size-10" />
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <Chip key={tag.key} selected={form.tags.includes(tag.key)} onClick={() => setForm({ ...form,
            tags: form.tags.includes(tag.key) ? form.tags.filter((k) => k !== tag.key) : [...form.tags, tag.key] })}>{name(tag)}</Chip>
        ))}
      </div>
      <textarea value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} maxLength={500} rows={2}
        placeholder={`${t('review_text')} (${t('optional')})`} className="w-full rounded-2xl border-2 border-brand/15 p-3" />
      {error?.fields ? <FieldErrors error={error} /> : <ErrorBanner error={error} />}
      <Button variant="sun" busy={busy} disabled={!form.rating} onClick={async () => {
        setBusy(true)
        setError(null)
        try { await api(`/bookings/${bookingId}/review/`, { method: 'POST', json: form }); onDone() } catch (e) { setError(e) } finally { setBusy(false) }
      }}>{t('submit_review')}</Button>
    </Card>
  )
}

function ReportForm({ bookingId, onDone }) {
  const { t, name } = useLang()
  const [open, setOpen] = useState(false)
  const [reasons, setReasons] = useState([])
  const [form, setForm] = useState({ reason: null, details: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  useEffect(() => { if (open) cached('/reports/reasons/').then(setReasons).catch(() => {}) }, [open])
  if (!open) return <Button variant="ghost" icon={Flag} onClick={() => setOpen(true)}>{t('report')}</Button>
  return (
    <Card className="space-y-3 ring-red-200">
      <Heading speak={t('report_title')}>{t('report_title')}</Heading>
      <p className="flex items-center gap-2 text-sm text-gray-600"><ShieldCheck className="size-4" aria-hidden />{t('report_private')}</p>
      <div className="flex flex-wrap gap-2">
        {reasons.map((r) => <Chip key={r.key} selected={form.reason === r.key} onClick={() => setForm({ ...form, reason: r.key })}>{name(r)}</Chip>)}
      </div>
      <textarea value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} maxLength={1000} rows={2}
        placeholder={`${t('report_details')} (${t('optional')})`} className="w-full rounded-2xl border-2 border-brand/15 p-3" />
      <ErrorBanner error={error} />
      <div className="grid grid-cols-2 gap-2">
        <Button variant="secondary" onClick={() => setOpen(false)}>{t('cancel')}</Button>
        <Button variant="danger" busy={busy} disabled={!form.reason} onClick={async () => {
          setBusy(true)
          setError(null)
          try { await api(`/bookings/${bookingId}/reports/`, { method: 'POST', json: form }); onDone() } catch (e) { setError(e) } finally { setBusy(false) }
        }}>{t('submit_report')}</Button>
      </div>
    </Card>
  )
}

export default function BookingPage() {
  const { id } = useParams()
  const { t, name } = useLang()
  const { data: b, error, loading, reload } = useApi(`/bookings/${id}/`, { poll: 8000 })
  if (loading && !b) return <Spinner />
  if (!b) return <ErrorBanner error={error} onRetry={reload} />

  const job = b.job_request
  const done = () => reload({ quiet: true })
  const isCustomer = b.viewer === 'customer'

  return (
    <div className="space-y-4" data-testid="booking" data-status={b.status}>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-brand">{name(job.trade)}</h1>
        <StatusBadge status={b.status} />
      </div>
      <Steps status={b.status} />

      <Card className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-gray-600">{t('agreed_price')}</span>
          <span className="num text-2xl font-bold text-brand" data-testid="booking-amount">{money(b.amount)}</span>
        </div>
        {isCustomer ? (
          <div className="flex items-center justify-between">
            <span>{t('worker')}: <b>{b.worker.display_name}</b></span>
            <span className="flex flex-col items-end"><VerifiedBadge /><RatingLine rating={b.worker.rating} /></span>
          </div>
        ) : (
          <p>{t('customer')}: <b>{b.customer.username}</b></p>
        )}
        <p className="flex items-center gap-1 text-gray-700"><MapPin className="size-5" aria-hidden />
          <span className="num">{job.service_area.sector_code}</span>
          {job.specialty && <span>· {name(job.specialty)}</span>}
          <TradeIcon iconKey={job.trade.icon_key} className="ms-auto size-6 text-brand" /></p>
        {job.address_details && <p className="rounded-2xl bg-brand-50 p-3">{t('address')}: {job.address_details}</p>}
        {job.description && <p>{job.description}</p>}
        {job.has_voice_note && <AudioPlayer url={job.voice_note_url} />}
      </Card>

      {b.status === 'BOOKED' && !isCustomer && !b.actions.includes('check_in') && <p>{t('wait_checkin')}</p>}
      {b.status === 'BOOKED' && isCustomer && <p className="text-brand/80">{t('wait_checkin')}</p>}
      {b.status === 'IN_PROGRESS' && <p className="rounded-2xl bg-violet-50 p-3">{t('in_progress_note')}</p>}
      {b.status === 'COMPLETED' && <p className="rounded-2xl bg-brand-100 p-3 font-bold">{t('done_note')}</p>}

      {b.actions.includes('issue_pin') && <IssuePin bookingId={b.id} activePin={b.active_pin} onDone={done} />}
      {b.actions.includes('check_in') && <CheckIn bookingId={b.id} onDone={done} />}
      {b.actions.includes('complete') && <Complete bookingId={b.id} onDone={done} />}
      {b.actions.includes('review') && <ReviewForm bookingId={b.id} onDone={done} />}
      {b.review && (
        <Card className="space-y-1">
          <p className="font-bold">{t('your_review')}</p>
          <Stars value={b.review.rating} />
          {b.review.text && <p>{b.review.text}</p>}
        </Card>
      )}
      {b.my_report && <p className="rounded-2xl bg-gray-100 p-3">{t('report_sent')} · {t(`r_${b.my_report.status}`)}</p>}
      {b.actions.includes('report') && <ReportForm bookingId={b.id} onDone={done} />}
    </div>
  )
}
