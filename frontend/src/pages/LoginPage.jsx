import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, loading } = useAuthStore()
  const [form, setForm] = useState({ email: '', password: '' })

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const user = await login(form.email, form.password)
      toast.success(`Welcome back, ${user.full_name}!`)
      navigate(user.role === 'admin' ? '/admin' : '/dashboard')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="min-h-screen flex bg-slate-950">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-gradient-to-br from-brand-950 via-slate-900 to-slate-950 border-r border-slate-800 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,_rgba(100,114,241,0.15)_0%,_transparent_60%)]" />
        <div className="relative">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 bg-brand-600 rounded-xl flex items-center justify-center text-white font-display font-bold">EF</div>
            <span className="font-display font-bold text-2xl text-white">ExamForge</span>
          </div>
          <h1 className="font-display text-5xl font-bold text-white leading-tight mb-6">
            Precision Testing<br />
            <span className="text-brand-400">at Scale.</span>
          </h1>
          <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
            A professional examination platform built for rigorous assessments, real-time monitoring, and detailed analytics.
          </p>
        </div>
        <div className="relative grid grid-cols-3 gap-4">
          {[
            { n: '10+', l: 'Question Types' },
            { n: '100%', l: 'Auto-Graded' },
            { n: 'Real-time', l: 'Analytics' },
          ].map((s) => (
            <div key={s.l} className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
              <p className="font-display font-bold text-2xl text-brand-400">{s.n}</p>
              <p className="text-xs text-slate-500 mt-1">{s.l}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center text-white font-display font-bold text-sm">EF</div>
            <span className="font-display font-bold text-xl text-white">ExamForge</span>
          </div>

          <h2 className="font-display text-3xl font-bold text-white mb-2">Sign in</h2>
          <p className="text-slate-400 mb-8">Enter your credentials to access your account.</p>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="label">Email address</label>
              <input
                type="email"
                className="input-field"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>

            <div className="flex justify-end">
              <Link to="/forgot-password" className="text-sm text-brand-400 hover:text-brand-300 transition-colors">
                Forgot password?
              </Link>
            </div>

            <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in…
                </span>
              ) : 'Sign in'}
            </button>
          </form>

          <p className="text-center mt-6 text-slate-400 text-sm">
            Don't have an account?{' '}
            <Link to="/signup" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              Create one
            </Link>
          </p>

          {/* Demo credentials */}
          <div className="mt-8 p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-500 space-y-1">
            <p className="font-semibold text-slate-400 mb-2">Demo Credentials</p>
            <p>Admin: <span className="font-mono text-slate-300">admin@examforge.io</span> / <span className="font-mono text-slate-300">Admin@1234</span></p>
            <p>Candidate: <span className="font-mono text-slate-300">candidate@example.com</span> / <span className="font-mono text-slate-300">Candidate@1234</span></p>
          </div>
        </div>
      </div>
    </div>
  )
}
