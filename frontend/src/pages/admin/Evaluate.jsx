import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { resultAPI } from '../../services/api'
import { format } from 'date-fns'

export default function AdminEvaluate() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    resultAPI.getMy()
      .then(r => setResults(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">My Results</h1>
          <p className="text-slate-400 text-sm mt-0.5">Review your exam submissions and detailed answers</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : results.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">✓</div>
            <h3 className="text-lg font-semibold text-white mb-2">No results yet</h3>
            <p className="text-slate-400 mb-6">Complete an exam to see your results here.</p>
            <button className="btn-primary" onClick={() => navigate('/dashboard')}>
              Go to Dashboard
            </button>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Exam', 'Score', 'Percentage', 'Status', 'Date', ''].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {results.map(r => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-4 text-white text-sm font-medium">Exam #{r.exam_id}</td>
                    <td className="px-4 py-4 font-mono text-slate-300 text-sm">
                      {r.obtained_marks}/{r.total_marks}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full bg-brand-500 rounded-full" style={{ width: `${r.percentage}%` }} />
                        </div>
                        <span className="text-sm font-mono text-slate-300">{r.percentage?.toFixed(1)}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className={r.is_passed ? 'badge-green' : 'badge-red'}>
                        {r.is_passed ? 'Passed' : 'Failed'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-500 text-xs">
                      {r.created_at ? format(new Date(r.created_at), 'MMM d, yy') : '—'}
                    </td>
                    <td className="px-4 py-4">
                      <button
                        className="text-brand-400 hover:text-brand-300 text-sm font-medium transition-colors"
                        onClick={() => navigate(`/result/${r.attempt_id}`)}
                      >
                        Review →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
