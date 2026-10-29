# Changelog

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.0.0 — work-in-progress checkpoint (auth-oidc improvements)

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
