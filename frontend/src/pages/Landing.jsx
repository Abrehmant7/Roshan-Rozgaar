import { Link, useLocation } from 'react-router-dom'
import { CircleCheck, Hammer, Search } from 'lucide-react'
import { Speak } from '../components/ui.jsx'
import { useLang } from '../lib/i18n.jsx'

function RoleCard({ to, icon: Icon, title, sub, tone }) {
  return (
    <Link to={to} className={`flex min-h-36 items-center gap-4 rounded-3xl p-5 shadow-sm ${tone}`}>
      <span className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-white/20">
        <Icon className="size-9" aria-hidden />
      </span>
      <span>
        <span className="block text-2xl font-bold">{title}</span>
        <span className="block opacity-90">{sub}</span>
      </span>
    </Link>
  )
}

export default function Landing() {
  const { t } = useLang()
  const location = useLocation()
  return (
    <div className="space-y-5 pt-4">
      {location.state?.notice === 'logged_out' && (
        <p role="status" className="flex items-center gap-2 rounded-2xl bg-brand-100 p-3 text-brand" data-testid="logged-out">
          <CircleCheck className="size-6" aria-hidden />{t('logged_out')}
        </p>
      )}
      <div className="space-y-1 text-center">
        <h1 className="text-3xl font-bold text-brand">{t('app_name')}</h1>
        <p className="text-brand/80">{t('tagline')}</p>
      </div>
      <div className="flex justify-end"><Speak text={`${t('i_am_worker')}. ${t('i_need_worker')}`} /></div>
      <RoleCard to="/login?role=worker" icon={Hammer} title={t('i_am_worker')} sub={t('i_am_worker_sub')} tone="bg-brand text-white" />
      <RoleCard to="/login?role=customer" icon={Search} title={t('i_need_worker')} sub={t('i_need_worker_sub')} tone="bg-sun text-ink" />
    </div>
  )
}
