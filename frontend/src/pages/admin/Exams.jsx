import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { examAPI } from '../../services/api'
import toast from 'react-hot-toast'

export default function Exams() {
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const navigate = useNavigate()

  const loadExams = () => {
    setLoading(true)
    examAPI.getAvailable()
      .then(r => setExams(r.data || []))
      .catch(() => toast.error('Failed to load exams'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadExams() }, [])

  const handleDelete = async (exam) => {
    if (!window.confirm(`Delete "${exam.title}"? This cannot be undone.`)) return
    setDeleting(exam.id)
    try {
      await examAPI.delete(exam.id)
      setExams(prev => prev.filter(e => e.id !== exam.id))
      toast.success('Exam deleted')
    } catch {
      toast.error('Failed to delete exam')
    } finally {
      setDeleting(null)
    }
  }

  const now = new Date()
  const isLive = (exam) =>
    exam.is_active &&
    (!exam.start_time || new Date(exam.start_time) <= now) &&
    (!exam.end_time   || new Date(exam.end_time)   >= now)

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Exams</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              {exams.length} exam{exams.length !== 1 ? 's' : ''} available
            </p>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : exams.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">◈</div>
            <h3 className="text-lg font-semibold text-white mb-2">No exams available</h3>
            <p className="text-slate-400">Check back later or use the AI Exam Generator to create one.</p>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Title', 'Duration', 'Marks', 'Questions', 'Status', 'Window', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {exams.map(exam => {
                  const live = isLive(exam)
                  return (
                    <tr key={exam.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-4">
                        <p className="font-medium text-white text-sm">{exam.title}</p>
                        {exam.description && (
                          <p className="text-slate-500 text-xs mt-0.5 truncate max-w-xs">{exam.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-4 text-slate-400 text-sm font-mono">{exam.duration_minutes}m</td>
                      <td className="px-4 py-4 text-slate-400 text-sm font-mono">{exam.total_marks}</td>
                      <td className="px-4 py-4 text-slate-400 text-sm">{exam.question_count ?? '—'}</td>
                      <td className="px-4 py-4">
                        <span className={live ? 'badge-green' : 'badge-gray'}>
                          {live ? 'Live' : exam.is_active ? 'Scheduled' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-slate-500 text-xs">
                        {exam.start_time
                          ? new Date(exam.start_time).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
                          : 'Always'}
                        {exam.end_time
                          ? ` – ${new Date(exam.end_time).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}`
                          : ''}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2 flex-wrap">
                          <button
                            disabled={!live}
                            onClick={() => navigate(`/exam/${exam.id}/instructions`)}
                            className="btn-primary text-sm py-1.5 px-3 disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            Start →
                          </button>
                          <button
                            onClick={() => navigate(`/exams/${exam.id}/edit`)}
                            className="text-brand-400 hover:text-brand-300 text-sm font-medium transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(exam)}
                            disabled={deleting === exam.id}
                            className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors disabled:opacity-50"
                          >
                            {deleting === exam.id ? 'Deleting…' : 'Delete'}
                          </button>
                        </div>
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
