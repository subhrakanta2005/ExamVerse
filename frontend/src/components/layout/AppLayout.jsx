import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import clsx from 'clsx'

const candidateNav = [
  { path: '/dashboard',          label: 'Dashboard',        icon: '▦', exact: true },
  { path: '/exams',              label: 'Exams',            icon: '◈' },
  { path: '/history',            label: 'Results',          icon: '◎' },
  { path: '/evaluate',           label: 'Evaluate',         icon: '◐' },
  { path: '/analytics',          label: 'Analytics',        icon: '◭' },
  { path: '/ai-exam-generator',  label: 'AI Exam Generator',icon: '✨' },
]

const adminNav = [
  { path: '/admin',                   label: 'Dashboard',        icon: '▦', exact: true },
  { path: '/admin/exams',             label: 'Exams',            icon: '◈' },
  { path: '/admin/results',           label: 'Results',          icon: '◎' },
  { path: '/admin/evaluate',          label: 'Evaluate',         icon: '◐' },
  { path: '/admin/analytics',         label: 'Analytics',        icon: '◭' },
  { path: '/admin/ai-exam-generator', label: 'AI Exam Generator',icon: '✨' },
  { path: '/admin/users',             label: 'Users',            icon: '◉' },
]

export default function AppLayout({ children }) {
  const { user, logout, isAdmin } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const navItems = isAdmin() ? adminNav : candidateNav

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const isActive = (path, exact) =>
    exact ? location.pathname === path : location.pathname.startsWith(path)

  return (
    <div className="min-h-screen flex bg-slate-950">
      {/* Sidebar */}
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-800',
        'flex flex-col transition-transform duration-300 lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800">
          <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center text-white font-display font-bold text-sm">EV</div>
          <span className="font-display font-bold text-lg text-white tracking-tight">ExamVerse</span>
        </div>

        {/* Role badge */}
        <div className="px-6 py-3">
          <span className={isAdmin() ? 'badge-blue' : 'badge-green'}>
            {isAdmin() ? '⚡ Admin' : '● Candidate'}
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-2 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              onClick={() => setSidebarOpen(false)}
              className={clsx(
                'flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                isActive(item.path, item.exact)
                  ? 'bg-brand-600/20 text-brand-400 border border-brand-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              )}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        {/* User section */}
        <div className="p-4 border-t border-slate-800">
          <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-slate-800/50">
            <div className="w-8 h-8 bg-brand-600 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {user?.full_name?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-xs text-slate-500 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="mt-2 w-full btn-ghost text-sm text-slate-400 hover:text-red-400 justify-center"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main content */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-slate-950/80 backdrop-blur border-b border-slate-800 px-6 py-4 flex items-center gap-4">
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-slate-800 text-slate-400"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <div className="flex-1" />
          <span className="text-xs text-slate-500 font-mono">
            {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </span>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6 animate-fade-in">
          {children}
        </main>
      </div>
    </div>
  )
}
