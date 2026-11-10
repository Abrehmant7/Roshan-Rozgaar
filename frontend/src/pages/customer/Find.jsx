import { useSearchParams } from 'react-router-dom'
import { Send } from 'lucide-react'
import CatalogPicker, { pickerFromParams, pickerToParams } from '../../components/CatalogPicker.jsx'
import WorkerCard from '../../components/WorkerCard.jsx'
import { Empty, ErrorBanner, Heading, LinkButton, Spinner } from '../../components/ui.jsx'
import { useApi, useCatalog } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'

export default function Find() {
  const { t } = useLang()
  const { trades, areas, error: catalogError, retry: retryCatalog } = useCatalog()
  const [params, setParams] = useSearchParams()
  const pick = pickerFromParams(params)
  const ready = Boolean(pick.trade && pick.area)
  const query = ready
    ? `/workers/?trade=${pick.trade}&service_area=${pick.area}${pick.specialty ? `&specialty=${pick.specialty}` : ''}&page_size=50`
    : null
  const { data, error, loading } = useApi(query, { enabled: ready })
  const qs = new URLSearchParams(pickerToParams(pick)).toString()

  if (catalogError) return <ErrorBanner error={catalogError} onRetry={retryCatalog} />
  if (!trades) return <Spinner />

  return (
    <div className="space-y-4">
      <Heading speak={t('find_title')}>{t('find_title')}</Heading>
      <CatalogPicker trades={trades} areas={areas} value={pick} onChange={(v) => setParams(pickerToParams(v), { replace: true })} />

      {ready && (
        <section className="space-y-3" aria-live="polite">
          <h2 className="text-xl font-bold text-brand">{t('results_title')}{data && <> (<span className="num">{data.count}</span>)</>}</h2>
          {loading && <Spinner />}
          <ErrorBanner error={error} />
          {data?.count === 0 && <Empty>{t('no_workers')}</Empty>}
          {data?.results.map((w) => <WorkerCard key={w.id} worker={w} to={`/c/workers/${w.id}?${qs}`} />)}
          <div className="sticky bottom-20">
            <LinkButton to={`/c/new?${qs}`} variant="sun" icon={Send}>{t('post_request')}</LinkButton>
          </div>
        </section>
      )}
    </div>
  )
}
