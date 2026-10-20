import { useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Shield } from 'lucide-react'
import { useAuthStore } from '@/hooks/useAuthStore'
export function Login() {
  const navigate = useNavigate()
  const { checkAuth } = useAuthStore()

  useEffect(() => {
    checkAuth().then(() => {
      const urlParams = new URLSearchParams(window.location.search)
      const redirect = urlParams.get('redirect') || '/'
      navigate(redirect, { replace: true })
    })
  }, [checkAuth, navigate])

  const handleLogin = async () => {
    const oidcIssuer = import.meta.env.VITE_OIDC_ISSUER || 'http://127.0.0.1:8080/realms/orbit-lens'
    const redirectUri = import.meta.env.VITE_OIDC_REDIRECT_URI || 'http://127.0.0.1:3000/callback'
    const scopes = import.meta.env.VITE_OIDC_SCOPES || 'openid profile email roles'
    const state = crypto.randomUUID()
    const codeVerifier = generateCodeVerifier()
    const codeChallenge = await generateCodeChallenge(codeVerifier)

    sessionStorage.setItem('oauth_state', state)
    sessionStorage.setItem('code_verifier', codeVerifier)

    const authUrl = new URL(`${oidcIssuer}/protocol/openid-connect/auth`)
    authUrl.searchParams.set('redirect_uri', redirectUri)
    authUrl.searchParams.set('response_type', 'code')
    authUrl.searchParams.set('scope', scopes)
    authUrl.searchParams.set('state', state)
    authUrl.searchParams.set('code_challenge', codeChallenge)
    authUrl.searchParams.set('code_challenge_method', 'S256')

    window.location.href = authUrl.toString()
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <Link to="/" className="inline-flex items-center gap-2 text-2xl font-bold text-blue-600">
            <Shield className="h-8 w-8" />
            Orbit Lens
          </Link>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">Sign in to your account</h2>
          <p className="mt-2 text-gray-600">Use Keycloak SSO to access the audit dashboard</p>
        </div>

        <div className="bg-white py-8 px-6 shadow-sm rounded-lg border border-gray-200">
          <button
            onClick={handleLogin}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
            </svg>
            Sign in with Keycloak
          </button>

          <p className="mt-6 text-center text-sm text-gray-500">
            Demo mode available for local development
          </p>
        </div>

        <div className="text-center text-sm text-gray-500">
          <p>Orbit Lens - Multi-phase security audit skill</p>
          <p className="mt-1">Alan Vo <span>alanvo@gmail.com</span></p>
        </div>
      </div>
    </div>
  )
}

function generateCodeVerifier(): string {
  const array = new Uint8Array(32)
  crypto.getRandomValues(array)
  return btoa(String.fromCharCode(...array))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '')
}

function generateCodeChallenge(codeVerifier: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(codeVerifier)
  return crypto.subtle.digest('SHA-256', data).then((hash) => {
    const bytes = new Uint8Array(hash)
    return btoa(String.fromCharCode(...bytes))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '')
  })
}