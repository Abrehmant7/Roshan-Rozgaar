import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { UserPlus } from 'lucide-react'
import { Button, Card, ErrorBanner, Heading } from '../components/ui.jsx'
import { useAuth } from '../lib/auth.jsx'
import { useLang } from '../lib/i18n.jsx'
import { TextField } from './Login.jsx'

/** Sign-up for either role. The server assigns the role from the endpoint, never from the form. */
export default function Register() {
  const { t } = useLang()
  const { register } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const role = params.get('role') === 'worker' ? 'worker' : 'customer'
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(form.username.trim(), form.password, role)
      navigate(role === 'worker' ? '/w/onboard' : '/c', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Heading speak={role === 'worker' ? t('worker_register_note') : null}>
        {t(role === 'worker' ? 'worker_register_title' : 'register')}
      </Heading>
      {role === 'worker' && <p className="text-brand/80">{t('worker_register_note')}</p>}
      <Card className="space-y-4">
        <TextField label={t('username')} name="username" autoComplete="username" autoCapitalize="none" required
          value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} error={error} />
        <TextField label={t('password')} name="password" type="password" autoComplete="new-password" required
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} error={error} />
        {!error?.fields && <ErrorBanner error={error} />}
        <Button type="submit" icon={UserPlus} busy={busy}>{t('register')}</Button>
      </Card>
      <p className="text-center">{t('have_account')} <Link className="font-bold text-brand underline" to={`/login?role=${role}`}>{t('login')}</Link></p>
    </form>
  )
}
