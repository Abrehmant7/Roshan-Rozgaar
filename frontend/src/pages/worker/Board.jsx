import { RefreshCw } from 'lucide-react'
import JobCard from '../../components/JobCard.jsx'
import { Button, Empty, ErrorBanner, Heading, LinkButton, Spinner } from '../../components/ui.jsx'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'

export default function Board() {
  const { t } = useLang()
  const { data, error, loading, reload } = useApi('/job-board/?page_size=50', { poll: 15000 })

  if (error?.code === 'profile_incomplete') {
    return (
      <div className="space-y-4">
        <ErrorBanner error={error} />
        <LinkButton to="/w/onboard" variant="sun">{t('make_profile')}</LinkButton>
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <Heading speak={t('board_title')}>{t('board_title')}</Heading>
      {data && !data.worker_is_available && <p className="rounded-2xl bg-sun-100 p-3">{t('board_unavailable')}</p>}
      {loading && !data && <Spinner />}
      <ErrorBanner error={error} onRetry={reload} />
      {data?.results.length === 0 && <Empty>{t('board_empty')}</Empty>}
      {data?.results.map((job) => <JobCard key={job.id} job={job} to={`/w/jobs/${job.id}`} />)}
      {data && <Button variant="secondary" icon={RefreshCw} onClick={() => reload()}>{t('refresh')}</Button>}
    </div>
  )
}
