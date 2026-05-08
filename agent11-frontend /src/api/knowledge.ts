import apiClient from './client'

export interface KnowledgeFile {
  id?: string
  filename: string
  path: string
  content?: string
  isFolder?: boolean
  createdAt: string
  updatedAt: string
  children?: KnowledgeFile[]
}

export interface GetKnowledgeResponse {
  success: boolean
  data?: KnowledgeFile[]
  error?: string
}

export interface GetFileResponse {
  success: boolean
  data?: KnowledgeFile
  error?: string
}

export interface SearchKnowledgeRequest {
  query: string
  limit?: number
}

export interface SearchKnowledgeResponse {
  success: boolean
  data?: {
    filename: string
    content: string
    score: number
  }[]
  error?: string
}

export interface FolderRequest {
  name: string
  parentPath?: string
}

export const knowledgeApi = {
  getFiles: async (path?: string): Promise<GetKnowledgeResponse> => {
    const url = path ? `/knowledge?path=${encodeURIComponent(path)}` : '/knowledge'
    const response = await apiClient.get<GetKnowledgeResponse>(url)
    return response.data
  },

  getFile: async (filename: string): Promise<GetFileResponse> => {
    const response = await apiClient.get<GetFileResponse>(`/knowledge/${encodeURIComponent(filename)}`)
    return response.data
  },

  uploadFile: async (file: File, folderPath?: string): Promise<{ success: boolean; data?: { filename: string }; error?: string }> => {
    const formData = new FormData()
    formData.append('file', file)
    if (folderPath) {
      formData.append('path', folderPath)
    }
    // Use apiClient with content-type unset so axios auto-generates boundary
    const response = await apiClient.post('/knowledge/upload', formData, {
      headers: {
        // Override Content-Type to let axios set it with proper boundary
        'Content-Type': undefined,
      },
    })
    return response.data
  },

  deleteFile: async (filename: string): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.delete(`/knowledge/${encodeURIComponent(filename)}`)
    return response.data
  },

  updateFile: async (filename: string, content: string): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.put(`/knowledge/${encodeURIComponent(filename)}`, { content })
    return response.data
  },

  search: async (data: SearchKnowledgeRequest): Promise<SearchKnowledgeResponse> => {
    const response = await apiClient.post<SearchKnowledgeResponse>('/knowledge/search', data)
    return response.data
  },

  createFolder: async (data: FolderRequest): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.post('/knowledge/folder', data)
    return response.data
  },

  deleteFolder: async (path: string): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.delete(`/knowledge/folder/${encodeURIComponent(path)}`)
    return response.data
  },
}

export default knowledgeApi
