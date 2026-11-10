import { Link } from 'react-router-dom'
import { Empty, ErrorBanner, Heading, Spinner, StatusBadge, TradeIcon } from '../../components/ui.jsx'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'
import { money, when } from '../../lib/format.js'

/** Booking history for either role. */
export function BookingList({ base }) {
  const { t, name, lang } = useLang()
  const { data, error, loading, reload } = useApi('/bookings/?page_size=50')
  if (loading && !data) return <Spinner />
  return (
    <div className="space-y-3">
      <ErrorBanner error={error} onRetry={reload} />
      {data?.results.length === 0 && <Empty>{t('history_empty')}</Empty>}
      {data?.results.map((b) => (
        <Link key={b.id} to={`${base}/${b.id}`} className="flex items-center gap-3 rounded-3xl bg-white p-4 ring-1 ring-brand/10">
          <TradeIcon iconKey={b.job_request.trade.icon_key} className="size-8 text-brand" />
          <div className="flex-1">
            <p className="font-bold">{name(b.job_request.trade)} · <span className="num">{b.job_request.service_area.sector_code}</span></p>
            <p className="text-sm text-gray-600">{when(b.booked_at, lang)}</p>
          </div>
          <div className="space-y-1 text-end">
            <StatusBadge status={b.status} />
            <p className="num font-bold">{money(b.amount)}</p>
          </div>
        </Link>
      ))}
    </div>
  )
}

export default function WorkerBookings() {
  const { t } = useLang()
  return (
    <div className="space-y-4">
      <Heading speak={t('nav_history')}>{t('nav_history')}</Heading>
      <BookingList base="/w/bookings" />
    </div>
  )
}
