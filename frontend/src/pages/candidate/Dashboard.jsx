import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { examAPI, resultAPI } from '../../services/api'
import useAuthStore from '../../store/authStore'
import toast from 'react-hot-toast'
import { format } from 'date-fns'

function ExamCard({ exam, onStart }) {
  const now = new Date()
  const isAvailable = exam.is_active &&
    (!exam.start_time || new Date(exam.start_time) <= now) &&
    (!exam.end_time || new Date(exam.end_time) >= now)

  return (
    <div className="glass-card p-6 flex flex-col gap-4 hover:border-brand-500/30 transition-all duration-200">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-white text-lg leading-tight">{exam.title}</h3>
          <p className="text-slate-400 text-sm mt-1 line-clamp-2">{exam.description}</p>
        </div>
        <span className={isAvailable ? 'badge-green' : 'badge-gray'}>
          {isAvailable ? 'Live' : 'Unavailable'}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        {[
          { label: 'Duration', value: `${exam.duration_minutes}m` },
          { label: 'Marks', value: exam.total_marks },
          { label: 'Questions', value: exam.question_count || '—' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-800/50 rounded-xl p-3">
            <p className="text-lg font-bold text-white font-mono">{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {exam.end_time && (
        <p className="text-xs text-amber-400">
          ⏰ Closes {format(new Date(exam.end_time), 'MMM d, yyyy h:mm a')}
        </p>
      )}

      <button
        className="btn-primary"
        disabled={!isAvailable}
        onClick={() => onStart(exam.id)}
      >
        {isAvailable ? 'View Instructions →' : 'Not Available'}
      </button>
    </div>
  )
}

export default function CandidateDashboard() {
  const [exams, setExams] = useState([])
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const { user } = useAuthStore()

  useEffect(() => {
    Promise.all([examAPI.getAvailable(), resultAPI.getMy()])
      .then(([exRes, rRes]) => {
        setExams(exRes.data)
        setResults(rRes.data)
      })
      .catch(() => toast.error('Failed to load data'))
      .finally(() => setLoading(false))
  }, [])

  const handleStart = (examId) => navigate(`/exam/${examId}/instructions`)

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    </AppLayout>
  )

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-8 animate-slide-up">
        {/* Header */}
        <div>
          <h1 className="font-display text-3xl font-bold text-white">
            Welcome back, {user?.full_name?.split(' ')[0]} 👋
          </h1>
          <p className="text-slate-400 mt-1">Your available exams and recent results.</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Available Exams', value: exams.length, icon: '◈' },
            { label: 'Completed', value: results.length, icon: '◎' },
            { label: 'Passed', value: results.filter(r => r.is_passed).length, icon: '✓' },
            { label: 'Avg Score', value: results.length ? `${Math.round(results.reduce((a, r) => a + r.percentage, 0) / results.length)}%` : '—', icon: '◭' },
          ].map(({ label, value, icon }) => (
            <div key={label} className="glass-card p-5">
              <p className="text-2xl mb-1">{icon}</p>
              <p className="font-display text-3xl font-bold text-white">{value}</p>
              <p className="text-xs text-slate-500 mt-1">{label}</p>
            </div>
          ))}
        </div>

        {/* Available Exams */}
        <div>
          <h2 className="font-display text-xl font-bold text-white mb-4">Available Exams</h2>
          {exams.length === 0 ? (
            <div className="glass-card p-12 text-center">
              <p className="text-4xl mb-3">◈</p>
              <p className="text-slate-400">No exams available right now.</p>
              <p className="text-slate-500 text-sm mt-1">Check back later or contact your administrator.</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
              {exams.map((exam) => (
                <ExamCard key={exam.id} exam={exam} onStart={handleStart} />
              ))}
            </div>
          )}
        </div>

        {/* Recent Results */}
        {results.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-display text-xl font-bold text-white">Recent Results</h2>
              <button onClick={() => navigate('/history')} className="btn-ghost text-sm">View all →</button>
            </div>
            <div className="glass-card overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800">
                    <th className="text-left px-5 py-3 text-slate-500 font-medium">Exam</th>
                    <th className="text-center px-4 py-3 text-slate-500 font-medium">Score</th>
                    <th className="text-center px-4 py-3 text-slate-500 font-medium">Status</th>
                    <th className="text-right px-5 py-3 text-slate-500 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {results.slice(0, 5).map((r) => (
                    <tr key={r.id} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                      <td className="px-5 py-3.5 text-white font-medium">Exam #{r.exam_id}</td>
                      <td className="px-4 py-3.5 text-center">
                        <span className="font-mono text-brand-400 font-semibold">{r.percentage.toFixed(1)}%</span>
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        <span className={r.is_passed ? 'badge-green' : 'badge-red'}>
                          {r.is_passed ? 'Passed' : 'Failed'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-right text-slate-500">
                        {format(new Date(r.created_at), 'MMM d, yy')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
