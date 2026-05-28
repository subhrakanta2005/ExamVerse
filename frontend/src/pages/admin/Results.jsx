import React, { useEffect, useState } from 'react'
import AppLayout from '../../components/layout/AppLayout'
import { resultAPI, examAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function AdminResults() {
  const [results, setResults] = useState([])
  const [exams, setExams] = useState([])
  const [selectedExam, setSelectedExam] = useState('')
  const [loading, setLoading] = useState(true)
  const [publishing, setPublishing] = useState(null)

  useEffect(() => {
    examAPI.getAdminAll(0, 100).then(r => setExams(r.data || []))
  }, [])

  const load = (examId = '') => {
    setLoading(true)
    resultAPI.adminGetAll(examId || undefined)
      .then(r => setResults(r.data || []))
      .catch(() => toast.error('Failed to load results'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(selectedExam) }, [selectedExam])

  const handlePublish = async (resultId) => {
    setPublishing(resultId)
    try {
      await resultAPI.publish(resultId)
      setResults(rs => rs.map(r =>
        r.id === resultId ? { ...r, is_published: true, status: 'published' } : r
      ))
      toast.success('Result published — candidate can now view it')
    } catch {
      toast.error('Failed to publish result')
    } finally {
      setPublishing(null)
    }
  }

  const formatDate = (iso) =>
    iso
      ? new Date(iso).toLocaleDateString('en-IN', {
          month: 'short', day: 'numeric', year: 'numeric',
        })
      : '—'

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white">Results</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              {results.length} result{results.length !== 1 ? 's' : ''}
            </p>
          </div>
          <select
            className="input-field w-auto min-w-48"
            value={selectedExam}
            onChange={e => setSelectedExam(e.target.value)}
          >
            <option value="">All Exams</option>
            {exams.map(e => (
              <option key={e.id} value={e.id}>{e.title}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : results.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">◎</div>
            <h3 className="text-lg font-semibold text-white mb-2">No results found</h3>
            <p className="text-slate-400">
              Results will appear here after candidates submit exams.
            </p>
          </div>
        ) : (
          <div className="glass-card overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-800">
                  {['Candidate', 'Exam', 'Score', 'Pass/Fail', 'Date', 'Published', 'Action'].map(h => (
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
                {results.map(result => {
                  const scorePercent =
                    result.total_marks > 0
                      ? Math.round((result.obtained_marks / result.total_marks) * 100)
                      : 0
                  // is_published comes from the enriched admin list endpoint
                  const isPublished = result.is_published || result.status === 'published'

                  return (
                    <tr key={result.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-4">
                        <p className="font-medium text-white text-sm">
                          {result.candidate_name || '—'}
                        </p>
                        <p className="text-slate-500 text-xs">
                          {result.candidate_email || ''}
                        </p>
                      </td>
                      <td className="px-4 py-4 text-slate-300 text-sm">
                        {result.exam_title || `Exam #${result.exam_id}`}
                      </td>
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 bg-slate-800 rounded-full overflow-hidden">
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
                        <p className="text-slate-500 text-xs mt-0.5">
                          {result.obtained_marks}/{result.total_marks}
                        </p>
                      </td>
                      <td className="px-4 py-4">
                        {/* Use is_passed (boolean) for pass/fail badge */}
                        <span className={result.is_passed ? 'badge-green' : 'badge-red'}>
                          {result.is_passed ? 'Passed' : 'Failed'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-slate-500 text-xs">
                        {formatDate(result.created_at)}
                      </td>
                      <td className="px-4 py-4">
                        <span className={isPublished ? 'badge-green' : 'badge-gray'}>
                          {isPublished ? 'Yes' : 'No'}
                        </span>
                      </td>
                      <td className="px-4 py-4">
                        {!isPublished ? (
                          <button
                            onClick={() => handlePublish(result.id)}
                            disabled={publishing === result.id}
                            className="text-brand-400 hover:text-brand-300 text-sm font-medium transition-colors disabled:opacity-50"
                          >
                            {publishing === result.id ? 'Publishing…' : 'Publish'}
                          </button>
                        ) : (
                          <span className="text-slate-600 text-sm">Published</span>
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
