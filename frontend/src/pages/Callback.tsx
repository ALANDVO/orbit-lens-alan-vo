import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '@/api/client'

export function Callback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState<string>('')
  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')
    const storedState = sessionStorage.getItem('oauth_state')
    const codeVerifier = sessionStorage.getItem('code_verifier')

    if (!code || !state || state !== storedState) {
      setStatus('error')
      setErrorMessage('Invalid OAuth state or missing authorization code')
      return
    }

    const exchangeCode = async () => {
      try {
        const oidcIssuer = import.meta.env.VITE_OIDC_ISSUER || 'http://127.0.0.1:8080/realms/orbit-lens'
        const clientId = import.meta.env.VITE_OIDC_CLIENT_ID || 'orbit-lens'
        const redirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI || 'http://127.0.0.1:3000/callback'

        const tokenResponse = await fetch(`${oidcIssuer}/protocol/openid-connect/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({
            grant_type: 'authorization_code',
            client_id: clientId,
            code,
            redirect_uri: redirectUri,
            code_verifier: codeVerifier || '',
          }),
        })

        if (!tokenResponse.ok) {
          const error = await tokenResponse.json()
          throw new Error(error.error_description || 'Token exchange failed')
        }

        const tokens = await tokenResponse.json()
        sessionStorage.setItem('access_token', tokens.access_token)
        if (tokens.refresh_token) {
          sessionStorage.setItem('refresh_token', tokens.refresh_token)
        }

        sessionStorage.removeItem('oauth_state')
        sessionStorage.removeItem('code_verifier')

        await api.get('/auth/me')
        setStatus('success')

        setTimeout(() => navigate('/'), 1000)
      } catch (err) {
        setStatus('error')
        setErrorMessage(err instanceof Error ? err.message : 'Authentication failed')
      }
    }

    exchangeCode()
  }, [searchParams, navigate])

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Completing sign in...</p>
        </div>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <CheckCircle className="h-12 w-12 text-green-600 mx-auto" />
          <p className="mt-4 text-gray-600">Sign in successful. Redirecting...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full text-center">
        <AlertCircle className="h-12 w-12 text-red-600 mx-auto" />
        <h2 className="mt-4 text-xl font-bold text-gray-900">Sign in failed</h2>
        <p className="mt-2 text-gray-600">{errorMessage}</p>
        <button
          onClick={() => navigate('/login')}
          className="mt-6 inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Try again
        </button>
      </div>
    </div>
  )
}