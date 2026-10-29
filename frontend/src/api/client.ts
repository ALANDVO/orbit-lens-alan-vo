import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = sessionStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && originalRequest && !originalRequest.url?.includes('/auth/refresh')) {
      // Try to refresh the token
      try {
        const refreshResponse = await axios.post('/api/v1/auth/refresh', {}, {
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem('access_token')}`,
          },
          withCredentials: true,
        })
        const newAccessToken = refreshResponse.data.access_token
        sessionStorage.setItem('access_token', newAccessToken)
        // Retry the original request with new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        }
        return api(originalRequest)
      } catch {
        // Refresh failed, redirect to login
        sessionStorage.removeItem('access_token')
        sessionStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export interface ApiResponse<T> {
  data: T
  meta?: {
    page?: number
    page_size?: number
    total?: number
  }
}

export interface AuditRun {
  id: number
  run_id: string
  owner_id: number
  target_path: string
  target_type: string
  profile: 'quick' | 'standard' | 'deep'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  current_phase: number
  total_phases: number
  config: Record<string, unknown>
  metadata: Record<string, unknown>
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface Finding {
  id: number
  finding_id: string
  audit_run_id: number
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info' | 'hardening'
  status: 'planned' | 'in_progress' | 'confirmed' | 'needs_validation' | 'rejected' | 'deferred' | 'out_of_scope'
  attack_class: string
  file_path: string | null
  line_start: number | null
  line_end: number | null
  evidence: Record<string, unknown>
  remediation: string | null
  tags: string[]
  verifier_notes: string | null
  created_at: string
  updated_at: string
  confirmed_at: string | null
}

export interface CoverageUnit {
  id: number
  unit_id: string
  audit_run_id: number
  phase: number
  hunter_id: string | null
  target_files: string[]
  invariant: string
  status: string
  method: string | null
  result: string | null
  artifacts: Array<Record<string, unknown>>
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateAuditRunRequest {
  target_path: string
  target_type: 'local' | 'git' | 'archive'
  profile: 'quick' | 'standard' | 'deep'
  config?: Record<string, unknown>
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const auditApi = {
  list: (params?: { page?: number; page_size?: number; status?: string }) =>
    api.get<PaginatedResponse<AuditRun>>('/audits', { params }),

  get: (runId: string) =>
    api.get<AuditRun>(`/audits/${runId}`),

  create: (data: CreateAuditRunRequest) =>
    api.post<AuditRun>('/audits', data),

  delete: (runId: string) =>
    api.delete(`/audits/${runId}`),

  getFindings: (runId: string, params?: { page?: number; page_size?: number; status?: string; severity?: string }) =>
    api.get<PaginatedResponse<Finding>>(`/audits/${runId}/findings`, { params }),

  getCoverage: (runId: string, params?: { page?: number; page_size?: number; phase?: number; status?: string }) =>
    api.get<PaginatedResponse<CoverageUnit>>(`/audits/${runId}/coverage`, { params }),

  exportRun: (runId: string, format: 'json' | 'sarif' = 'json') =>
    api.get(`/audits/${runId}/export`, { params: { format }, responseType: 'blob' }),
}

export const healthApi = {
  check: () => api.get<{ status: string; version: string; timestamp: string }>('/health'),
  db: () => api.get<{ status: string; database: string }>('/health/db'),
}