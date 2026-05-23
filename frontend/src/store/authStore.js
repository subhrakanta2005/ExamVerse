import { create } from 'zustand'
import { authAPI } from '../services/api'

const useAuthStore = create((set, get) => ({
  user: (() => {
    try {
      const u = localStorage.getItem('examforge_user')
      return u ? JSON.parse(u) : null
    } catch { return null }
  })(),
  token: localStorage.getItem('examforge_token') || null,
  loading: false,
  error: null,

  setAuth: (user, token) => {
    localStorage.setItem('examforge_token', token)
    localStorage.setItem('examforge_user', JSON.stringify(user))
    set({ user, token, error: null })
  },

  clearAuth: () => {
    localStorage.removeItem('examforge_token')
    localStorage.removeItem('examforge_user')
    set({ user: null, token: null })
  },

  login: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const res = await authAPI.login({ email, password })
      get().setAuth(res.data.user, res.data.access_token)
      return res.data.user
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed'
      set({ error: msg })
      throw new Error(msg)
    } finally {
      set({ loading: false })
    }
  },

  signup: async (data) => {
    set({ loading: true, error: null })
    try {
      const res = await authAPI.signup(data)
      get().setAuth(res.data.user, res.data.access_token)
      return res.data.user
    } catch (err) {
      const msg = err.response?.data?.detail || 'Signup failed'
      set({ error: msg })
      throw new Error(msg)
    } finally {
      set({ loading: false })
    }
  },

  logout: () => {
    get().clearAuth()
  },

  isAdmin: () => get().user?.role === 'admin',
  isCandidate: () => get().user?.role === 'candidate',
  isAuthenticated: () => !!get().token,
}))

export default useAuthStore
