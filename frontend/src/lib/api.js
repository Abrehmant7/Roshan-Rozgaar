// The one API client. Same-origin relative URLs, Django session cookie (HttpOnly,
// never read here) and X-CSRFToken on every write. Errors become ApiError with
// the backend's stable `code`, field errors and HTTP status. Every request is
// bounded by a timeout and can be cancelled by the caller.

let csrfToken = null
export const DEFAULT_TIMEOUT_MS = 15000

export class ApiError extends Error {
  constructor(status, body, code = null) {
    super(body?.detail || code || `Request failed (${status})`)
    this.status = status
    // Client-side codes: timeout | network | aborted | server_error
    this.code = code || body?.code || (status >= 500 ? 'server_error' : null)
    this.body = body
    // DRF field errors: {"field": ["msg", ...]} (no "detail")
    this.fields = body && typeof body === 'object' && !('detail' in body) ? body : null
  }
  field(name) {
    const v = this.fields?.[name]
    return Array.isArray(v) ? v[0] : null
  }
  get retryable() {
    return ['timeout', 'network', 'server_error'].includes(this.code) || Boolean(this.body?.retryable)
  }
}

/** fetch() with a timeout and an optional caller signal; maps failures to ApiError. */
async function request(url, init, { signal, timeout = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeout)
  const forward = () => controller.abort()
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', forward, { once: true })
  }
  try {
    const res = await fetch(url, { ...init, credentials: 'same-origin', signal: controller.signal })
    const isJson = (res.headers.get('content-type') || '').includes('json')
    const data = res.status === 204 ? null : isJson ? await res.json() : null
    return { res, data }
  } catch (err) {
    if (timedOut) throw new ApiError(0, null, 'timeout')
    if (signal?.aborted) throw new ApiError(0, null, 'aborted')
    if (err instanceof ApiError) throw err
    throw new ApiError(0, null, 'network')
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forward)
  }
}

export async function refreshCsrf({ signal } = {}) {
  const { res, data } = await request('/api/v1/auth/csrf/', { headers: { Accept: 'application/json' } }, { signal })
  if (!res.ok || !data?.csrf_token) throw new ApiError(res.status, data)
  csrfToken = data.csrf_token
  return csrfToken
}

export async function api(path, { method = 'GET', json, form, retry = true, signal, timeout } = {}) {
  const headers = { Accept: 'application/json' }
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form // browser sets the multipart boundary
  }
  if (method !== 'GET') {
    if (!csrfToken) await refreshCsrf({ signal })
    headers['X-CSRFToken'] = csrfToken
  }
  const { res, data } = await request(`/api/v1${path}`, { method, headers, body }, { signal, timeout })
  if (!res.ok) {
    // A rotated or missing token: fetch a fresh one and retry once.
    if (res.status === 403 && data?.code === 'csrf_failed' && retry) {
      await refreshCsrf({ signal })
      return api(path, { method, json, form, retry: false, signal, timeout })
    }
    throw new ApiError(res.status, data)
  }
  return data
}

/** Fetch a protected media file (voice note) as an object URL. */
export async function fetchBlobUrl(url, { timeout = 30000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(url, { credentials: 'same-origin', signal: controller.signal })
    if (!res.ok) {
      let data = null
      try { data = await res.json() } catch { /* not json */ }
      throw new ApiError(res.status, data)
    }
    return URL.createObjectURL(await res.blob())
  } catch (err) {
    if (err instanceof ApiError) throw err
    throw new ApiError(0, null, controller.signal.aborted ? 'timeout' : 'network')
  } finally {
    clearTimeout(timer)
  }
}
