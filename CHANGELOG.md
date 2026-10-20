# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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