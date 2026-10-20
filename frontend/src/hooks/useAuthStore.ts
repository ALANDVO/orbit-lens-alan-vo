import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: number
  keycloak_id: string
  email: string
  username: string
  full_name: string | null
  role: 'viewer' | 'analyst' | 'admin'
  is_active: boolean
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  setUser: (user: User | null) => void
  setLoading: (loading: boolean) => void
  checkAuth: () => Promise<void>
  logout: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),

      setLoading: (isLoading) => set({ isLoading }),

      checkAuth: async () => {
        const token = sessionStorage.getItem('access_token')
        if (!token) {
          set({ user: null, isAuthenticated: false, isLoading: false })
          return
        }
        try {
          const response = await fetch('/api/v1/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (response.ok) {
            const user = await response.json()
            set({ user, isAuthenticated: true, isLoading: false })
          } else {
            sessionStorage.removeItem('access_token')
            set({ user: null, isAuthenticated: false, isLoading: false })
          }
        } catch {
          set({ user: null, isAuthenticated: false, isLoading: false })
        }
      },

      logout: async () => {
        const token = sessionStorage.getItem('access_token')
        if (token) {
          try {
            await fetch('/api/v1/auth/logout', {
              method: 'POST',
              headers: { Authorization: `Bearer ${token}` },
            })
          } catch {
            // Ignore logout errors
          }
        }
        sessionStorage.removeItem('access_token')
        sessionStorage.removeItem('refresh_token')
        set({ user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)