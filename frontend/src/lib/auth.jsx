import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, refreshCsrf } from './api.js'

const AuthCtx = createContext(null)

export function homeFor(user) {
  return user?.role === 'worker' ? '/w' : '/c'
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined) // undefined = still restoring the session

  const restore = useCallback(async () => {
    try {
      setUser(await api('/auth/me/'))
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => { restore() }, [restore])

  const login = useCallback(async (username, password) => {
    await refreshCsrf()
    const u = await api('/auth/login/', { method: 'POST', json: { username, password } })
    await refreshCsrf() // Django rotates the token on login
    setUser(u)
    return u
  }, [])

  const register = useCallback(async (username, password) => {
    await refreshCsrf()
    const u = await api('/auth/register/', { method: 'POST', json: { username, password } })
    await refreshCsrf()
    setUser(u)
    return u
  }, [])

  const logout = useCallback(async () => {
    try { await api('/auth/logout/', { method: 'POST' }) } finally {
      await refreshCsrf().catch(() => {})
      setUser(null)
    }
  }, [])

  return <AuthCtx.Provider value={{ user, login, register, logout, restore }}>{children}</AuthCtx.Provider>
}

export function useAuth() {
  return useContext(AuthCtx)
}
