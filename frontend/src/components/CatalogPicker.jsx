import { MapPin } from 'lucide-react'
import { useSpecialties } from '../lib/hooks.js'
import { useLang } from '../lib/i18n.jsx'
import { Chip, Tile, TradeIcon } from './ui.jsx'

/** Single-choice trade + area + optional specialty, all as tap targets. */
export default function CatalogPicker({ trades, areas, value, onChange }) {
  const { t, name } = useLang()
  const specialties = useSpecialties(value.trade ? [value.trade] : [])
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        {trades.map((tr) => (
          <Tile key={tr.id} selected={value.trade === tr.id} label={name(tr)} icon={<TradeIcon iconKey={tr.icon_key} className="size-9" />}
            onClick={() => onChange({ ...value, trade: tr.id, specialty: null })} />
        ))}
      </div>
      {value.trade && specialties.length > 0 && (
        <section className="space-y-2">
          <h2 className="font-bold text-brand">{t('choose_specialty')}</h2>
          <div className="flex flex-wrap gap-2">
            <Chip selected={!value.specialty} onClick={() => onChange({ ...value, specialty: null })}>{t('any_specialty')}</Chip>
            {specialties.map((s) => (
              <Chip key={s.id} selected={value.specialty === s.id} onClick={() => onChange({ ...value, specialty: s.id })}>{name(s)}</Chip>
            ))}
          </div>
        </section>
      )}
      <section className="space-y-2">
        <h2 className="font-bold text-brand">{t('choose_area')}</h2>
        <div className="grid grid-cols-3 gap-2">
          {areas.map((a) => (
            <Tile key={a.id} selected={value.area === a.id} label={<span className="num">{a.sector_code}</span>} sub={a.city}
              icon={<MapPin className="size-5" />} onClick={() => onChange({ ...value, area: a.id })} />
          ))}
        </div>
      </section>
    </div>
  )
}

export function pickerFromParams(params) {
  const num = (k) => (params.get(k) ? Number(params.get(k)) : null)
  return { trade: num('trade'), area: num('area'), specialty: num('specialty') }
}

export function pickerToParams(v) {
  const out = {}
  if (v.trade) out.trade = String(v.trade)
  if (v.area) out.area = String(v.area)
  if (v.specialty) out.specialty = String(v.specialty)
  return out
}
