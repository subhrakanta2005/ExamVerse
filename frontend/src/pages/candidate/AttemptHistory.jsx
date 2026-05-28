import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { attemptAPI, resultAPI } from '../../services/api'
import clsx from 'clsx'

const STATUS_COLORS = {
  submitted:      'badge-blue',
  auto_submitted: 'badge-blue',
  in_progress:    'badge-yellow',
  timed_out:      'badge-red',
  abandoned:      'badge-gray',
}

const RESULT_COLORS = {
  published: 'badge-green',
  pending:   'badge-yellow',
}

export default function AttemptHistory() {
  const [attempts, setAttempts] = useState([])
  const [results,  setResults]  = useState({})   // keyed by attempt_id
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    Promise.all([attemptAPI.getMyAttempts(), resultAPI.getMy()])
      .then(([attRes, resRes]) => {
        setAttempts(attRes.data || [])
        const byAttempt = {}
        ;(resRes.data || []).forEach(r => { byAttempt[r.attempt_id] = r })
        setResults(byAttempt)
      })
      .finally(() => setLoading(false))
  }, [])

  const formatDate = (iso) =>
    iso
      ? new Date(iso).toLocaleDateString('en-IN', {
          day: 'numeric', month: 'short', year: 'numeric',
          hour: '2-digit', minute: '2-digit',
        })
      : '—'

  // time_spent_seconds lives on the Attempt object, not on Result
  const formatDuration = (secs) => {
    if (!secs) return '—'
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m}m ${s}s`
  }

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Attempt History</h1>
          <p className="text-slate-400 text-sm mt-0.5">All your exam attempts and results</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : attempts.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">📋</div>
            <h3 className="text-lg font-semibold text-white mb-2">No attempts yet</h3>
            <p className="text-slate-400 mb-6">
              You haven't taken any exams. Head to the dashboard to get started.
            </p>
            <Link to="/dashboard" className="btn-primary">Browse Exams</Link>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Exam', 'Started', 'Duration', 'Status', 'Score', 'Result', 'Action'].map(h => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {attempts.map(attempt => {
                  const result = results[attempt.id]
                  const scorePercent =
                    result && result.total_marks > 0
                      ? Math.round((result.obtained_marks / result.total_marks) * 100)
                      : null

                  return (
                    <tr key={attempt.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-4">
                        <p className="font-medium text-white text-sm">
                          {attempt.exam_title || `Exam #${attempt.exam_id}`}
                        </p>
                        <p className="text-slate-500 text-xs mt-0.5">#{attempt.id}</p>
                      </td>
                      <td className="px-4 py-4 text-slate-400 text-sm">
                        {formatDate(attempt.started_at)}
                      </td>
                      <td className="px-4 py-4 text-slate-400 text-sm font-mono">
                        {/* time_spent_seconds is on the Attempt object */}
                        {formatDuration(attempt.time_spent_seconds)}
                      </td>
                      <td className="px-4 py-4">
                        <span className={STATUS_COLORS[attempt.status] || 'badge-gray'}>
                          {attempt.status?.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {scorePercent !== null ? (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={clsx(
                                  'h-full rounded-full',
                                  scorePercent >= 50 ? 'bg-emerald-500' : 'bg-red-500'
                                )}
                                style={{ width: `${scorePercent}%` }}
                              />
                            </div>
                            <span className="text-sm font-mono text-slate-300">
                              {scorePercent}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-600 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {result ? (
                          <span className={RESULT_COLORS[result.status] || 'badge-gray'}>
                            {result.is_passed ? 'Passed' : 'Failed'}
                          </span>
                        ) : (
                          <span className="text-slate-600 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {result ? (
                          <Link
                            to={`/result/${attempt.id}`}
                            className="text-brand-400 hover:text-brand-300 text-sm font-medium transition-colors"
                          >
                            View →
                          </Link>
                        ) : attempt.status === 'in_progress' ? (
                          <Link
                            to={`/exam/${attempt.exam_id}/attempt/${attempt.id}`}
                            className="text-amber-400 hover:text-amber-300 text-sm font-medium"
                          >
                            Resume →
                          </Link>
                        ) : (
                          <span className="text-slate-600 text-sm">Pending</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
