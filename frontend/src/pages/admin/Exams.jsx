import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { examAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function AdminExams() {
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    examAPI.getAdminAll(0, 100)
      .then(r => setExams(r.data || []))
      .catch(() => toast.error('Failed to load exams'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id, title) => {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return
    setDeleting(id)
    try {
      await examAPI.delete(id)
      toast.success('Exam deleted')
      setExams(e => e.filter(x => x.id !== id))
    } catch {
      toast.error('Failed to delete exam')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Exams</h1>
            <p className="text-slate-400 text-sm mt-0.5">{exams.length} exam{exams.length !== 1 ? 's' : ''} total</p>
          </div>
          <Link to="/admin/exams/new" className="btn-primary">+ New Exam</Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : exams.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">◈</div>
            <h3 className="text-lg font-semibold text-white mb-2">No exams yet</h3>
            <p className="text-slate-400 mb-6">Create your first exam to get started.</p>
            <Link to="/admin/exams/new" className="btn-primary">Create Exam</Link>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Title', 'Duration', 'Marks', 'Sections', 'Status', 'Window', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {exams.map(exam => (
                  <tr key={exam.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-4">
                      <p className="font-medium text-white text-sm">{exam.title}</p>
                      {exam.description && (
                        <p className="text-slate-500 text-xs mt-0.5 truncate max-w-xs">{exam.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-4 text-slate-400 text-sm font-mono">{exam.duration_minutes}m</td>
                    <td className="px-4 py-4 text-slate-400 text-sm font-mono">{exam.total_marks}</td>
                    <td className="px-4 py-4 text-slate-400 text-sm">{exam.section_count ?? '—'}</td>
                    <td className="px-4 py-4">
                      <span className={exam.is_published ? 'badge-green' : 'badge-gray'}>
                        {exam.is_published ? 'Published' : 'Draft'}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-500 text-xs">
                      {exam.available_from
                        ? new Date(exam.available_from).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })
                        : 'Always'}
                      {exam.available_until
                        ? ` – ${new Date(exam.available_until).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' })}`
                        : ''}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-3">
                        <Link
                          to={`/admin/exams/${exam.id}/edit`}
                          className="text-brand-400 hover:text-brand-300 text-sm font-medium transition-colors"
                        >
                          Edit
                        </Link>
                        <button
                          onClick={() => handleDelete(exam.id, exam.title)}
                          disabled={deleting === exam.id}
                          className="text-red-500 hover:text-red-400 text-sm font-medium transition-colors disabled:opacity-50"
                        >
                          {deleting === exam.id ? '...' : 'Delete'}
                        </button>
                      </div>
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
