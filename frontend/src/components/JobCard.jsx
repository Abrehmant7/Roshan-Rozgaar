import { Link } from 'react-router-dom'
import { MapPin, Mic } from 'lucide-react'
import { useLang } from '../lib/i18n.jsx'
import { money, when } from '../lib/format.js'
import { StatusBadge, TradeIcon } from './ui.jsx'

/** Summary of a job request for lists (worker board, customer requests). */
export default function JobCard({ job, to, extra }) {
  const { t, name, lang } = useLang()
  return (
    <Link to={to} className="block space-y-2 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-brand/10 active:bg-brand-50" data-testid="job-card">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-brand-100 text-brand">
            <TradeIcon iconKey={job.trade.icon_key} className="size-7" />
          </span>
          <div>
            <p className="font-bold">{name(job.trade)}{job.specialty && <span className="font-normal"> · {name(job.specialty)}</span>}</p>
            <p className="flex items-center gap-1 text-sm text-gray-600">
              <MapPin className="size-4" aria-hidden /><span className="num">{job.service_area.sector_code}</span>
              <span>· {when(job.created_at, lang)}</span>
            </p>
          </div>
        </div>
        <StatusBadge status={job.status} />
      </div>
      {job.description && <p className="line-clamp-2">{job.description}</p>}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {job.has_voice_note && (
          <span className="inline-flex items-center gap-1 rounded-full bg-sun-100 px-2 py-0.5"><Mic className="size-4" aria-hidden />{t('voice_note')}</span>
        )}
        {job.my_quote && (
          <span className="rounded-full bg-brand-100 px-2 py-0.5">{t('your_quote')}: <span className="num">{money(job.my_quote.amount)}</span> · {t(`q_${job.my_quote.status}`)}</span>
        )}
        {extra}
      </div>
    </Link>
  )
}
