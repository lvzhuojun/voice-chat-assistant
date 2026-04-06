/**
 * 认证 API
 * Authentication API.
 */

import client from './client'
import type { AuthResponse, User } from '@/types'

/** 注册 / Register */
export const register = (data: {
  email: string
  password: string
  username: string
}) => client.post<AuthResponse>('/auth/register', data)

/** 登录 / Login */
export const login = (data: { email: string; password: string }) =>
  client.post<AuthResponse>('/auth/login', data)

/** 获取当前用户 / Fetch the current authenticated user */
export const getMe = () => client.get<User>('/auth/me')
