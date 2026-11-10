import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BadgeCheck, CircleCheck, Delete, Droplet, Hammer, Inbox, LoaderCircle, Paintbrush, Play, Snowflake,
  Star, TriangleAlert, Volume2, Wrench, Zap,
} from 'lucide-react'
import { fetchBlobUrl } from '../lib/api.js'
import { useLang } from '../lib/i18n.jsx'

export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

const VARIANTS = {
  primary: 'bg-brand text-white active:bg-brand-600 disabled:bg-brand/50',
  sun: 'bg-sun text-ink active:brightness-95 disabled:opacity-60',
  secondary: 'bg-white text-brand border-2 border-brand/20 active:bg-brand-50 disabled:opacity-60',
  danger: 'bg-white text-red-700 border-2 border-red-200 active:bg-red-50 disabled:opacity-60',
  ghost: 'text-brand underline-offset-4 hover:underline disabled:opacity-50',
}

export function Button({ variant = 'primary', busy = false, icon: Icon, className, children, disabled, ...props }) {
  return (
    <button
      type="button"
      {...props}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx(
        'inline-flex min-h-14 w-full items-center justify-center gap-3 rounded-2xl px-5 text-lg font-bold transition',
        VARIANTS[variant], className,
      )}
    >
      {busy ? <LoaderCircle className="size-6 animate-spin" aria-hidden /> : Icon && <Icon className="size-6 shrink-0" aria-hidden />}
      <span>{children}</span>
    </button>
  )
}

/** A navigation link styled as a big button (no button nested inside a link). */
export function LinkButton({ to, variant = 'primary', icon: Icon, className, children }) {
  return (
    <Link to={to} className={cx(
      'inline-flex min-h-14 w-full items-center justify-center gap-3 rounded-2xl px-5 text-lg font-bold transition',
      VARIANTS[variant], className,
    )}>
      {Icon && <Icon className="size-6 shrink-0" aria-hidden />}
      <span>{children}</span>
    </Link>
  )
}

export function Card({ className, children, ...props }) {
  return <section {...props} className={cx('rounded-3xl bg-white p-4 shadow-sm ring-1 ring-brand/10', className)}>{children}</section>
}

export function Spinner({ label }) {
  const { t } = useLang()
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-10 text-brand">
      <LoaderCircle className="size-7 animate-spin" aria-hidden />
      <span>{label || t('loading')}</span>
    </div>
  )
}

export function ErrorBanner({ error, onRetry }) {
  const { t, errorText } = useLang()
  if (!error) return null
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl bg-red-50 p-4 text-red-800 ring-1 ring-red-200">
      <TriangleAlert className="mt-1 size-6 shrink-0" aria-hidden />
      <div className="flex-1">
        <p>{errorText(error)}</p>
        {error.body?.attempts_remaining != null && (
          <p className="text-sm">{t('pin_attempts')}: <span className="num">{error.body.attempts_remaining}</span></p>
        )}
        {onRetry && <button type="button" onClick={onRetry} className="mt-1 font-bold underline">{t('retry')}</button>}
      </div>
    </div>
  )
}

/** All field errors of a failed form submit, as one list. */
export function FieldErrors({ error }) {
  if (!error?.fields) return null
  return (
    <ul role="alert" className="list-inside list-disc rounded-2xl bg-red-50 p-4 text-red-800 ring-1 ring-red-200">
      {Object.values(error.fields).flat().map((m) => <li key={m}>{String(m)}</li>)}
    </ul>
  )
}

export function FieldError({ error, name }) {
  const msg = error?.field?.(name)
  return msg ? <p className="mt-1 text-sm text-red-700">{msg}</p> : null
}

export function Empty({ icon: Icon = Inbox, children }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-3xl border-2 border-dashed border-brand/20 p-8 text-center text-brand/80">
      <Icon className="size-10" aria-hidden />
      <p>{children}</p>
    </div>
  )
}

const TONES = {
  OPEN: 'bg-sky-100 text-sky-900',
  BOOKED: 'bg-sun-100 text-amber-900',
  IN_PROGRESS: 'bg-violet-100 text-violet-900',
  COMPLETED: 'bg-brand-100 text-brand',
}

export function StatusBadge({ status }) {
  const { t } = useLang()
  return <span className={cx('rounded-full px-3 py-0.5 text-sm font-bold', TONES[status] || 'bg-gray-100')}>{t(`s_${status}`)}</span>
}

const TRADE_ICONS = { droplet: Droplet, zap: Zap, snowflake: Snowflake, hammer: Hammer, paintbrush: Paintbrush }

export function TradeIcon({ iconKey, className = 'size-8' }) {
  const Icon = TRADE_ICONS[iconKey] || Wrench
  return <Icon className={className} aria-hidden />
}

/** Large tap target for picking catalog entries (multi- or single-select). */
export function Tile({ selected, onClick, icon, label, sub }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cx(
        'relative flex min-h-24 flex-col items-center justify-center gap-1 rounded-2xl p-3 text-center font-bold transition',
        selected ? 'bg-brand text-white ring-4 ring-sun' : 'bg-white text-brand ring-1 ring-brand/15 active:bg-brand-50',
      )}
    >
      {selected && <CircleCheck className="absolute end-2 top-2 size-5 text-sun" aria-hidden />}
      {icon}
      <span className="leading-snug">{label}</span>
      {sub && <span className="text-xs font-normal opacity-80">{sub}</span>}
    </button>
  )
}

export function Chip({ selected, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={cx(
        'min-h-11 rounded-full px-4 text-base transition',
        selected ? 'bg-brand text-white' : 'bg-white text-brand ring-1 ring-brand/20 active:bg-brand-50',
      )}
    >
      {children}
    </button>
  )
}

export function Stars({ value, onChange, size = 'size-7', label }) {
  return (
    <div className="flex gap-1" dir="ltr" role={onChange ? 'radiogroup' : 'img'} aria-label={label || `${value ?? 0} / 5`}>
      {[1, 2, 3, 4, 5].map((n) => {
        const filled = value != null && n <= Math.round(value)
        const star = <Star className={cx(size, filled ? 'fill-sun text-sun' : 'text-gray-300')} aria-hidden />
        return onChange ? (
          <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n}`}
            onClick={() => onChange(n)} className="p-1">{star}</button>
        ) : <span key={n}>{star}</span>
      })}
    </div>
  )
}

export function RatingLine({ rating, completed }) {
  const { t } = useLang()
  if (!rating || rating.count === 0) {
    return <span className="rounded-full bg-sky-100 px-2 text-sm text-sky-900">{t('new_worker')}</span>
  }
  return (
    <span className="inline-flex items-center gap-1 text-sm">
      <Star className="size-4 fill-sun text-sun" aria-hidden />
      <span className="num font-bold">{rating.average.toFixed(1)}</span>
      <span className="num text-gray-500">({rating.count})</span>
      {completed != null && <span className="text-gray-500">· <span className="num">{completed}</span> {t('jobs_done')}</span>}
    </span>
  )
}

/** ID matched against the fictional demo registry (never a real identity check). */
export function VerifiedBadge() {
  const { t } = useLang()
  return (
    <span className="inline-flex items-center gap-1 text-sm text-brand" title={t('registry_fictional')}>
      <BadgeCheck className="size-4" aria-hidden />
      {t('verified_demo')}
    </span>
  )
}

/** Fetches the protected audio with the session cookie, then plays it locally. */
export function AudioPlayer({ url }) {
  const { t, errorText } = useLang()
  const [src, setSrc] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => () => { if (src) URL.revokeObjectURL(src) }, [src])
  if (src) return <audio controls autoPlay src={src} className="w-full" />
  return (
    <div>
      <Button variant="secondary" icon={Play} busy={busy} onClick={async () => {
        setBusy(true)
        setError(null)
        try { setSrc(await fetchBlobUrl(url)) } catch (e) { setError(e) } finally { setBusy(false) }
      }}>
        {t('voice_note')} · {t('play')}
      </Button>
      {error && <p className="mt-2 text-sm text-red-700">{errorText(error)}</p>}
    </div>
  )
}

/** Reads a label aloud where the device has an Urdu voice; hidden otherwise. */
export function Speak({ text }) {
  const { lang } = useLang()
  const [voice, setVoice] = useState(null)
  useEffect(() => {
    if (!('speechSynthesis' in window)) return undefined
    const pick = () => {
      const want = lang === 'ur' ? 'ur' : 'en'
      setVoice(window.speechSynthesis.getVoices().find((v) => v.lang?.toLowerCase().startsWith(want)) || null)
    }
    pick()
    window.speechSynthesis.addEventListener?.('voiceschanged', pick)
    return () => window.speechSynthesis.removeEventListener?.('voiceschanged', pick)
  }, [lang])
  if (!voice) return null
  return (
    <button type="button" aria-label="Listen" className="rounded-full bg-sun-100 p-2 text-ink"
      onClick={() => {
        const u = new SpeechSynthesisUtterance(text)
        u.voice = voice
        u.lang = voice.lang
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(u)
      }}>
      <Volume2 className="size-5" aria-hidden />
    </button>
  )
}

export function Heading({ children, speak }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <h1 className="text-2xl font-bold text-brand">{children}</h1>
      {speak && <Speak text={speak} />}
    </div>
  )
}

/** Six-digit PIN entry with an on-screen keypad (no typing needed). */
export function PinPad({ onSubmit, busy, label }) {
  const [digits, setDigits] = useState('')
  const press = (d) => setDigits((v) => (v.length < 6 ? v + d : v))
  return (
    <div className="space-y-3">
      <div className="flex justify-center gap-2" dir="ltr" aria-label={label} aria-live="polite">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <span key={i} className={cx('num flex h-14 w-11 items-center justify-center rounded-xl text-2xl font-bold',
            digits[i] ? 'bg-brand text-white' : 'bg-brand-50 ring-1 ring-brand/20')}>{digits[i] || ''}</span>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2" dir="ltr">
        {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
          <button key={d} type="button" onClick={() => press(d)} className="num min-h-14 rounded-2xl bg-white text-2xl font-bold ring-1 ring-brand/15 active:bg-brand-50">{d}</button>
        ))}
        <button type="button" aria-label="delete" onClick={() => setDigits((v) => v.slice(0, -1))} className="flex min-h-14 items-center justify-center rounded-2xl bg-white ring-1 ring-brand/15"><Delete className="size-6" /></button>
        <button type="button" onClick={() => press('0')} className="num min-h-14 rounded-2xl bg-white text-2xl font-bold ring-1 ring-brand/15 active:bg-brand-50">0</button>
        <span />
      </div>
      <Button variant="sun" busy={busy} disabled={digits.length !== 6}
        onClick={() => onSubmit(digits, () => setDigits(''))}>{label}</Button>
    </div>
  )
}
