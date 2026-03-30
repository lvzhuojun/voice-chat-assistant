/**
 * 注册页面
 * 同登录页设计风格
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mic, Mail, Lock, User, Loader2, AlertCircle } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [username, setUsername] = useState('')
  const { register, isLoading, error, setError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password || !username) {
      setError('请填写所有必填项')
      return
    }
    if (password.length < 6) {
      setError('密码至少需要 6 位')
      return
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致')
      return
    }
    await register(email, password, username)
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden noise-bg">
      {/* 深色渐变背景 */}
      <div className="absolute inset-0 bg-dark-gradient" />

      {/* 背景光晕 */}
      <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-brand-purple/20 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-80 h-80 bg-brand-blue/20 rounded-full blur-[120px] pointer-events-none" />

      {/* 注册卡片 */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="glass-card p-8 shadow-card">
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="w-14 h-14 rounded-2xl bg-brand-gradient flex items-center justify-center mb-4 shadow-glow-purple">
              <Mic className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-text-primary">Voice Chat</h1>
            <p className="text-text-secondary text-sm mt-1">AI 语音对话助手</p>
          </div>

          <h2 className="text-xl font-semibold text-text-primary mb-6 text-center">
            创建账号
          </h2>

          {/* 错误提示 */}
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="flex items-center gap-2 text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3 mb-5 text-sm"
            >
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </motion.div>
          )}

          {/* 表单 */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* 用户名 */}
            <div className="space-y-1.5">
              <label className="text-sm text-text-secondary font-medium">用户名</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="给自己起个名字"
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-brand-purple/60 focus:ring-1 focus:ring-brand-purple/40 transition-all duration-150"
                />
              </div>
            </div>

            {/* 邮箱 */}
            <div className="space-y-1.5">
              <label className="text-sm text-text-secondary font-medium">邮箱</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-brand-purple/60 focus:ring-1 focus:ring-brand-purple/40 transition-all duration-150"
                  autoComplete="email"
                />
              </div>
            </div>

            {/* 密码 */}
            <div className="space-y-1.5">
              <label className="text-sm text-text-secondary font-medium">密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 6 位"
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-brand-purple/60 focus:ring-1 focus:ring-brand-purple/40 transition-all duration-150"
                />
              </div>
            </div>

            {/* 确认密码 */}
            <div className="space-y-1.5">
              <label className="text-sm text-text-secondary font-medium">确认密码</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入密码"
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:border-brand-purple/60 focus:ring-1 focus:ring-brand-purple/40 transition-all duration-150"
                />
              </div>
            </div>

            {/* 注册按钮 */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full btn-gradient text-white font-semibold rounded-xl py-3 mt-2 flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  注册中…
                </>
              ) : (
                '创建账号'
              )}
            </button>
          </form>

          {/* 切换登录 */}
          <p className="text-center text-text-secondary text-sm mt-6">
            已有账号？{' '}
            <Link
              to="/login"
              className="text-brand-purple hover:text-brand-blue transition-colors duration-150 font-medium"
            >
              立即登录
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  )
}
