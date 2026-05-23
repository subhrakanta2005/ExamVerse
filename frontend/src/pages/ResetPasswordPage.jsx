import React, { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { authAPI } from '../services/api'
import toast from 'react-hot-toast'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password.length < 8) return toast.error('Password must be at least 8 characters')
    setLoading(true)
    try {
      await authAPI.resetPassword({ token, new_password: password })
      toast.success('Password reset! Please log in.')
      navigate('/login')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Reset failed. Token may have expired.')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 p-8">
        <div className="text-center">
          <p className="text-red-400 mb-4">Invalid reset link.</p>
          <Link to="/forgot-password" className="btn-primary">Request new link</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 mb-10">
          <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center text-white font-display font-bold">EF</div>
          <span className="font-display font-bold text-2xl text-white">ExamForge</span>
        </div>
        <h2 className="font-display text-3xl font-bold text-white mb-2">New password</h2>
        <p className="text-slate-400 mb-8">Enter your new password below.</p>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="label">New password</label>
            <input type="password" className="input-field" placeholder="Min. 8 characters"
              value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          </div>
          <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
            {loading ? 'Resetting…' : 'Reset password'}
          </button>
        </form>
      </div>
    </div>
  )
}
