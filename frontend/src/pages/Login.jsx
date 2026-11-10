import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { LogIn } from 'lucide-react'
import { Button, Card, ErrorBanner, Heading } from '../components/ui.jsx'
import { homeFor, useAuth } from '../lib/auth.jsx'
import { useLang } from '../lib/i18n.jsx'

export function TextField({ label, error, name, ...props }) {
  const msg = error?.field?.(name)
  return (
    <label className="block space-y-1">
      <span className="font-bold text-brand">{label}</span>
      <input name={name} {...props}
        className="block min-h-14 w-full rounded-2xl border-2 border-brand/15 bg-white px-4 text-lg focus:border-brand" />
      {msg && <span className="block text-sm text-red-700">{msg}</span>}
    </label>
  )
}

export default function Login() {
  const { t } = useLang()
  const { login } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const role = params.get('role') === 'worker' ? 'worker' : 'customer'
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const user = await login(form.username.trim(), form.password)
      if (user.role !== role) setNotice(t(role === 'worker' ? 'wrong_role_worker' : 'wrong_role_customer'))
      const next = params.get('next')
      navigate(next && next.startsWith(`/${user.role === 'worker' ? 'w' : 'c'}`) ? next : homeFor(user), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const title = t(role === 'worker' ? 'worker_login_title' : 'customer_login_title')
  return (
    <form onSubmit={submit} className="space-y-4">
      <Heading speak={role === 'worker' ? `${title}. ${t('worker_login_note')}` : null}>{title}</Heading>
      {role === 'worker' && <p className="text-brand/80">{t('worker_login_note')}</p>}
      <Card className="space-y-4">
        <TextField label={t('username')} name="username" autoComplete="username" autoCapitalize="none" required
          value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} error={error} />
        <TextField label={t('password')} name="password" type="password" autoComplete="current-password" required
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} error={error} />
        <ErrorBanner error={error} />
        {notice && <p className="text-amber-800">{notice}</p>}
        <Button type="submit" icon={LogIn} busy={busy}>{t('login')}</Button>
      </Card>
      <p className="text-center">
        {t('no_account')}{' '}
        <Link className="font-bold text-brand underline" to={role === 'worker' ? '/register?role=worker' : '/register'}>
          {t(role === 'worker' ? 'create_worker_account' : 'register')}
        </Link>
      </p>
    </form>
  )
}
