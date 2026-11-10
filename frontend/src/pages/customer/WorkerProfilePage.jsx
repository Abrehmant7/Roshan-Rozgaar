import { useParams, useSearchParams } from 'react-router-dom'
import { Send } from 'lucide-react'
import WorkerCard from '../../components/WorkerCard.jsx'
import { Card, Empty, ErrorBanner, LinkButton, Spinner, Stars } from '../../components/ui.jsx'
import { cached, useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'
import { when } from '../../lib/format.js'
import { useEffect, useState } from 'react'

export default function WorkerProfilePage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const { t, name, lang } = useLang()
  const { data: w, error, loading } = useApi(`/workers/${id}/`)
  const [tags, setTags] = useState({})
  useEffect(() => { cached('/reviews/tags/').then((list) => setTags(Object.fromEntries(list.map((x) => [x.key, x])))).catch(() => {}) }, [])

  if (loading && !w) return <Spinner />
  if (!w) return <ErrorBanner error={error} />
  return (
    <div className="space-y-4">
      <WorkerCard worker={w} />
      <section className="space-y-2">
        <h2 className="text-xl font-bold text-brand">{t('reviews')}</h2>
        {w.recent_reviews.length === 0 && <Empty>{t('no_reviews')}</Empty>}
        {w.recent_reviews.map((r) => (
          <Card key={r.id} className="space-y-1">
            <div className="flex items-center justify-between"><Stars value={r.rating} size="size-5" /><span className="text-sm text-gray-500">{when(r.created_at, lang)}</span></div>
            {r.text && <p>{r.text}</p>}
            <div className="flex flex-wrap gap-1">{r.tags.map((k) => <span key={k} className="rounded-full bg-brand-50 px-2 text-sm">{tags[k] ? name(tags[k]) : k}</span>)}</div>
          </Card>
        ))}
      </section>
      <LinkButton to={`/c/new?${params.toString()}`} variant="sun" icon={Send}>{t('post_request')}</LinkButton>
    </div>
  )
}
