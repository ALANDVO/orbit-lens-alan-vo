import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Loader2, AlertCircle, Download, FileText, Bug, Shield, Search, Filter, Clock, XCircle, CheckCircle } from 'lucide-react'
import { auditApi, AuditRun, Finding, CoverageUnit } from '@/api/client'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'
const severityColors: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-blue-100 text-blue-700',
  info: 'bg-gray-100 text-gray-700',
  hardening: 'bg-purple-100 text-purple-700',
}

const findingStatusColors: Record<string, string> = {
  planned: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-blue-100 text-blue-700',
  confirmed: 'bg-green-100 text-green-700',
  needs_validation: 'bg-yellow-100 text-yellow-700',
  rejected: 'bg-red-100 text-red-700',
  deferred: 'bg-purple-100 text-purple-700',
  out_of_scope: 'bg-gray-100 text-gray-500',
}

const coverageStatusColors: Record<string, string> = {
  planned: 'bg-gray-100 text-gray-700',
  in_progress: 'bg-blue-100 text-blue-700',
  covered: 'bg-green-100 text-green-700',
  blocked: 'bg-red-100 text-red-700',
  candidate: 'bg-yellow-100 text-yellow-700',
  deferred: 'bg-purple-100 text-purple-700',
  out_of_scope: 'bg-gray-100 text-gray-500',
}

export function AuditDetail() {
  const { runId } = useParams<{ runId: string }>()
  const [audit, setAudit] = useState<AuditRun | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [coverage, setCoverage] = useState<CoverageUnit[]>([])
  const [loading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'findings' | 'coverage'>('overview')
  const [findingPage, setFindingPage] = useState(1)
  const [findingTotalPages, setFindingTotalPages] = useState(1)
  const [coveragePage, setCoveragePage] = useState(1)
  const [coverageTotalPages, setCoverageTotalPages] = useState(1)
  const pageSize = 10
  const [findingStatusFilter, setFindingStatusFilter] = useState<string>('')
  const [findingSeverityFilter, setFindingSeverityFilter] = useState<string>('')
  const [coverageStatusFilter, setCoverageStatusFilter] = useState<string>('')
  const [coveragePhaseFilter, setCoveragePhaseFilter] = useState<string>('')

  useEffect(() => {
    if (runId) {
      fetchAudit()
      fetchFindings()
      fetchCoverage()
    }
  }, [runId])

  const fetchAudit = async () => {
    try {
      const response = await auditApi.get(runId!)
      setAudit(response.data)
    } catch (err) {
      setError('Failed to load audit')
      console.error(err)
    }
  }

  const fetchFindings = async () => {
    try {
      const response = await auditApi.getFindings(runId!, {
        page: findingPage,
        page_size: pageSize,
        status: findingStatusFilter || undefined,
        severity: findingSeverityFilter || undefined,
      })
      setFindings(response.data.items)
      setFindingTotalPages(response.data.total_pages)
    } catch (err) {
      console.error(err)
    }
  }

  const fetchCoverage = async () => {
    try {
      const response = await auditApi.getCoverage(runId!, {
        page: coveragePage,
        page_size: pageSize,
        status: coverageStatusFilter || undefined,
        phase: coveragePhaseFilter ? parseInt(coveragePhaseFilter) : undefined,
      })
      setCoverage(response.data.items)
      setCoverageTotalPages(response.data.total_pages)
    } catch (err) {
      console.error(err)
    }
  }

  const handleExport = async (format: 'json' | 'sarif') => {
    try {
      const response = await auditApi.exportRun(runId!, format)
      const blob = new Blob([response.data], { type: format === 'json' ? 'application/json' : 'application/sarif+json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${runId}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error(err)
    }
  }

  if (loading && !audit) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <AlertCircle className="h-12 w-12 text-red-600 mx-auto" />
        <p className="mt-4 text-gray-600">{error}</p>
        <Link to="/" className="mt-4 inline-block text-blue-600 hover:underline">Back to dashboard</Link>
      </div>
    )
  }

  if (!audit) return null

  const statusColors: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-700',
    running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    cancelled: 'bg-yellow-100 text-yellow-700',
  }

  const statusIcons: Record<string, React.ReactNode> = {
    pending: <Clock className="h-4 w-4" />,
    running: <Loader2 className="h-4 w-4 animate-spin" />,
    completed: <CheckCircle className="h-4 w-4" />,
    failed: <AlertCircle className="h-4 w-4" />,
    cancelled: <XCircle className="h-4 w-4" />,
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link to="/" className="text-blue-600 hover:underline text-sm mb-2 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Audit Run {audit.run_id.slice(0, 12)}…</h1>
          <p className="text-gray-500 mt-1">{audit.target_path} • {audit.profile} profile</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('inline-flex items-center gap-1.5 px-3 py-1 text-sm font-medium rounded-full', statusColors[audit.status])}>
            {statusIcons[audit.status]}
            {audit.status.charAt(0).toUpperCase() + audit.status.slice(1)}
          </span>
          <button onClick={() => handleExport('json')} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4 mr-1" /> JSON
          </button>
          <button onClick={() => handleExport('sarif')} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
            <Download className="h-4 w-4 mr-1" /> SARIF
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="border-b border-gray-200">
          <nav className="flex gap-4 p-4" aria-label="Audit tabs">
            <button
              onClick={() => setActiveTab('overview')}
              className={cn('px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeTab === 'overview' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('findings')}
              className={cn('px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeTab === 'findings' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
            >
              Findings ({findings.length})
            </button>
            <button
              onClick={() => setActiveTab('coverage')}
              className={cn('px-4 py-2 text-sm font-medium border-b-2 transition-colors', activeTab === 'coverage' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700')}
            >
              Coverage ({coverage.length})
            </button>
          </nav>
        </div>

        <div className="p-4">
          {activeTab === 'overview' && <OverviewTab audit={audit} />}
          {activeTab === 'findings' && <FindingsTab findings={findings} fetchFindings={fetchFindings} page={findingPage} totalPages={findingTotalPages} setPage={setFindingPage} statusFilter={findingStatusFilter} setStatusFilter={setFindingStatusFilter} severityFilter={findingSeverityFilter} setSeverityFilter={setFindingSeverityFilter} />}
          {activeTab === 'coverage' && <CoverageTab coverage={coverage} fetchCoverage={fetchCoverage} page={coveragePage} totalPages={coverageTotalPages} setPage={setCoveragePage} statusFilter={coverageStatusFilter} setStatusFilter={setCoverageStatusFilter} phaseFilter={coveragePhaseFilter} setPhaseFilter={setCoveragePhaseFilter} audit={audit} />}
        </div>
      </div>
    </div>
  )
}

function OverviewTab({ audit }: { audit: AuditRun }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Target" value={audit.target_path} icon={<FileText className="h-5 w-5" />} />
        <StatCard title="Profile" value={audit.profile} icon={<Shield className="h-5 w-5" />} />
        <StatCard title="Phases" value={`${audit.current_phase}/${audit.total_phases}`} icon={<Bug className="h-5 w-5" />} />
        <StatCard title="Created" value={formatDistanceToNow(new Date(audit.created_at), { addSuffix: true })} icon={<Clock className="h-5 w-5" />} />
      </div>

      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-3">Configuration</h3>
        <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">{JSON.stringify(audit.config, null, 2)}</pre>
      </div>

      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-3">Metadata</h3>
        <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">{JSON.stringify(audit.metadata, null, 2)}</pre>
      </div>
    </div>
  )
}

function StatCard({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="flex items-center gap-2 text-gray-500 mb-1">
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="text-lg font-semibold text-gray-900 truncate">{value}</p>
    </div>
  )
}

function FindingsTab({
  findings,
  fetchFindings,
  page,
  totalPages,
  setPage,
  statusFilter,
  setStatusFilter,
  severityFilter,
  setSeverityFilter,
}: {
  findings: Finding[]
  fetchFindings: () => void
  page: number
  totalPages: number
  setPage: (page: number) => void
  statusFilter: string
  setStatusFilter: (filter: string) => void
  severityFilter: string
  setSeverityFilter: (filter: string) => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); fetchFindings(); }}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="planned">Planned</option>
            <option value="in_progress">In Progress</option>
            <option value="confirmed">Confirmed</option>
            <option value="needs_validation">Needs Validation</option>
            <option value="rejected">Rejected</option>
            <option value="deferred">Deferred</option>
            <option value="out_of_scope">Out of Scope</option>
          </select>
        </div>
        <div className="relative flex-1 min-w-[200px]">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={severityFilter}
            onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); fetchFindings(); }}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
            <option value="info">Info</option>
            <option value="hardening">Hardening</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full" role="table">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Finding ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Severity</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Attack Class</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Location</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {findings.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-500">No findings found</td>
              </tr>
            ) : (
              findings.map((finding) => (
                <tr key={finding.finding_id} className="hover:bg-gray-50">
                  <td className="px-4 py-4 text-sm font-mono text-gray-900">{finding.finding_id.slice(0, 12)}…</td>
                  <td className="px-4 py-4 text-sm text-gray-900 max-w-md truncate" title={finding.title}>{finding.title}</td>
                  <td className="px-4 py-4">
                    <span className={cn('inline-flex px-2 py-1 text-xs font-medium rounded-full', severityColors[finding.severity])}>
                      {finding.severity}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <span className={cn('inline-flex px-2 py-1 text-xs font-medium rounded-full', findingStatusColors[finding.status])}>
                      {finding.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-700">{finding.attack_class}</td>
                  <td className="px-4 py-4 text-sm text-gray-500 font-mono">
                    {finding.file_path ? `${finding.file_path}${finding.line_start ? `:${finding.line_start}` : ''}` : 'N/A'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </div>
  )
}

function CoverageTab({
  coverage,
  fetchCoverage,
  page,
  totalPages,
  setPage,
  statusFilter,
  setStatusFilter,
  phaseFilter,
  setPhaseFilter,
  audit,
}: {
  coverage: CoverageUnit[]
  fetchCoverage: () => void
  page: number
  totalPages: number
  setPage: (page: number) => void
  statusFilter: string
  setStatusFilter: (filter: string) => void
  phaseFilter: string
  setPhaseFilter: (filter: string) => void
  audit: AuditRun
}) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4">
        <div className="relative flex-1 min-w-[200px]">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); fetchCoverage(); }}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="planned">Planned</option>
            <option value="in_progress">In Progress</option>
            <option value="covered">Covered</option>
            <option value="blocked">Blocked</option>
            <option value="candidate">Candidate</option>
            <option value="deferred">Deferred</option>
            <option value="out_of_scope">Out of Scope</option>
          </select>
        </div>
        <div className="relative flex-1 min-w-[200px]">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={phaseFilter}
            onChange={(e) => { setPhaseFilter(e.target.value); setPage(1); fetchCoverage(); }}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Phases</option>
            {Array.from({ length: audit.total_phases }, (_, i) => i + 1).map((phase) => (
              <option key={phase} value={String(phase)}>Phase {phase}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full" role="table">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Unit ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Phase</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Hunter</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Method</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Target Files</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Invariant</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {coverage.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-gray-500">No coverage units found</td>
              </tr>
            ) : (
              coverage.map((unit) => (
                <tr key={unit.unit_id} className="hover:bg-gray-50">
                  <td className="px-4 py-4 text-sm font-mono text-gray-900">{unit.unit_id.slice(0, 12)}…</td>
                  <td className="px-4 py-4 text-sm text-gray-900">{unit.phase}</td>
                  <td className="px-4 py-4 text-sm text-gray-500">{unit.hunter_id || 'N/A'}</td>
                  <td className="px-4 py-4">
                    <span className={cn('inline-flex px-2 py-1 text-xs font-medium rounded-full', coverageStatusColors[unit.status])}>
                      {unit.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-700">{unit.method || 'N/A'}</td>
                  <td className="px-4 py-4 text-sm text-gray-500 truncate max-w-xs">{unit.target_files.join(', ')}</td>
                  <td className="px-4 py-4 text-sm text-gray-700 max-w-md truncate" title={unit.invariant}>{unit.invariant}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      )}
    </div>
  )
}

function Pagination({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (page: number) => void }) {
  return (
    <div className="flex items-center justify-between border-t border-gray-200 pt-4">
      <p className="text-sm text-gray-700">Page {page} of {totalPages}</p>
      <div className="flex gap-2">
        <button onClick={() => onPageChange(page - 1)} disabled={page === 1} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50">Previous</button>
        <button onClick={() => onPageChange(page + 1)} disabled={page === totalPages} className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50">Next</button>
      </div>
    </div>
  )
}