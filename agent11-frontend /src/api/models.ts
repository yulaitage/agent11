import apiClient from './client'

export interface ColumnDetail {
  name: string
  type: string
  nullable: boolean
}

export interface TableInfo {
  name: string
  columns: string[]
  columns_detail: ColumnDetail[]
  row_count: number
}

export interface DatabaseInfo {
  id: string
  name: string
  tables: TableInfo[]
}

export interface SchemaResponse {
  databases: DatabaseInfo[]
}

export interface TableDataResponse {
  table: string
  columns: string[]
  rows: Record<string, string | null>[]
  total: number
  limit: number
  offset: number
}

export const modelsApi = {
  getSchema: async (): Promise<SchemaResponse> => {
    const response = await apiClient.get<SchemaResponse>('/models/schema')
    return response.data
  },

  getTableData: async (
    tableName: string,
    limit = 50,
    offset = 0,
  ): Promise<TableDataResponse> => {
    const response = await apiClient.get<TableDataResponse>(
      `/models/tables/${encodeURIComponent(tableName)}/data`,
      { params: { limit, offset } },
    )
    return response.data
  },

  deleteTable: async (tableName: string): Promise<void> => {
    await apiClient.delete(`/models/tables/${encodeURIComponent(tableName)}`)
  },

  deleteTableRows: async (tableName: string): Promise<void> => {
    await apiClient.delete(`/models/tables/${encodeURIComponent(tableName)}/rows`)
  },

  getViews: async (): Promise<{views: {name: string, definition: string}[]}> => {
    const response = await apiClient.get('/models/views')
    return response.data
  },

  createView: async (name: string, definition: string): Promise<void> => {
    await apiClient.post('/models/views', { name, definition })
  },

  deleteView: async (viewName: string): Promise<void> => {
    await apiClient.delete(`/models/views/${encodeURIComponent(viewName)}`)
  },

  getViewData: async (viewName: string, limit = 50, offset = 0): Promise<TableDataResponse> => {
    const response = await apiClient.get<TableDataResponse>(
      `/models/views/${encodeURIComponent(viewName)}/data`,
      { params: { limit, offset } },
    )
    return response.data
  },
}
