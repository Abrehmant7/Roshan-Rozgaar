import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BadgeCheck, Camera, Check, FlaskConical, Info, MapPin, Minus, Plus, RefreshCw, ScanLine } from 'lucide-react'
import { Button, Card, Chip, ErrorBanner, FieldErrors, Heading, Spinner, Tile, TradeIcon } from '../../components/ui.jsx'
import { api } from '../../lib/api.js'
import { useCatalog, useSpecialties } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'

const toggle = (list, id) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id])

function ScanStep({ onDone }) {
  const { t, lang } = useLang()
  const input = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function upload(file) {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    const form = new FormData()
    form.append('image', file)
    try {
      // Live OCR can take several seconds; the server caps it at OCR_TIMEOUT_SECONDS.
      setResult(await api('/workers/me/scan/', { method: 'POST', form, timeout: 45000 }))
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
      if (input.current) input.current.value = ''
    }
  }

  return (
    <div className="space-y-4">
      <Heading speak={`${t('scan_title')}. ${t('scan_hint')}`}>{t('scan_title')}</Heading>
      <p className="text-brand/80">{t('scan_hint')}</p>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only"
        data-testid="scan-input" onChange={(e) => upload(e.target.files?.[0])} />
      {busy && <Spinner label={t('scanning')} />}
      {!busy && !result && (
        <button type="button" onClick={() => input.current?.click()}
          className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-3 rounded-3xl border-4 border-dashed border-brand/30 bg-white text-brand active:bg-brand-50">
          <Camera className="size-16" aria-hidden />
          <span className="text-xl font-bold">{t('scan_button')}</span>
        </button>
      )}
      <ErrorBanner error={error} onRetry={error?.retryable ? () => input.current?.click() : null} />
      {result && (
        <Card className="space-y-3">
          {result.simulated ? (
            <div className="flex items-center gap-2 rounded-2xl bg-amber-100 p-3 text-amber-900" data-testid="mock-label">
              <FlaskConical className="size-6 shrink-0" aria-hidden />
              <div><p className="font-bold">{t('mock_badge')}</p><p className="text-sm">{t('mock_badge_note')}</p></div>
            </div>
          ) : (
            <p className="flex items-center gap-2 text-sm text-brand" data-testid="live-label"><ScanLine className="size-5" aria-hidden />{t('ocr_live')}</p>
          )}
          <p className="flex items-start gap-2 rounded-2xl bg-sky-50 p-3 text-sm text-sky-900" data-testid="registry-label">
            <Info className="mt-1 size-5 shrink-0" aria-hidden />{t('registry_fictional')}
          </p>
          <p className="flex items-center gap-2 text-brand"><BadgeCheck className="size-6" aria-hidden />{t('scan_ok')}</p>
          <p className="text-lg">{t('is_this_you')}</p>
          <p className="text-2xl font-bold">{lang === 'ur' ? result.identity.name_ur : result.identity.name_en}</p>
          <p className="num text-lg tracking-wider text-gray-600">{result.identity.id_masked}</p>
          <Button icon={Check} onClick={() => onDone(result)}>{t('yes_me')}</Button>
          <Button variant="secondary" icon={RefreshCw} onClick={() => { setResult(null); input.current?.click() }}>{t('retry')}</Button>
        </Card>
      )}
    </div>
  )
}

export default function Onboarding() {
  const { t, name, lang } = useLang()
  const navigate = useNavigate()
  const { trades, areas, error: catalogError, retry: retryCatalog } = useCatalog()
  const [existing, setExisting] = useState(undefined) // undefined: loading, null: no profile yet
  const [loadError, setLoadError] = useState(null)
  const [attempt, setAttempt] = useState(0)
  const [scan, setScan] = useState(null)
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({ display_name: '', experience_years: 1, trades: [], specialties: [], service_areas: [] })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const specialties = useSpecialties(form.trades)

  useEffect(() => {
    let live = true
    setLoadError(null)
    api('/workers/me/').then((p) => {
      if (!live) return
      setExisting(p)
      setForm({ display_name: p.display_name, experience_years: p.experience_years, trades: p.trades,
        specialties: p.specialties, service_areas: p.service_areas })
      setStep(1)
    }).catch((e) => {
      if (!live) return
      // Only "no profile yet" starts onboarding; any other failure is shown with a retry.
      if (e.status === 404 && e.code === 'profile_not_found') setExisting(null)
      else setLoadError(e)
    })
    return () => { live = false }
  }, [attempt])

  // Drop specialties whose trade was unselected.
  useEffect(() => {
    const valid = new Set(specialties.map((s) => s.id))
    setForm((f) => ({ ...f, specialties: f.specialties.filter((id) => valid.has(id)) }))
  }, [specialties])

  if (loadError) {
    return (
      <div className="space-y-3" data-testid="profile-load-error">
        <Heading>{t('profile_load_failed')}</Heading>
        <ErrorBanner error={loadError} onRetry={() => setAttempt((n) => n + 1)} />
      </div>
    )
  }
  if (catalogError) return <ErrorBanner error={catalogError} onRetry={retryCatalog} />
  if (existing === undefined || !trades) return <Spinner />

  if (step === 0) {
    return <ScanStep onDone={(r) => {
      setScan(r)
      setForm((f) => ({ ...f, display_name: f.display_name || (lang === 'ur' ? r.identity.name_ur : r.identity.name_en) }))
      setStep(1)
    }} />
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api('/workers/me/', { method: 'PUT', json: { ...form, accepting_jobs: existing?.accepting_jobs ?? true,
        ...(scan ? { scan_proof: scan.scan_proof } : {}) } })
      navigate('/w', { replace: true })
    } catch (e) {
      setError(e)
      if (e.field('scan_proof')) { setScan(null); setStep(0) }
    } finally {
      setBusy(false)
    }
  }

  const steps = [
    null,
    {
      title: t('pick_trades'), ok: form.trades.length > 0,
      body: (
        <div className="grid grid-cols-2 gap-3">
          {trades.map((tr) => (
            <Tile key={tr.id} selected={form.trades.includes(tr.id)} label={name(tr)}
              icon={<TradeIcon iconKey={tr.icon_key} className="size-9" />}
              onClick={() => setForm({ ...form, trades: toggle(form.trades, tr.id) })} />
          ))}
        </div>
      ),
    },
    {
      title: t('pick_specialties'), ok: true,
      body: (
        <div className="flex flex-wrap gap-2">
          {specialties.map((s) => (
            <Chip key={s.id} selected={form.specialties.includes(s.id)}
              onClick={() => setForm({ ...form, specialties: toggle(form.specialties, s.id) })}>{name(s)}</Chip>
          ))}
        </div>
      ),
    },
    {
      title: t('pick_areas'), ok: form.service_areas.length > 0,
      body: (
        <div className="grid grid-cols-3 gap-3">
          {areas.map((a) => (
            <Tile key={a.id} selected={form.service_areas.includes(a.id)} label={<span className="num">{a.sector_code}</span>}
              sub={a.city} icon={<MapPin className="size-6" />}
              onClick={() => setForm({ ...form, service_areas: toggle(form.service_areas, a.id) })} />
          ))}
        </div>
      ),
    },
    {
      title: t('your_name'), ok: form.display_name.trim().length > 0,
      body: (
        <div className="space-y-5">
          <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            aria-label={t('your_name')} maxLength={100}
            className="block min-h-14 w-full rounded-2xl border-2 border-brand/15 bg-white px-4 text-xl" />
          <div>
            <p className="mb-2 font-bold text-brand">{t('experience')}</p>
            <div className="flex items-center justify-between gap-3" dir="ltr">
              <button type="button" aria-label="-1" onClick={() => setForm({ ...form, experience_years: Math.max(0, form.experience_years - 1) })}
                className="flex size-16 items-center justify-center rounded-2xl bg-white ring-1 ring-brand/20"><Minus className="size-7" /></button>
              <span className="num text-4xl font-bold text-brand" data-testid="experience">{form.experience_years}</span>
              <button type="button" aria-label="+1" onClick={() => setForm({ ...form, experience_years: Math.min(60, form.experience_years + 1) })}
                className="flex size-16 items-center justify-center rounded-2xl bg-white ring-1 ring-brand/20"><Plus className="size-7" /></button>
            </div>
          </div>
        </div>
      ),
    },
  ]
  const current = steps[step]
  const last = step === steps.length - 1

  return (
    <div className="space-y-4">
      <p className="text-sm text-brand/70">{t(existing ? 'onb_edit_title' : 'onb_title')} · <span className="num">{step}/{steps.length - 1}</span></p>
      <Heading speak={current.title}>{current.title}</Heading>
      {current.body}
      {!current.ok && <p className="text-sm text-amber-800">{t('choose_one')}</p>}
      {error?.fields ? <FieldErrors error={error} /> : <ErrorBanner error={error} />}
      <div className="grid grid-cols-2 gap-3">
        <Button variant="secondary" onClick={() => setStep(step - 1)} disabled={step === 1 && Boolean(existing)}>{t('back')}</Button>
        {last
          ? <Button variant="sun" busy={busy} disabled={!current.ok} onClick={save}>{t('save_profile')}</Button>
          : <Button disabled={!current.ok} onClick={() => setStep(step + 1)}>{t('next')}</Button>}
      </div>
    </div>
  )
}
