import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { resultAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function ResultPage() {
  const { attemptId } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    resultAPI.getByAttempt(attemptId)
      .then(r => setResult(r.data))
      .catch(() => toast.error('Result not available yet or access denied'))
      .finally(() => setLoading(false))
  }, [attemptId])

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    </AppLayout>
  )

  if (!result) return (
    <AppLayout>
      <div className="max-w-lg mx-auto text-center py-20">
        <div className="text-5xl mb-4">⏳</div>
        <h2 className="text-2xl font-bold text-white mb-2">Result Pending</h2>
        <p className="text-slate-400 mb-6">Your result hasn't been published yet. Check back later.</p>
        <Link to="/history" className="btn-primary">View Attempt History</Link>
      </div>
    </AppLayout>
  )

  const passed = result.status === 'passed'
  const scorePercent = result.total_marks > 0
    ? Math.round((result.obtained_marks / result.total_marks) * 100)
    : 0

  const circleRadius = 54
  const circleCircumference = 2 * Math.PI * circleRadius
  const circleOffset = circleCircumference - (scorePercent / 100) * circleCircumference

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto space-y-6 animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Exam Result</h1>
            <p className="text-slate-400 text-sm mt-0.5">{result.exam_title || 'Exam'}</p>
          </div>
          <Link to="/history" className="btn-secondary text-sm">← Back to History</Link>
        </div>

        {/* Pass/Fail Banner */}
        <div className={clsx(
          'rounded-2xl p-6 border flex items-center gap-6',
          passed
            ? 'bg-emerald-500/10 border-emerald-500/30'
            : 'bg-red-500/10 border-red-500/30'
        )}>
          <div className={clsx(
            'w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold flex-shrink-0',
            passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
          )}>
            {passed ? '✓' : '✗'}
          </div>
          <div className="flex-1">
            <h2 className={clsx('text-3xl font-bold', passed ? 'text-emerald-400' : 'text-red-400')}>
              {passed ? 'Congratulations!' : 'Better Luck Next Time'}
            </h2>
            <p className="text-slate-300 mt-1">
              You have <span className="font-semibold">{passed ? 'passed' : 'failed'}</span> this exam.
              {result.pass_mark && ` Pass mark was ${result.pass_mark}%.`}
            </p>
          </div>
          <div className="hidden sm:block">
            {/* Score Ring */}
            <svg width="128" height="128" viewBox="0 0 128 128">
              <circle cx="64" cy="64" r={circleRadius} fill="none" stroke="#1e2640" strokeWidth="10" />
              <circle
                cx="64" cy="64" r={circleRadius} fill="none"
                stroke={passed ? '#10b981' : '#ef4444'} strokeWidth="10"
                strokeDasharray={circleCircumference}
                strokeDashoffset={circleOffset}
                strokeLinecap="round"
                transform="rotate(-90 64 64)"
                style={{ transition: 'stroke-dashoffset 1s ease' }}
              />
              <text x="64" y="60" textAnchor="middle" fill="white" fontSize="20" fontWeight="bold">{scorePercent}%</text>
              <text x="64" y="78" textAnchor="middle" fill="#94a3b8" fontSize="10">Score</text>
            </svg>
          </div>
        </div>

        {/* Score Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Obtained', value: result.obtained_marks?.toFixed(1), color: 'text-white' },
            { label: 'Total Marks', value: result.total_marks?.toFixed(1), color: 'text-slate-300' },
            { label: 'Correct', value: result.correct_count ?? '—', color: 'text-emerald-400' },
            { label: 'Wrong', value: result.wrong_count ?? '—', color: 'text-red-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass-card p-5 text-center">
              <p className={clsx('text-3xl font-bold font-mono', color)}>{value}</p>
              <p className="text-slate-500 text-xs mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* Additional stats */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="glass-card p-5">
            <p className="text-slate-400 text-sm mb-1">Unattempted</p>
            <p className="text-2xl font-bold text-amber-400">{result.unattempted_count ?? '—'}</p>
          </div>
          <div className="glass-card p-5">
            <p className="text-slate-400 text-sm mb-1">Time Taken</p>
            <p className="text-2xl font-bold text-slate-200">
              {result.time_taken_seconds != null
                ? `${Math.floor(result.time_taken_seconds / 60)}m ${result.time_taken_seconds % 60}s`
                : '—'}
            </p>
          </div>
          <div className="glass-card p-5">
            <p className="text-slate-400 text-sm mb-1">Rank</p>
            <p className="text-2xl font-bold text-brand-400">{result.rank ? `#${result.rank}` : '—'}</p>
          </div>
        </div>

        {/* Section-wise breakdown */}
        {result.section_breakdown && result.section_breakdown.length > 0 && (
          <div className="glass-card p-6">
            <h3 className="font-semibold text-white mb-4">Section-wise Analysis</h3>
            <div className="space-y-3">
              {result.section_breakdown.map((sec) => {
                const pct = sec.total > 0 ? Math.round((sec.obtained / sec.total) * 100) : 0
                return (
                  <div key={sec.section_id}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-slate-300">{sec.section_name}</span>
                      <span className="text-slate-400">{sec.obtained}/{sec.total} ({pct}%)</span>
                    </div>
                    <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-brand-500 rounded-full transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Pending evaluation notice */}
        {result.status === 'pending_evaluation' && (
          <div className="glass-card p-5 border border-amber-500/30 bg-amber-500/5">
            <p className="text-amber-400 font-medium">⏳ Partial Result</p>
            <p className="text-slate-400 text-sm mt-1">
              Some descriptive/subjective questions are pending manual evaluation.
              Your final score will be updated once the examiner reviews them.
            </p>
          </div>
        )}

        <div className="flex gap-3">
          <Link to="/dashboard" className="btn-primary">Go to Dashboard</Link>
          <Link to="/history" className="btn-secondary">View All Attempts</Link>
        </div>
      </div>
    </AppLayout>
  )
}
