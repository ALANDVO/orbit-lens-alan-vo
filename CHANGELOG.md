# Changelog

## 1.5.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

All notable changes to Orbit Lens will be documented in this file.

## [1.4.0] - 2026-11-23

### Added
- Coverage ledger tracking with CoverageUnit model
- CoverageValidator for artifact integrity checking
- Comprehensive coverage ledger tests
- Audit run creation with target specification
- Multi-phase audit execution (reconnaissance, hunting, validation, reporting, consolidation)
- Profile-based phase selection (QUICK, STANDARD, DEEP)
- Coverage unit creation with security invariants
- Finding detection and verification workflow
- Audit log event tracking
- REST API for audit management (create, list, start, findings, coverage, export, logs)
- JSON and SARIF export formats

### Changed
- Updated test suite to 31 passing tests
- Enhanced coverage validation to reject symlinks and missing artifacts

## [1.3.0] - 2026-11-16

### Added
- OIDC authentication with Keycloak integration
- Role-based access control (viewer/analyst/admin)
- Session management with HttpOnly cookies
- CSRF protection on state-changing operations
- Frontend login and callback pages
- Auth store with token management

### Changed
- Updated backend auth middleware
- Enhanced frontend API client with token handling

## [1.2.0] - 2026-11-09

### Added
- FastAPI backend with health endpoints
- React + Vite frontend skeleton
- SQLite database with migrations
- Dockerfiles for backend and frontend
- Docker Compose with Keycloak
- Basic project structure

### Changed
- Initial project setup
- Development environment configuration

## [1.1.0] - 2026-11-02

### Added
- Project initialization
- Basic architecture planning
- Technology stack selection

## [1.0.0] - 2026-10-26

### Added
- Initial project concept
- Requirements gathering

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
