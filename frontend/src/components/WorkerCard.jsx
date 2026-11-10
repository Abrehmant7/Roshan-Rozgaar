import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useLang } from '../lib/i18n.jsx'
import { RatingLine, VerifiedBadge } from './ui.jsx'

export default function WorkerCard({ worker, to, children }) {
  const { t } = useLang()
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-lg font-bold">{worker.display_name}</p>
          <VerifiedBadge />
        </div>
        {worker.matches_specialty && (
          <span className="inline-flex items-center gap-1 rounded-full bg-sun-100 px-2 text-sm"><Sparkles className="size-4" aria-hidden />{t('matches_skill')}</span>
        )}
        {worker.is_available === false && <span className="rounded-full bg-gray-200 px-2 text-sm">{t('worker_busy')}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <RatingLine rating={worker.rating} completed={worker.completed_jobs} />
        <span className="text-sm text-gray-600"><span className="num">{worker.experience_years}</span> {t('exp_years')}</span>
      </div>
      {children}
    </>
  )
  const cls = 'block space-y-2 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-brand/10'
  return to ? <Link to={to} className={`${cls} active:bg-brand-50`} data-testid="worker-card">{body}</Link>
    : <div className={cls} data-testid="worker-card">{body}</div>
}
