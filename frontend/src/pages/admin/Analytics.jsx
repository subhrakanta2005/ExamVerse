import React, { useEffect, useState } from 'react'
import AppLayout from '../../components/layout/AppLayout'
import { adminAPI, examAPI } from '../../services/api'
import clsx from 'clsx'

function BarChart({ data, valueKey = 'value', labelKey = 'label', color = '#6472f1' }) {
  const max = Math.max(...data.map(d => d[valueKey]), 1)
  return (
    <div className="flex items-end gap-2 h-40">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <span className="text-xs text-slate-500 font-mono">{d[valueKey]?.toFixed?.(1) ?? d[valueKey]}</span>
          <div
            className="w-full rounded-t-lg transition-all duration-700"
            style={{ height: `${(d[valueKey] / max) * 100}%`, backgroundColor: color, minHeight: 2 }}
          />
          <span className="text-xs text-slate-500 truncate w-full text-center">{d[labelKey]}</span>
        </div>
      ))}
    </div>
  )
}

export default function AdminAnalytics() {
  const [overview, setOverview] = useState(null)
  const [exams, setExams] = useState([])
  const [selectedExam, setSelectedExam] = useState('')
  const [examAnalytics, setExamAnalytics] = useState(null)
  const [leaderboard, setLeaderboard] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([adminAPI.overview(), examAPI.getAdminAll(0, 100)])
      .then(([ov, ex]) => {
        setOverview(ov.data)
        const exList = ex.data || []
        setExams(exList)
        if (exList.length > 0 && !selectedExam) setSelectedExam(String(exList[0].id))
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedExam) return
    Promise.all([
      adminAPI.examAnalytics(selectedExam),
      adminAPI.leaderboard(selectedExam, 10),
    ]).then(([an, lb]) => {
      setExamAnalytics(an.data)
      setLeaderboard(lb.data || [])
    }).catch(() => {
      setExamAnalytics(null)
      setLeaderboard([])
    })
  }, [selectedExam])

  const statItems = overview ? [
    { label: 'Total Users', value: overview.total_users, color: 'text-white' },
    { label: 'Total Exams', value: overview.total_exams, color: 'text-brand-400' },
    { label: 'Total Attempts', value: overview.total_attempts, color: 'text-emerald-400' },
    { label: 'Avg Score', value: overview.avg_score != null ? `${overview.avg_score.toFixed(1)}%` : '—', color: 'text-amber-400' },
    { label: 'Pass Rate', value: overview.pass_rate != null ? `${overview.pass_rate.toFixed(1)}%` : '—', color: 'text-cyan-400' },
    { label: 'Pending Eval', value: overview.pending_evaluations ?? 0, color: 'text-red-400' },
  ] : []

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-slate-400 text-sm mt-0.5">Platform-wide and per-exam insights</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Overview stats */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {statItems.map(({ label, value, color }) => (
                <div key={label} className="glass-card p-4 text-center">
                  <p className={clsx('text-2xl font-bold font-mono', color)}>{value}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* Per-exam selector */}
            <div className="glass-card p-6 space-y-6">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <h2 className="font-semibold text-white">Exam Analytics</h2>
                <select
                  className="input-field w-auto min-w-48"
                  value={selectedExam}
                  onChange={e => setSelectedExam(e.target.value)}
                >
                  {exams.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}
                </select>
              </div>

              {examAnalytics ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {[
                    { label: 'Attempts', value: examAnalytics.total_attempts },
                    { label: 'Avg Score', value: examAnalytics.avg_score != null ? `${examAnalytics.avg_score.toFixed(1)}%` : '—' },
                    { label: 'Pass Rate', value: examAnalytics.pass_rate != null ? `${examAnalytics.pass_rate.toFixed(1)}%` : '—' },
                    { label: 'Highest', value: examAnalytics.highest_score != null ? `${examAnalytics.highest_score.toFixed(1)}%` : '—' },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-slate-800/50 rounded-xl p-4 text-center">
                      <p className="text-2xl font-bold text-white font-mono">{value ?? '—'}</p>
                      <p className="text-slate-500 text-xs mt-1">{label}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 text-sm">No analytics available for this exam yet.</p>
              )}

              {examAnalytics?.score_distribution && examAnalytics.score_distribution.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-slate-400 mb-3">Score Distribution</p>
                  <BarChart
                    data={examAnalytics.score_distribution}
                    valueKey="count"
                    labelKey="range"
                    color="#6472f1"
                  />
                </div>
              )}
            </div>

            {/* Leaderboard */}
            {leaderboard.length > 0 && (
              <div className="glass-card overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-800">
                  <h2 className="font-semibold text-white">Leaderboard</h2>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-800">
                      {['Rank', 'Candidate', 'Score', 'Percentage', 'Submitted'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {leaderboard.map((entry, i) => (
                      <tr key={entry.user_id || i} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-4 py-4">
                          <span className={clsx(
                            'w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold',
                            i === 0 ? 'bg-amber-500/20 text-amber-400' :
                            i === 1 ? 'bg-slate-500/20 text-slate-300' :
                            i === 2 ? 'bg-orange-500/20 text-orange-400' :
                            'text-slate-500'
                          )}>
                            {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`}
                          </span>
                        </td>
                        <td className="px-4 py-4">
                          <p className="font-medium text-white text-sm">{entry.candidate_name || '—'}</p>
                          <p className="text-slate-500 text-xs">{entry.candidate_email || ''}</p>
                        </td>
                        <td className="px-4 py-4 font-mono text-slate-300 text-sm">{entry.obtained_marks}/{entry.total_marks}</td>
                        <td className="px-4 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div className="h-full bg-brand-500 rounded-full" style={{ width: `${entry.percentage}%` }} />
                            </div>
                            <span className="text-sm font-mono text-slate-300">{entry.percentage?.toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-slate-500 text-xs">
                          {entry.submitted_at ? new Date(entry.submitted_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  )
}
