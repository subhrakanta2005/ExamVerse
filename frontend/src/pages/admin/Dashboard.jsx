import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { adminAPI, examAPI } from '../../services/api'
import clsx from 'clsx'

function StatCard({ label, value, sub, color = 'text-white', icon }) {
  return (
    <div className="glass-card p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-500 text-sm">{label}</p>
          <p className={clsx('text-4xl font-bold font-mono mt-1', color)}>{value ?? '—'}</p>
          {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
        </div>
        <span className="text-2xl opacity-60">{icon}</span>
      </div>
    </div>
  )
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState(null)
  const [recentExams, setRecentExams] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([adminAPI.overview(), examAPI.getAdminAll(0, 5)])
      .then(([ov, ex]) => {
        setOverview(ov.data)
        setRecentExams(ex.data || [])
      })
      .finally(() => setLoading(false))
  }, [])

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Admin Overview</h1>
            <p className="text-slate-400 text-sm mt-0.5">Platform-wide statistics at a glance</p>
          </div>
          <Link to="/admin/exams/new" className="btn-primary">+ Create Exam</Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="Total Users"    value={overview?.total_users}    icon="◉" color="text-white"      sub="Registered accounts" />
              <StatCard label="Active Exams"   value={overview?.active_exams}   icon="◈" color="text-brand-400"  sub="Published & live" />
              <StatCard label="Total Attempts" value={overview?.total_attempts}  icon="◎" color="text-emerald-400" sub="All time" />
              <StatCard
                label="Avg Score"
                value={overview?.avg_score != null ? `${overview.avg_score.toFixed(1)}%` : '—'}
                icon="◭"
                color="text-amber-400"
                sub="Across all exams"
              />
            </div>

            {/* Quick links */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {[
                { to: '/admin/exams',    label: 'Manage Exams',     desc: 'Create, edit, delete exams',      icon: '◈', color: 'border-brand-500/30 hover:border-brand-500/60' },
                { to: '/admin/users',    label: 'User Management',  desc: 'View and manage candidates',      icon: '◉', color: 'border-emerald-500/30 hover:border-emerald-500/60' },
                { to: '/admin/results',  label: 'Results',          desc: 'Publish and review scores',       icon: '◎', color: 'border-amber-500/30 hover:border-amber-500/60' },
                { to: '/admin/evaluate', label: 'Manual Evaluate',  desc: 'Review subjective answers',       icon: '◐', color: 'border-purple-500/30 hover:border-purple-500/60' },
                { to: '/admin/analytics',label: 'Analytics',        desc: 'Charts & leaderboards',           icon: '◭', color: 'border-cyan-500/30 hover:border-cyan-500/60' },
              ].map(({ to, label, desc, icon, color }) => (
                <Link
                  key={to}
                  to={to}
                  className={clsx('glass-card p-5 border transition-all duration-200 group', color)}
                >
                  <span className="text-2xl">{icon}</span>
                  <p className="font-semibold text-white mt-3 group-hover:text-brand-300 transition-colors">{label}</p>
                  <p className="text-slate-500 text-sm mt-0.5">{desc}</p>
                </Link>
              ))}
            </div>

            {/* Recent Exams */}
            {recentExams.length > 0 && (
              <div className="glass-card overflow-hidden">
                <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                  <h2 className="font-semibold text-white">Recent Exams</h2>
                  <Link to="/admin/exams" className="text-brand-400 text-sm hover:text-brand-300">View all →</Link>
                </div>
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-slate-800">
                      {['Title', 'Duration', 'Questions', 'Status', 'Actions'].map(h => (
                        <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {recentExams.map(exam => (
                      <tr key={exam.id} className="hover:bg-slate-800/30 transition-colors">
                        <td className="px-4 py-3 font-medium text-white text-sm">{exam.title}</td>
                        <td className="px-4 py-3 text-slate-400 text-sm">{exam.duration_minutes}m</td>
                        <td className="px-4 py-3 text-slate-400 text-sm">{exam.question_count ?? '—'}</td>
                        <td className="px-4 py-3">
                          {/* FIX: was exam.is_published (doesn't exist) — use exam.is_active */}
                          <span className={exam.is_active ? 'badge-green' : 'badge-gray'}>
                            {exam.is_active ? 'Active' : 'Draft'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Link to={`/admin/exams/${exam.id}/edit`} className="text-brand-400 hover:text-brand-300 text-sm">Edit →</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Manual eval badge */}
            {overview?.pending_evaluations > 0 && (
              <div className="glass-card p-5 border border-amber-500/30 bg-amber-500/5 flex items-center justify-between">
                <div>
                  <p className="text-amber-400 font-semibold">⚠ Manual Evaluation Required</p>
                  <p className="text-slate-400 text-sm mt-0.5">
                    {overview.pending_evaluations} answer{overview.pending_evaluations !== 1 ? 's' : ''} waiting for manual scoring.
                  </p>
                </div>
                <Link to="/admin/evaluate" className="btn-primary">Review Now</Link>
              </div>
            )}
          </>
        )}
      </div>
    </AppLayout>
  )
}
