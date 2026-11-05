# Changelog

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.1.0 — work-in-progress checkpoint (auth-oidc: refresh token support)

### Added
- `backend/app/api/auth.py` — TokenResponse model now includes `refresh_token` field
- `backend/app/api/auth.py` — Token exchange endpoint (`/api/v1/auth/token`) returns `refresh_token` for client-side storage
- `backend/app/api/auth.py` — Refresh endpoint (`/api/v1/auth/refresh`) returns rotated `refresh_token` for token rotation
- `frontend/src/pages/Callback.tsx` — Stores `refresh_token` in sessionStorage after successful token exchange
- `frontend/src/api/client.ts` — Axios interceptor uses `refresh_token` for token refresh requests (was incorrectly using access_token)
- `backend/tests/test_auth.py` — Added 4 new tests: token exchange returns refresh_token, refresh endpoint returns rotated tokens, invalid token rejected, access token rejected for refresh

### Changed
- Token exchange response now includes refresh_token alongside access_token
- Token refresh response now includes new refresh_token for rotation

### Fixed
- Frontend token refresh now correctly uses refresh_token instead of access_token
- Token rotation working properly on both token exchange and refresh

### Tests
- All 26 backend tests passing (13 audit + 13 auth)
- 2 frontend tests passing

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.0.0 — work-in-progress checkpoint (auth-oidc improvements)

Partial code published for continued development. Known issues: STATUS.md.

## [1.0.0] - 2026-10-29

### Added
- `backend/app/core/auth.py` — core OIDC authentication module with token verification (signature, issuer, audience checks)
- `backend/tests/test_auth.py` — 9 auth-related tests (token validation, role mapping, expired tokens, unauthorized access)
- Frontend callback now exchanges authorization code via backend `/api/v1/auth/token` endpoint
- Frontend API client with automatic token refresh on 401 responses
- Role-based access control with viewer/analyst/admin roles mapped from Keycloak realm roles

### Changed
- Refactored `backend/app/api/auth.py` to delegate OIDC verification to `core.auth`
- Token exchange now uses structured `TokenExchangeRequest` model
- Internal token generation centralized in `core.auth` (create_access_token, create_refresh_token)
- JWT error handling in `get_current_user` catches all JWTError variants

### Fixed
- Expired tokens now properly return 401 instead of unhandled exception
- Test fixtures updated to import from `app.core.auth`

### Tests
- All 22 backend tests passing (13 audit + 9 auth)
- 2 frontend tests passing

## [1.0.0] - 2026-10-20

### Added
- Project skeleton with FastAPI backend and React + Vite frontend
- SQLite database with SQLAlchemy async ORM
- Health check endpoints (`/api/v1/health`, `/api/v1/health/db`)
- Audit run CRUD API with pagination and filtering
- Findings and coverage ledger API endpoints
- JSON and SARIF 2.1.0 export endpoints
- OIDC authentication infrastructure (Keycloak realm, PKCE flow)
- Role-based access control (viewer, analyst, admin)
- JWT token validation with JWKS
- Dockerfiles for backend and frontend with non-root users
- compose.yaml with Keycloak and persistent volumes
- GitHub Actions CI workflow (backend tests, frontend tests, Docker builds)
- Test suite: 13 backend tests, 2 frontend tests passing
- pyproject.toml with project metadata
- portfolio.json for portfolio integration
- LICENSE (MIT)
