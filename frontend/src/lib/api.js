// The one API client. Same-origin relative URLs, Django session cookie (HttpOnly,
// never read here) and X-CSRFToken on every write. Errors become ApiError with
// the backend's stable `code`, field errors and HTTP status.

let csrfToken = null

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || (status === 0 ? 'Network error' : `Request failed (${status})`))
    this.status = status
    this.code = body?.code || (status === 0 ? 'network' : null)
    this.body = body
    // DRF field errors: {"field": ["msg", ...]} (no "detail")
    this.fields = body && typeof body === 'object' && !('detail' in body) ? body : null
  }
  field(name) {
    const v = this.fields?.[name]
    return Array.isArray(v) ? v[0] : null
  }
}

export async function refreshCsrf() {
  const res = await fetch('/api/v1/auth/csrf/', { credentials: 'same-origin' })
  csrfToken = (await res.json()).csrf_token
  return csrfToken
}

export async function api(path, { method = 'GET', json, form, retry = true } = {}) {
  const headers = { Accept: 'application/json' }
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) {
    body = form // browser sets the multipart boundary
  }
  if (method !== 'GET') {
    if (!csrfToken) await refreshCsrf()
    headers['X-CSRFToken'] = csrfToken
  }
  let res
  try {
    res = await fetch(`/api/v1${path}`, { method, headers, body, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, null)
  }
  if (res.status === 204) return null
  const data = (res.headers.get('content-type') || '').includes('json') ? await res.json() : null
  if (!res.ok) {
    // A rotated or missing token: fetch a fresh one and retry once.
    if (res.status === 403 && data?.code === 'csrf_failed' && retry) {
      await refreshCsrf()
      return api(path, { method, json, form, retry: false })
    }
    throw new ApiError(res.status, data)
  }
  return data
}

/** Fetch a protected media file (voice note) as an object URL. */
export async function fetchBlobUrl(url) {
  const res = await fetch(url, { credentials: 'same-origin' })
  if (!res.ok) {
    let data = null
    try { data = await res.json() } catch { /* not json */ }
    throw new ApiError(res.status, data)
  }
  return URL.createObjectURL(await res.blob())
}
