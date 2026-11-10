import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/**
 * GET a resource, optionally polling. Returns {data, error, loading, reload}.
 *
 * - Survives React Strict Mode: `mounted` is re-armed on every effect setup.
 * - Latest request wins: every request gets a sequence number, older ones are
 *   aborted, and a response is applied only if it is still the newest one.
 * - State is keyed by `path`, so switching to another resource (e.g. another
 *   booking ID) never shows the previous resource's data or errors.
 * - Polls never overlap an in-flight request; a manual reload supersedes it.
 */
export function useApi(path, { poll = 0, enabled = true, timeout } = {}) {
  const active = Boolean(path && enabled)
  const [state, setState] = useState({ key: null, data: null, error: null, loading: false })
  const mounted = useRef(false)
  const seq = useRef(0)
  const inFlight = useRef(null)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      inFlight.current?.abort()
    }
  }, [])

  const reload = useCallback(async ({ quiet = false } = {}) => {
    if (!active) return null
    if (quiet && inFlight.current) return null // a poll never stacks on a pending request
    const id = ++seq.current
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    if (!quiet) {
      setState((s) => (s.key === path ? { ...s, loading: true } : { key: path, data: null, error: null, loading: true }))
    }
    try {
      const data = await api(path, { signal: controller.signal, timeout })
      if (mounted.current && id === seq.current) setState({ key: path, data, error: null, loading: false })
      return data
    } catch (error) {
      if (error.code !== 'aborted' && mounted.current && id === seq.current) {
        setState((s) => ({ key: path, data: s.key === path ? s.data : null, error, loading: false }))
      }
      return null
    } finally {
      if (inFlight.current === controller) inFlight.current = null
    }
  }, [path, active, timeout])

  useEffect(() => {
    reload()
    if (!poll) return () => inFlight.current?.abort()
    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') reload({ quiet: true })
    }, poll)
    return () => {
      clearInterval(timer)
      inFlight.current?.abort()
    }
  }, [reload, poll])

  // Never expose another path's state, even for the render before the effect runs.
  const current = state.key === path ? state : { data: null, error: null, loading: active }
  return { data: current.data, error: current.error, loading: current.loading, reload }
}

// Catalog lists change rarely: one fetch per page load, shared by all screens.
const cache = new Map()
export function cached(path) {
  if (!cache.has(path)) {
    cache.set(path, api(path).catch((e) => { cache.delete(path); throw e }))
  }
  return cache.get(path)
}

export function useCatalog() {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ trades: null, areas: null, error: null })
  useEffect(() => {
    let live = true
    setState((s) => ({ ...s, error: null }))
    Promise.all([cached('/catalog/trades/'), cached('/catalog/service-areas/')])
      .then(([trades, areas]) => live && setState({ trades, areas, error: null }))
      .catch((error) => live && setState((s) => ({ ...s, error })))
    return () => { live = false }
  }, [attempt])
  return { ...state, retry: () => setAttempt((n) => n + 1) }
}

export function useSpecialties(tradeIds) {
  const key = [...tradeIds].sort().join(',')
  const [items, setItems] = useState([])
  useEffect(() => {
    let live = true
    const ids = key ? key.split(',') : []
    Promise.all(ids.map((id) => cached(`/catalog/trades/${id}/specialties/`).catch(() => [])))
      .then((lists) => live && setItems(lists.flat()))
    return () => { live = false }
  }, [key])
  return items
}
