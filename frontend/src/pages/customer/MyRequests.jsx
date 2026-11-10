import { Plus } from 'lucide-react'
import JobCard from '../../components/JobCard.jsx'
import { Empty, ErrorBanner, Heading, LinkButton, Spinner } from '../../components/ui.jsx'
import { useApi } from '../../lib/hooks.js'
import { useLang } from '../../lib/i18n.jsx'

export default function MyRequests() {
  const { t } = useLang()
  const { data, error, loading, reload } = useApi('/job-requests/?page_size=50', { poll: 15000 })
  return (
    <div className="space-y-4">
      <Heading speak={t('my_requests')}>{t('my_requests')}</Heading>
      <LinkButton to="/c" variant="sun" icon={Plus}>{t('post_request')}</LinkButton>
      {loading && !data && <Spinner />}
      <ErrorBanner error={error} onRetry={reload} />
      {data?.results.length === 0 && <Empty>{t('requests_empty')}</Empty>}
      {data?.results.map((job) => (
        <JobCard key={job.id} job={job} to={`/c/requests/${job.id}`}
          extra={job.status === 'OPEN' && (
            <span className="rounded-full bg-brand-100 px-2 py-0.5"><span className="num">{job.quote_count}</span> {t('quotes_count')}</span>
          )} />
      ))}
    </div>
  )
}
