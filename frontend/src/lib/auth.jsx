import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, refreshCsrf } from './api.js'

const AuthCtx = createContext(null)

export function homeFor(user) {
  return user?.role === 'worker' ? '/w' : '/c'
}

export function AuthProvider({ children }) {
  // undefined = not known yet (restoring, or restore failed); null = signed out.
  const [user, setUser] = useState(undefined)
  const [restoreError, setRestoreError] = useState(null)

  const restore = useCallback(async () => {
    setRestoreError(null)
    try {
      setUser(await api('/auth/me/'))
    } catch (e) {
      // Only an explicit "not signed in" from Django means signed out. Network,
      // timeout and server failures keep the state unknown and offer a retry.
      if (e.status === 401 || e.status === 403) setUser(null)
      else setRestoreError(e)
    }
  }, [])

  useEffect(() => { restore() }, [restore])

  const login = useCallback(async (username, password) => {
    await refreshCsrf()
    const u = await api('/auth/login/', { method: 'POST', json: { username, password } })
    await refreshCsrf() // Django rotates the token on login
    setRestoreError(null)
    setUser(u)
    return u
  }, [])

  /** role "customer" -> /auth/register/, role "worker" -> /auth/register/worker/ */
  const register = useCallback(async (username, password, role = 'customer') => {
    await refreshCsrf()
    const path = role === 'worker' ? '/auth/register/worker/' : '/auth/register/'
    const u = await api(path, { method: 'POST', json: { username, password } })
    await refreshCsrf()
    setRestoreError(null)
    setUser(u)
    return u
  }, [])

  /** Resolves only after Django confirms (204); throws otherwise and keeps the session state. */
  const logout = useCallback(async () => {
    await api('/auth/logout/', { method: 'POST' })
    setUser(null)
    await refreshCsrf().catch(() => {})
  }, [])

  return (
    <AuthCtx.Provider value={{ user, restoreError, login, register, logout, restore }}>
      {children}
    </AuthCtx.Provider>
  )
}

export function useAuth() {
  return useContext(AuthCtx)
}
