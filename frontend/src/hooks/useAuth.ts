/**
 * 认证 Hook
 * 封装登录、注册、登出逻辑
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import * as authApi from '@/api/auth'

export function useAuth() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { setAuth, clearAuth, user, isAuthenticated } = useAuthStore()
  const navigate = useNavigate()

  /** 登录 */
  const login = async (email: string, password: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await authApi.login({ email, password })
      setAuth(res.data.user, res.data.access_token)
      navigate('/chat')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? '登录失败，请检查邮箱和密码'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  /** 注册 */
  const register = async (
    email: string,
    password: string,
    username: string
  ) => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await authApi.register({ email, password, username })
      setAuth(res.data.user, res.data.access_token)
      navigate('/chat')
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? '注册失败，请重试'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }

  /** 登出 */
  const logout = () => {
    clearAuth()
    navigate('/login')
  }

  return { login, register, logout, isLoading, error, setError, user, isAuthenticated }
}
