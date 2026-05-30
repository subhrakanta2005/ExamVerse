import React, { useEffect, useState } from 'react'
import AppLayout from '../../components/layout/AppLayout'
import { resultAPI, examAPI } from '../../services/api'
import clsx from 'clsx'
import { format } from 'date-fns'

function BarChart({ data, valueKey = 'value', labelKey = 'label', color = '#6472f1' }) {
  const max = Math.max(...data.map(d => d[valueKey]), 1)
  return (
    <div className="flex items-end gap-2 h-40">
      {data.map((d, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1">
          <span className="text-xs text-slate-500 font-mono">{d[valueKey]}</span>
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

export default function CandidateAnalytics() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    resultAPI.getMy()
      .then(r => setResults(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const total      = results.length
  const passed     = results.filter(r => r.is_passed).length
  const avgScore   = total ? (results.reduce((a, r) => a + r.percentage, 0) / total).toFixed(1) : '—'
  const passRate   = total ? ((passed / total) * 100).toFixed(1) : '—'
  const highest    = total ? Math.max(...results.map(r => r.percentage)).toFixed(1) : '—'
  const lowest     = total ? Math.min(...results.map(r => r.percentage)).toFixed(1) : '—'

  // Score distribution buckets
  const buckets = ['0–20','21–40','41–60','61–80','81–100'].map(label => {
    const [lo, hi] = label.split('–').map(Number)
    return { label, value: results.filter(r => r.percentage >= lo && r.percentage <= hi).length }
  })

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-slate-400 text-sm mt-0.5">Your personal performance statistics</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : total === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">◭</div>
            <h3 className="text-lg font-semibold text-white mb-2">No data yet</h3>
            <p className="text-slate-400">Complete some exams to see your analytics.</p>
          </div>
        ) : (
          <>
            {/* Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {[
                { label: 'Attempts',  value: total,    color: 'text-white' },
                { label: 'Passed',    value: passed,   color: 'text-emerald-400' },
                { label: 'Avg Score', value: `${avgScore}%`, color: 'text-brand-400' },
                { label: 'Pass Rate', value: `${passRate}%`, color: 'text-cyan-400' },
                { label: 'Highest',   value: `${highest}%`,  color: 'text-amber-400' },
                { label: 'Lowest',    value: `${lowest}%`,   color: 'text-red-400' },
              ].map(({ label, value, color }) => (
                <div key={label} className="glass-card p-4 text-center">
                  <p className={clsx('text-2xl font-bold font-mono', color)}>{value}</p>
                  <p className="text-slate-500 text-xs mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* Score distribution */}
            <div className="glass-card p-6 space-y-4">
              <h2 className="font-semibold text-white">Score Distribution</h2>
              <BarChart data={buckets} valueKey="value" labelKey="label" color="#6472f1" />
            </div>

            {/* Recent results */}
            <div className="glass-card overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800">
                <h2 className="font-semibold text-white">Attempt History</h2>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-800">
                    {['Exam', 'Score', 'Percentage', 'Status', 'Date'].map(h => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {results.map(r => (
                    <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-4 text-white text-sm font-medium">Exam #{r.exam_id}</td>
                      <td className="px-4 py-4 font-mono text-slate-300 text-sm">{r.obtained_marks}/{r.total_marks}</td>
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  )
}
