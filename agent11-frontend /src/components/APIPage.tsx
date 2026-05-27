import React, { useState, useEffect, useRef } from 'react'
import {
  History,
  ExternalLink,
  Search,
  MoreHorizontal,
  Inbox,
  Loader2,
  AlertCircle,
  X,
  ChevronRight,
} from 'lucide-react'
import { logsApi, APILogEntry, GetLogsParams } from '../api/logs'

const STATUS_LABELS: Record<number, string> = {
  200: 'OK',
  201: 'Created',
  204: 'No Content',
  400: 'Bad Request',
  401: 'Unauthorized',
  403: 'Forbidden',
  404: 'Not Found',
  422: 'Validation Error',
  500: 'Server Error',
}

const STATUS_COLOR: Record<string, string> = {
  '2xx': 'bg-green-100 text-green-700',
  '3xx': 'bg-blue-100 text-blue-700',
  '4xx': 'bg-orange-100 text-orange-700',
  '5xx': 'bg-red-100 text-red-700',
}

function getStatusClass(status: number): string {
  if (status >= 200 && status < 300) return STATUS_COLOR['2xx']
  if (status >= 300 && status < 400) return STATUS_COLOR['3xx']
  if (status >= 400 && status < 500) return STATUS_COLOR['4xx']
  return STATUS_COLOR['5xx']
}

const API_REFERENCE_DOCS = [
  {
    title: 'Authentication',
    endpoints: [
      { method: 'POST', path: '/api/auth/login', description: 'Login with email and password' },
      { method: 'POST', path: '/api/auth/register', description: 'Register a new user' },
      { method: 'POST', path: '/api/auth/logout', description: 'Logout current user' },
    ],
  },
  {
    title: 'Chats',
    endpoints: [
      { method: 'GET', path: '/api/chats/', description: 'List all chats for current user' },
      { method: 'POST', path: '/api/chats/', description: 'Create a new chat session' },
      { method: 'GET', path: '/api/chats/:id/messages', description: 'Get messages for a chat' },
      { method: 'POST', path: '/api/chats/:id/messages', description: 'Send a message to a chat' },
    ],
  },
  {
    title: 'Knowledge',
    endpoints: [
      { method: 'GET', path: '/api/knowledge/', description: 'List all knowledge base files' },
      { method: 'POST', path: '/api/knowledge/', description: 'Upload a new knowledge file' },
      { method: 'DELETE', path: '/api/knowledge/:id', description: 'Delete a knowledge file' },
    ],
  },
  {
    title: 'Devices & Data',
    endpoints: [
      { method: 'GET', path: '/api/devices/', description: 'List all devices' },
      { method: 'GET', path: '/api/devices/:id/readings', description: 'Get device readings' },
      { method: 'GET', path: '/api/models/tables', description: 'Get database table schema' },
      { method: 'POST', path: '/api/models/query', description: 'Execute SQL query' },
    ],
  },
  {
    title: 'API Logs',
    endpoints: [
      { method: 'GET', path: '/api/logs/', description: 'List API call logs with filters' },
      { method: 'GET', path: '/api/logs/stats', description: 'Get API call statistics' },
    ],
  },
]

const APIPage: React.FC<{ isApiRefOpen?: boolean; onToggleApiRef?: () => void }> = ({ isApiRefOpen, onToggleApiRef }) => {
  const [logs, setLogs] = useState<APILogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [limit] = useState(30)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const tableRef = useRef<HTMLDivElement>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Use parent state if provided, otherwise use local state
  const [localShowApiRef, setLocalShowApiRef] = useState(false)
  const showApiRef = isApiRefOpen !== undefined ? isApiRefOpen : localShowApiRef
  const setShowApiRef = onToggleApiRef ? () => onToggleApiRef() : setLocalShowApiRef

  const fetchLogs = async (params: GetLogsParams) => {
    setLoading(true)
    setError(null)
    try {
      const res = await logsApi.getLogs(params)
      setLogs(res.logs)
      setTotal(res.total)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load API logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const params: GetLogsParams = { limit, offset }
    if (statusFilter) params.status = parseInt(statusFilter)
    if (searchInput.trim()) params.path = searchInput.trim()
    fetchLogs(params)
  }, [offset, statusFilter, searchInput])

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const handleSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setOffset(0)
    setSearchInput(search)
  }

  const handleStatusFilter = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(e.target.value)
    setOffset(0)
  }

  const handlePrev = () => setOffset(Math.max(0, offset - limit))
  const handleNext = () => setOffset(Math.min(total, offset + limit))

  const columns = [
    { label: 'Timestamp', key: 'timestamp' },
    { label: 'Method', key: 'method', hasFilter: false },
    { label: 'Status', key: 'response_status', hasFilter: true },
    { label: 'Path', key: 'path' },
    { label: 'Duration', key: 'duration_ms' },
    { label: 'Actions', key: 'actions' },
  ]

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* API Reference Modal */}
      {showApiRef && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setShowApiRef(false)} />
          <div className="absolute right-0 top-0 bottom-0 w-[500px] bg-white shadow-xl overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-800">API Reference</h2>
              <button onClick={() => setShowApiRef(false)} className="p-1 hover:bg-slate-100 rounded">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-6 space-y-6">
              {API_REFERENCE_DOCS.map((section) => (
                <div key={section.title}>
                  <h3 className="text-sm font-semibold text-slate-600 uppercase tracking-wider mb-3">
                    {section.title}
                  </h3>
                  <div className="space-y-2">
                    {section.endpoints.map((ep) => (
                      <div key={ep.path} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          ep.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                          ep.method === 'POST' ? 'bg-green-100 text-green-700' :
                          ep.method === 'PUT' ? 'bg-orange-100 text-orange-700' :
                          ep.method === 'DELETE' ? 'bg-red-100 text-red-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {ep.method}
                        </span>
                        <div className="flex-1 min-w-0">
                          <code className="text-sm font-mono text-slate-700 block truncate">{ep.path}</code>
                          <span className="text-xs text-slate-500">{ep.description}</span>
                        </div>
                        <ChevronRight className="w-4 h-4 text-slate-300 flex-shrink-0" />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="p-8">
        <div className="flex items-center gap-2 mb-2">
          <History className="w-5 h-5 text-slate-400" />
          <h1 className="text-xl font-semibold text-slate-800">API History</h1>
          {total > 0 && (
            <span className="ml-2 text-sm text-slate-400">{total} total</span>
          )}
        </div>
        <p className="text-sm text-slate-500 mb-6">
          View all API calls made by the frontend, including request details, response status, and execution time.
        </p>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search path..."
                className="pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700"
            >
              Search
            </button>
          </form>

          <select
            value={statusFilter}
            onChange={handleStatusFilter}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="200">200 OK</option>
            <option value="201">201 Created</option>
            <option value="400">400 Bad Request</option>
            <option value="401">401 Unauthorized</option>
            <option value="404">404 Not Found</option>
            <option value="500">500 Server Error</option>
          </select>

          <label className="flex items-center gap-2 text-sm text-slate-500 ml-auto cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            Auto-scroll to latest
          </label>
        </div>

        {/* Table */}
        <div ref={tableRef} className="border border-slate-200 rounded-lg overflow-hidden shadow-sm max-h-[500px] overflow-y-auto">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-slate-50 z-10">
              <tr className="border-b border-slate-200">
                {columns.map((col) => (
                  <th key={col.key} className="px-4 py-3 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <div className="flex items-center gap-2">
                      {col.label}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={columns.length} className="py-20">
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      <Loader2 className="w-8 h-8 animate-spin mb-2" />
                      <span className="text-sm">Loading...</span>
                    </div>
                  </td>
                </tr>
              )}
              {!loading && error && (
                <tr>
                  <td colSpan={columns.length} className="py-20">
                    <div className="flex flex-col items-center justify-center text-red-400">
                      <AlertCircle className="w-8 h-8 mb-2" />
                      <span className="text-sm">{error}</span>
                    </div>
                  </td>
                </tr>
              )}
              {!loading && !error && logs.length === 0 && (
                <tr>
                  <td colSpan={columns.length} className="py-20">
                    <div className="flex flex-col items-center justify-center text-slate-400">
                      <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mb-4">
                        <Inbox className="w-8 h-8 opacity-20" />
                      </div>
                      <span className="text-sm font-medium">No API calls yet</span>
                    </div>
                  </td>
                </tr>
              )}
              {!loading && !error && logs.map((log) => (
                <tr key={log.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-600">
                    {new Date(log.timestamp).toLocaleString('zh-CN', { hour12: false })}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      log.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                      log.method === 'POST' ? 'bg-green-100 text-green-700' :
                      log.method === 'PUT' ? 'bg-orange-100 text-orange-700' :
                      log.method === 'DELETE' ? 'bg-red-100 text-red-700' :
                      'bg-slate-100 text-slate-700'
                    }`}>
                      {log.method}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusClass(log.response_status)}`}>
                      {log.response_status} {STATUS_LABELS[log.response_status] || ''}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700 font-mono truncate max-w-xs">
                    {log.path}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {log.duration_ms}ms
                  </td>
                  <td className="px-4 py-3">
                    <button className="text-slate-400 hover:text-slate-600">
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div ref={logsEndRef} />
        </div>

        {/* Pagination */}
        {!loading && !error && total > limit && (
          <div className="flex items-center justify-between mt-4">
            <span className="text-sm text-slate-500">
              Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={handlePrev}
                disabled={offset === 0}
                className="px-3 py-1 border border-slate-200 rounded text-sm disabled:opacity-50 hover:bg-slate-50"
              >
                Prev
              </button>
              <button
                onClick={handleNext}
                disabled={offset + limit >= total}
                className="px-3 py-1 border border-slate-200 rounded text-sm disabled:opacity-50 hover:bg-slate-50"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export const APISidebar: React.FC<{ onOpenApiRef?: () => void }> = ({ onOpenApiRef }) => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1">
        <div className="px-2 py-2">
          <button className="w-full flex items-center gap-3 px-3 py-2 text-sm font-medium text-indigo-700 bg-indigo-50 rounded-lg transition-all">
            <History className="w-4 h-4" />
            API history
          </button>
          <button
            onClick={onOpenApiRef}
            className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-slate-600 hover:bg-white hover:shadow-sm rounded-lg transition-all mt-1"
          >
            <div className="flex items-center gap-3">
              <ExternalLink className="w-4 h-4 text-slate-400" />
              API reference
            </div>
            <ExternalLink className="w-3 h-3 text-slate-400" />
          </button>
        </div>
      </div>
    </div>
  )
}

export const APIHeaderExtras: React.FC = () => null

export default APIPage