import apiClient from './client'

export interface LLMConfig {
  provider: 'ollama' | 'lmstudio' | 'deepseek' | 'zhipu' | 'minimax'
  base_url: string
  model: string
  temperature: number
  timeout: number
  api_key?: string
}

export interface LLMModelsResponse {
  models: string[]
}

export interface LLMConnectionStatus {
  connected: boolean
  provider: string
  model: string
}

export const llmApi = {
  getConfig: async (): Promise<LLMConfig> => {
    const response = await apiClient.get<LLMConfig>('/llm/config')
    return response.data
  },

  updateConfig: async (config: LLMConfig): Promise<{ success: boolean; config: LLMConfig }> => {
    const response = await apiClient.put<{ success: boolean; config: LLMConfig }>('/llm/config', config)
    return response.data
  },

  getAvailableModels: async (): Promise<LLMModelsResponse> => {
    const response = await apiClient.get<LLMModelsResponse>('/llm/models')
    return response.data
  },

  getConnectionStatus: async (): Promise<LLMConnectionStatus> => {
    const response = await apiClient.get<LLMConnectionStatus>('/llm/connection-status')
    return response.data
  },

  testConnection: async (config: LLMConfig): Promise<{ success: boolean; message: string }> => {
    const response = await apiClient.post<{ success: boolean; message: string }>('/llm/test', config)
    return response.data
  },
}

export default llmApi