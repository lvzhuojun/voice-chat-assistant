/**
 * 认证 API
 */

import client from './client'
import type { AuthResponse, User } from '@/types'

/** 注册 */
export const register = (data: {
  email: string
  password: string
  username: string
}) => client.post<AuthResponse>('/auth/register', data)

/** 登录 */
export const login = (data: { email: string; password: string }) =>
  client.post<AuthResponse>('/auth/login', data)

/** 获取当前用户 */
export const getMe = () => client.get<User>('/auth/me')
