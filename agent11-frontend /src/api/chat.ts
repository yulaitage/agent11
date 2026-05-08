import apiClient from './client'

// Keep frontend skill names aligned with backend SkillRegistry / AgentGenerator.
export type SkillType =
  | 'query'
  | 'troubleshoot'
  | 'maintenance_report'
  | 'prediction'
  | 'flexible_report'
  ;

export interface Message {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  skill?: string
  reasoning_chain?: ReasoningStep[]
  confidence?: number
  map_data?: MapData
  data?: TableData
  sources?: string[]
  pdfData?: string
}

export interface ReasoningStep {
  step: number
  action: string
  observation: string
  conclusion: string
}

export interface MapData {
  center: [number, number]
  zoom: number
  markers: Marker[]
  legend?: Record<string, string>
}

export interface Marker {
  device_id: string
  lat: number
  lng: number
  status: string
  popup: string
}

export interface TableData {
  headers: string[]
  rows: string[][]
  total?: number
}

export interface Chat {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

export interface ChatListItem {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

export interface SendMessageRequest {
  message: string
  skill: SkillType | null
}

export interface SendMessageResponse {
  success: boolean
  message?: Message
  error?: string
}

export interface GetChatsResponse {
  chats: ChatListItem[]
}

export interface GetChatResponse {
  id: string
  title: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

export const chatApi = {
  getChats: async (): Promise<GetChatsResponse> => {
    // FastAPI router uses a trailing slash for collection routes; avoid 307 redirects in prod.
    const response = await apiClient.get<GetChatsResponse>('/chats/')
    return response.data
  },

  getChat: async (chatId: string): Promise<GetChatResponse> => {
    const response = await apiClient.get<GetChatResponse>(`/chats/${chatId}`)
    return response.data
  },

  createChat: async (title?: string): Promise<{ id: string; title: string }> => {
    // FastAPI router uses a trailing slash for collection routes; avoid 307 redirects in prod.
    const response = await apiClient.post('/chats/', { title })
    return response.data
  },

  sendMessage: async (chatId: string, data: SendMessageRequest): Promise<SendMessageResponse> => {
    const response = await apiClient.post<SendMessageResponse>(`/chats/${chatId}/messages`, data)
    return response.data
  },

  deleteChat: async (chatId: string): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.delete(`/chats/${chatId}`)
    return response.data
  },

  updateChatTitle: async (chatId: string, title: string): Promise<{ success: boolean; error?: string }> => {
    const response = await apiClient.put(`/chats/${chatId}`, { title })
    return response.data
  },
}

export default chatApi
