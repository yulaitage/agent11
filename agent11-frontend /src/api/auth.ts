import apiClient from './client'

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  userName: string
  email: string
  password: string
}

export interface AuthResponse {
  success: boolean
  data?: {
    token: string
    user: {
      userId: string
      userName: string
      email: string
      profilePicture?: string
    }
  }
  error?: string
}

export const authApi = {
  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login', data)
    return response.data
  },

  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/register', data)
    return response.data
  },

  getMe: async (): Promise<{ success: boolean; data?: AuthResponse['data']['user']; error?: string }> => {
    const response = await apiClient.get('/auth/me')
    return response.data
  },
}

export default authApi
