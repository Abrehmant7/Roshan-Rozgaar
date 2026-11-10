import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

/** GET a resource; optional polling. Returns {data, error, loading, reload}. */
export function useApi(path, { poll = 0, enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: Boolean(path && enabled) })
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])

  const reload = useCallback(async ({ quiet = false } = {}) => {
    if (!path || !enabled) return null
    if (!quiet) setState((s) => ({ ...s, loading: true }))
    try {
      const data = await api(path)
      if (alive.current) setState({ data, error: null, loading: false })
      return data
    } catch (error) {
      if (alive.current) setState((s) => ({ ...s, error, loading: false }))
      return null
    }
  }, [path, enabled])

  useEffect(() => {
    reload()
    if (!poll) return undefined
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') reload({ quiet: true })
    }, poll)
    return () => clearInterval(id)
  }, [reload, poll])

  return { ...state, reload, setData: (data) => setState((s) => ({ ...s, data })) }
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
  const [state, setState] = useState({ trades: null, areas: null, error: null })
  useEffect(() => {
    let live = true
    Promise.all([cached('/catalog/trades/'), cached('/catalog/service-areas/')])
      .then(([trades, areas]) => live && setState({ trades, areas, error: null }))
      .catch((error) => live && setState((s) => ({ ...s, error })))
    return () => { live = false }
  }, [])
  return state
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
