import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, ChevronLeft, Pencil, UserPlus } from 'lucide-react'
import { Card, ErrorBanner, Heading, LinkButton, RatingLine, Spinner, StatusBadge, cx } from '../../components/ui.jsx'
import { api } from '../../lib/api.js'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'
import { money } from '../../lib/format.js'

function Toggle({ checked, onChange, busy, label }) {
  return (
    <button type="button" role="switch" aria-checked={checked} aria-label={label} disabled={busy} onClick={() => onChange(!checked)}
      className={cx('relative h-10 w-18 shrink-0 rounded-full transition', checked ? 'bg-brand' : 'bg-gray-300', busy && 'opacity-60')}>
      <span className={cx('absolute top-1 size-8 rounded-full bg-white shadow transition-all', checked ? 'start-9' : 'start-1')} />
    </button>
  )
}

export default function WorkerHome() {
  const { t } = useLang()
  const { data, error, loading, reload } = useApi('/workers/me/dashboard/', { poll: 10000 })
  const [busy, setBusy] = useState(false)
  const [toggleError, setToggleError] = useState(null)

  if (loading && !data) return <Spinner />
  if (error && !data) return <div data-testid="dashboard-error"><ErrorBanner error={error} onRetry={() => reload()} /></div>

  if (data.profile_status === 'missing') {
    return (
      <div className="space-y-4">
        <Heading speak={t('make_profile_note')}>{t('hello')}</Heading>
        <Card className="space-y-4 text-center">
          <UserPlus className="mx-auto size-14 text-brand" aria-hidden />
          <p className="text-lg">{t('make_profile_note')}</p>
          <LinkButton to="/w/onboard" variant="sun">{t('make_profile')}</LinkButton>
        </Card>
      </div>
    )
  }

  const busyOnJob = Boolean(data.active_booking)
  const statusKey = busyOnJob ? 'status_busy' : data.is_available ? 'status_available' : 'status_paused'

  async function setAccepting(value) {
    setBusy(true)
    setToggleError(null)
    try {
      await api('/workers/me/availability/', { method: 'PATCH', json: { accepting_jobs: value } })
      await reload({ quiet: true })
    } catch (e) {
      setToggleError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <div data-testid="stale-banner" className="space-y-1">
          <p className="text-sm text-amber-800">{t('stale_data')}</p>
          <ErrorBanner error={error} onRetry={() => reload()} />
        </div>
      )}
      <Heading speak={`${t('hello')} ${data.display_name}. ${t(statusKey)}`}>{t('hello')}، {data.display_name}</Heading>

      <Card className={cx('space-y-3', data.is_available ? 'bg-brand-100' : busyOnJob ? 'bg-sun-100' : 'bg-gray-100')}>
        <p className="text-lg font-bold" data-testid="availability-status">{t(statusKey)}</p>
        <div className="flex items-center justify-between gap-3">
          <span>{t('taking_jobs')}</span>
          <Toggle checked={Boolean(data.accepting_jobs)} onChange={setAccepting} busy={busy} label={t('taking_jobs')} />
        </div>
        <ErrorBanner error={toggleError} />
      </Card>

      {data.active_booking && (
        <Link to={`/w/bookings/${data.active_booking.id}`} className="block">
          <Card className="space-y-2 ring-2 ring-sun">
            <div className="flex items-center justify-between">
              <span className="font-bold">{t('active_job')}</span>
              <StatusBadge status={data.active_booking.status} />
            </div>
            <p className="line-clamp-2">{data.active_booking.job_request.description || t('voice_note')}</p>
            <p className="flex items-center justify-between font-bold text-brand">
              <span className="num">{money(data.active_booking.amount)}</span>
              <span className="inline-flex items-center gap-1">{t('open_job')} <ChevronLeft className="size-5 ltr:rotate-180" /></span>
            </p>
          </Card>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Card className="text-center">
          <p className="text-sm text-gray-500">{t('jobs_done')}</p>
          <p className="num text-3xl font-bold text-brand">{data.completed_jobs}</p>
        </Card>
        <Card className="text-center">
          <p className="text-sm text-gray-500">{t('rating')}</p>
          <div className="flex justify-center pt-2"><RatingLine rating={data.rating} /></div>
        </Card>
      </div>

      <LinkButton to="/w/board" icon={Briefcase}>
        {t('see_jobs')} (<span className="num">{data.open_jobs_matching}</span>)
      </LinkButton>
      {data.pending_quotes > 0 && (
        <p className="text-center text-brand/80">{t('pending_quotes')}: <span className="num">{data.pending_quotes}</span></p>
      )}

      {data.recent_jobs.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-bold text-brand">{t('recent_jobs')}</h2>
          {data.recent_jobs.map((j) => (
            <Link key={j.booking_id} to={`/w/bookings/${j.booking_id}`} className="flex items-center justify-between rounded-2xl bg-white p-3 ring-1 ring-brand/10">
              <StatusBadge status={j.status} />
              <span className="num font-bold">{money(j.amount)}</span>
              {j.rating != null && <span className="num">★ {j.rating}</span>}
            </Link>
          ))}
        </section>
      )}

      <LinkButton to="/w/onboard" variant="ghost" icon={Pencil}>{t('edit_profile')}</LinkButton>
    </div>
  )
}
