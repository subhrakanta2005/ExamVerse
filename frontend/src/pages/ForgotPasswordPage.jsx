import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import toast from 'react-hot-toast'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authAPI.forgotPassword(email)
      setSent(true)
      toast.success('Reset email sent!')
    } catch {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2 mb-10">
          <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center text-white font-display font-bold">EF</div>
          <span className="font-display font-bold text-2xl text-white">ExamForge</span>
        </div>

        {sent ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mx-auto mb-4 text-3xl">✉</div>
            <h2 className="font-display text-2xl font-bold text-white mb-3">Check your email</h2>
            <p className="text-slate-400">If <span className="text-white">{email}</span> is registered, you'll receive a reset link shortly.</p>
            <Link to="/login" className="mt-6 btn-primary inline-flex">Back to sign in</Link>
          </div>
        ) : (
          <>
            <h2 className="font-display text-3xl font-bold text-white mb-2">Reset password</h2>
            <p className="text-slate-400 mb-8">Enter your email and we'll send you a reset link.</p>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="label">Email address</label>
                <input type="email" className="input-field" placeholder="you@example.com"
                  value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
                {loading ? 'Sending…' : 'Send reset link'}
              </button>
            </form>
            <p className="text-center mt-6 text-slate-400 text-sm">
              <Link to="/login" className="text-brand-400 hover:text-brand-300 transition-colors">← Back to sign in</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export default ForgotPasswordPage
