import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import toast from 'react-hot-toast'

export default function SignupPage() {
  const navigate = useNavigate()
  const { signup, loading } = useAuthStore()
  const [form, setForm] = useState({ email: '', username: '', full_name: '', password: '' })

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await signup(form)
      toast.success('Account created! Welcome to ExamForge.')
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.message)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 mb-10">
          <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center text-white font-display font-bold">EF</div>
          <span className="font-display font-bold text-2xl text-white">ExamForge</span>
        </div>

        <h2 className="font-display text-3xl font-bold text-white mb-2">Create account</h2>
        <p className="text-slate-400 mb-8">Join ExamForge and start your assessment journey.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Full name</label>
            <input
              type="text"
              className="input-field"
              placeholder="John Doe"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required minLength={2}
            />
          </div>
          <div>
            <label className="label">Username</label>
            <input
              type="text"
              className="input-field"
              placeholder="johndoe"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required minLength={3}
            />
          </div>
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
              placeholder="Min. 8 characters"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required minLength={8}
            />
          </div>

          <button type="submit" className="btn-primary w-full py-3 mt-2" disabled={loading}>
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating account…
              </span>
            ) : 'Create account'}
          </button>
        </form>

        <p className="text-center mt-6 text-slate-400 text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
