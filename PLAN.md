# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

auth-oidc

## Roadmap

### project-skeleton — Project skeleton with FastAPI backend and React frontend

Status: done

Acceptance:
- FastAPI app runs with health endpoint
- React + Vite frontend builds and serves
- SQLite database with migrations
- Dockerfiles for backend and frontend
- docker-compose.yml with Keycloak
- Basic project structure matches contract

Implementation: `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/models/__init__.py`, `backend/app/api/__init__.py`, `backend/app/services/__init__.py`, `backend/requirements.txt`, `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/api/client.ts`, `Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, `.env.example`, `.gitignore`

Tests: `backend/tests/test_health.py`, `frontend/src/App.test.tsx`

### auth-oidc — OIDC authentication with Keycloak (PKCE flow)

Status: in_progress

Acceptance:
- Login/logout works via Keycloak
- Tokens validated with signature/issuer/audience checks
- Role-based access control (viewer/analyst/admin)
- Session management with HttpOnly cookies
- CSRF protection on state-changing operations

Implementation: `backend/app/core/auth.py`, `backend/app/api/auth.py`, `backend/app/models/models.py`, `keycloak/realm-import.json`, `frontend/src/pages/Login.tsx`, `frontend/src/pages/Callback.tsx`, `frontend/src/hooks/useAuthStore.ts`, `frontend/src/api/client.ts`

Tests: `backend/tests/test_auth.py`, `frontend/src/App.test.tsx`

### audit-domain-engine — Multi-phase security audit domain engine

Status: planned

Acceptance:
- Audit run creation with target specification
- Multi-phase execution (recon, hunting, validation, reporting)
- Coverage ledger tracking
- Findings with evidence artifacts
- Deterministic offline core (no LLM required)

Implementation: `backend/app/models/audit.py`, `backend/app/services/audit_engine.py`, `backend/app/services/coverage.py`, `backend/app/api/audit.py`, `backend/app/services/validators.py`

Tests: `backend/tests/test_audit_engine.py`, `backend/tests/test_coverage.py`

### audit-workflows — Three complete audit workflows

Status: planned

Acceptance:
- Quick audit profile (single hunter wave)
- Standard audit profile (multi-phase with verification)
- Deep audit profile (carried records, extended hunting)
- Export/import of audit runs

Implementation: `backend/app/services/profiles.py`, `backend/app/api/workflows.py`, `frontend/src/components/audit/`, `frontend/src/pages/AuditDashboard.tsx`

Tests: `backend/tests/test_workflows.py`, `frontend/src/pages/AuditDashboard.test.tsx`

### llm-integration — LLM provider adapters (optional advisory explanations)

Status: planned

Acceptance:
- OpenAI-compatible adapter
- Anthropic messages adapter
- Gemini generateContent adapter
- Ollama adapter
- Configurable provider/model/endpoint
- Keys server-side only, redacted errors

Implementation: `backend/app/services/llm_adapters.py`, `backend/app/core/llm_config.py`, `backend/app/api/llm.py`

Tests: `backend/tests/test_llm_adapters.py`

### frontend-dashboard — React dashboard with audit workflows

Status: planned

Acceptance:
- Audit dashboard with create/import/search/detail/export
- Loading/error/empty states
- Typed API client from backend routes
- Real-time progress updates
- Responsive professional UI

Implementation: `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/hooks/`

Tests: `frontend/src/pages/*.test.tsx`

### docs-and-ci — Documentation, CI/CD, and portfolio.json

Status: planned

Acceptance:
- README with install/run/test steps, Mermaid diagram
- CHANGELOG.md
- portfolio.json with required fields
- LICENSE MIT
- GitHub Actions CI workflow
- API docs
- All tests pass

Implementation: `README.md`, `CHANGELOG.md`, `portfolio.json`, `LICENSE`, `.github/workflows/ci.yml`, `docs/`

Tests: `Full test suite passes`

