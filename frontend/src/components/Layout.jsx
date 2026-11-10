import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ClipboardList, History, House, Languages, LogOut, Search, Briefcase } from 'lucide-react'
import { useAuth } from '../lib/auth.jsx'
import { useLang } from '../lib/i18n.jsx'
import { ErrorBanner, cx } from './ui.jsx'

export function LangToggle({ className }) {
  const { lang, setLang } = useLang()
  return (
    <button type="button" onClick={() => setLang(lang === 'ur' ? 'en' : 'ur')}
      className={cx('inline-flex min-h-11 items-center gap-2 rounded-full bg-white/15 px-3 text-sm font-bold', className)}>
      <Languages className="size-5" aria-hidden />
      {lang === 'ur' ? 'English' : 'اردو'}
    </button>
  )
}

const TABS = {
  worker: [
    { to: '/w', icon: House, label: 'nav_home', end: true },
    { to: '/w/board', icon: Briefcase, label: 'nav_jobs' },
    { to: '/w/bookings', icon: History, label: 'nav_history' },
  ],
  customer: [
    { to: '/c', icon: Search, label: 'nav_find', end: true },
    { to: '/c/requests', icon: ClipboardList, label: 'nav_requests' },
  ],
}

export default function Layout({ role }) {
  const { t } = useLang()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [leaving, setLeaving] = useState(false)
  const [logoutError, setLogoutError] = useState(null)

  async function signOut() {
    setLeaving(true)
    setLogoutError(null)
    try {
      await logout() // resolves only after Django answers 204
      navigate('/', { replace: true, state: { notice: 'logged_out' } })
    } catch (e) {
      setLogoutError(e)
    } finally {
      setLeaving(false)
    }
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-20 bg-brand text-white shadow">
        <div className="mx-auto flex max-w-md items-center justify-between gap-2 px-4 py-2">
          <div className="flex items-center gap-2">
            <span className="size-3 rounded-full bg-sun" aria-hidden />
            <span className="text-lg font-bold">{t('app_name')}</span>
          </div>
          <div className="flex items-center gap-2">
            <LangToggle />
            {user && (
              <button type="button" aria-label={t('logout')} title={t('logout')}
                onClick={signOut} disabled={leaving} aria-busy={leaving || undefined}
                className="inline-flex min-h-11 items-center gap-1 rounded-full bg-white/15 px-3 text-sm disabled:opacity-60">
                <LogOut className="size-5" aria-hidden /><span className="sr-only sm:not-sr-only">{t('logout')}</span>
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-md space-y-4 px-4 pt-4 pb-28">
        {logoutError && <ErrorBanner error={logoutError} onRetry={signOut} />}
        <Outlet />
      </main>
      {TABS[role] && (
        <nav className="fixed inset-x-0 bottom-0 z-20 border-t border-brand/10 bg-white pb-[env(safe-area-inset-bottom)]">
          <div className="mx-auto grid max-w-md" style={{ gridTemplateColumns: `repeat(${TABS[role].length}, 1fr)` }}>
            {TABS[role].map(({ to, icon: Icon, label, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) => cx('flex min-h-16 flex-col items-center justify-center gap-0.5 text-sm',
                  isActive ? 'font-bold text-brand' : 'text-gray-500')}>
                <Icon className="size-6" aria-hidden />
                {t(label)}
              </NavLink>
            ))}
          </div>
        </nav>
      )}
    </div>
  )
}
