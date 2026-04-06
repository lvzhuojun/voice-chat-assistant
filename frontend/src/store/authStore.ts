/**
 * 认证状态 Store（Zustand）
 * Authentication state store (Zustand).
 * 持久化到 localStorage
 * Persisted to localStorage.
 */

import { create } from 'zustand'
import type { User } from '@/types'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  setAuth: (user: User, token: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  // 从 localStorage 恢复持久化状态 / Restore persisted state from localStorage
  user: (() => {
    try {
      const u = localStorage.getItem('user')
      return u ? JSON.parse(u) : null
    } catch {
      return null
    }
  })(),
  token: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),

  /** 登录后设置认证状态（同步写 localStorage） / Set auth state after login (synchronously writes to localStorage) */
  setAuth: (user, token) => {
    localStorage.setItem('access_token', token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ user, token, isAuthenticated: true })
  },

  /** 登出：清除所有认证状态 / Logout: clear all authentication state */
  clearAuth: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    set({ user: null, token: null, isAuthenticated: false })
  },
}))
