import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { useAuthStore } from './hooks/useAuthStore'

vi.mock('./hooks/useAuthStore')

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders login page when not authenticated', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      setUser: vi.fn(),
      setLoading: vi.fn(),
      checkAuth: vi.fn().mockResolvedValue(undefined),
      logout: vi.fn().mockResolvedValue(undefined),
    })

    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    expect(screen.getByText('Sign in to your account')).toBeInTheDocument()
  })

  it('redirects to dashboard when authenticated', async () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: {
        id: 1,
        keycloak_id: 'test',
        email: 'test@example.com',
        username: 'testuser',
        full_name: 'Test User',
        role: 'analyst',
        is_active: true,
      },
      isAuthenticated: true,
      isLoading: false,
      setUser: vi.fn(),
      setLoading: vi.fn(),
      checkAuth: vi.fn().mockResolvedValue(undefined),
      logout: vi.fn().mockResolvedValue(undefined),
    })

    render(
      <BrowserRouter>
        <App />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Audit Dashboard')).toBeInTheDocument()
    })
  })
})