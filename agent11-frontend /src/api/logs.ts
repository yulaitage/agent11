import apiClient from './client'

export interface APILogEntry {
  id: string
  timestamp: string
  method: string
  path: string
  request_body: Record<string, unknown> | null
  response_status: number
  response_body: Record<string, unknown> | null
  duration_ms: number
  user_id: string | null
  thread_id: string | null
  ip_address: string | null
  user_agent: string | null
}

export interface GetLogsResponse {
  logs: APILogEntry[]
  total: number
  limit: number
  offset: number
}

export interface APILogStats {
  total: number
  avg_duration_ms: number
  by_status: Record<number, number>
  by_method: Record<string, number>
}

export interface GetLogsParams {
  status?: number
  method?: string
  path?: string
  start_date?: string
  end_date?: string
  limit?: number
  offset?: number
}

export const logsApi = {
  getLogs: async (params: GetLogsParams = {}): Promise<GetLogsResponse> => {
    const response = await apiClient.get<GetLogsResponse>('/logs/', { params })
    return response.data
  },

  getStats: async (): Promise<APILogStats> => {
    const response = await apiClient.get<APILogStats>('/logs/stats')
    return response.data
  },
}

export default logsApi