/**
 * Axios HTTP 客户端
 * Axios HTTP client.
 * 自动附加 JWT Token，401 时跳转登录页
 * Automatically attaches the JWT token; redirects to the login page on 401.
 */

import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── 请求拦截器：自动附加 JWT / Request interceptor: auto-attach JWT ──
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── 响应拦截器：401 自动跳转登录 / Response interceptor: redirect to login on 401 ──
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      // 跳转到登录页（避免循环，只在非登录页时跳转）
      // Redirect to the login page (only when not already on /login to avoid redirect loops)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
