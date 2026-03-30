import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 品牌色
        brand: {
          purple: '#7c3aed',
          blue: '#2563eb',
        },
        // 背景
        bg: {
          DEFAULT: '#0a0a0f',
          card: 'rgba(255,255,255,0.05)',
          hover: 'rgba(255,255,255,0.08)',
        },
        // 文字
        text: {
          primary: '#f1f5f9',
          secondary: '#94a3b8',
          muted: '#64748b',
        },
        // 边框
        border: {
          DEFAULT: 'rgba(255,255,255,0.1)',
          hover: 'rgba(255,255,255,0.2)',
        },
      },
      backgroundImage: {
        // 主渐变（紫→蓝）
        'brand-gradient': 'linear-gradient(135deg, #7c3aed 0%, #2563eb 100%)',
        // 深色背景渐变（登录页）
        'dark-gradient': 'linear-gradient(135deg, #0f0a1e 0%, #0a1628 50%, #0a0a0f 100%)',
      },
      borderRadius: {
        DEFAULT: '12px',
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'ripple': 'ripple 1.5s ease-out infinite',
        'fade-in-up': 'fadeInUp 0.4s ease-out',
      },
      keyframes: {
        ripple: {
          '0%': { transform: 'scale(1)', opacity: '0.8' },
          '100%': { transform: 'scale(2.5)', opacity: '0' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      backdropBlur: {
        xl: '24px',
      },
      boxShadow: {
        'glow-purple': '0 0 20px rgba(124, 58, 237, 0.4)',
        'glow-blue': '0 0 20px rgba(37, 99, 235, 0.4)',
        'card': '0 4px 24px rgba(0, 0, 0, 0.4)',
      },
    },
  },
  plugins: [],
}

export default config
