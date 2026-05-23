import React, { useEffect, useState } from 'react'
import AppLayout from '../../components/layout/AppLayout'
import { adminAPI, resultAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function AdminEvaluate() {
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [marks, setMarks] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    setLoading(true)
    adminAPI.manualQueue()
      .then(r => setQueue(r.data || []))
      .catch(() => toast.error('Failed to load evaluation queue'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const openItem = (item) => {
    setSelected(item)
    setMarks(item.awarded_marks != null ? String(item.awarded_marks) : '')
    setComment(item.evaluator_comment || '')
  }

  const handleSubmit = async () => {
    if (marks === '' || isNaN(Number(marks))) return toast.error('Enter a valid marks value')
    if (Number(marks) < 0) return toast.error('Marks cannot be negative')
    if (Number(marks) > selected.max_marks) return toast.error(`Marks cannot exceed ${selected.max_marks}`)
    setSubmitting(true)
    try {
      await resultAPI.evaluate({
        answer_id: selected.answer_id,
        awarded_marks: Number(marks),
        evaluator_comment: comment,
      })
      toast.success('Evaluation saved')
      setQueue(q => q.filter(item => item.answer_id !== selected.answer_id))
      setSelected(null)
    } catch {
      toast.error('Failed to save evaluation')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AppLayout>
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Manual Evaluation</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {queue.length} answer{queue.length !== 1 ? 's' : ''} pending review
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : queue.length === 0 ? (
          <div className="glass-card p-16 text-center">
            <div className="text-5xl mb-4">✓</div>
            <h3 className="text-lg font-semibold text-white mb-2">All caught up!</h3>
            <p className="text-slate-400">No answers are pending manual evaluation.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Queue list */}
            <div className="space-y-3">
              <h2 className="font-semibold text-slate-300 text-sm uppercase tracking-wider">Pending Queue</h2>
              {queue.map(item => (
                <button
                  key={item.answer_id}
                  onClick={() => openItem(item)}
                  className={clsx(
                    'w-full text-left glass-card p-4 transition-all duration-200 border',
                    selected?.answer_id === item.answer_id
                      ? 'border-brand-500/60 bg-brand-500/5'
                      : 'border-slate-700/50 hover:border-slate-600'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge-yellow text-xs">{item.question_type?.replace('_', ' ')}</span>
                        <span className="text-slate-500 text-xs">{item.max_marks} marks</span>
                      </div>
                      <p className="text-slate-300 text-sm font-medium line-clamp-2">{item.question_text}</p>
                      <p className="text-slate-500 text-xs mt-1">
                        {item.candidate_name} · {item.exam_title}
                      </p>
                    </div>
                    <span className="text-brand-400 text-sm flex-shrink-0">Review →</span>
                  </div>
                </button>
              ))}
            </div>

            {/* Evaluation panel */}
            {selected ? (
              <div className="glass-card p-6 space-y-5 border border-brand-500/20 self-start sticky top-24">
                <div>
                  <h2 className="font-semibold text-white mb-1">Evaluate Answer</h2>
                  <p className="text-slate-500 text-xs">
                    {selected.candidate_name} · {selected.exam_title} · {selected.section_title}
                  </p>
                </div>

                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Question</p>
                  <p className="text-slate-200 text-sm">{selected.question_text}</p>
                </div>

                <div className="bg-slate-800/50 rounded-xl p-4">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Candidate's Answer</p>
                  <p className="text-slate-200 text-sm whitespace-pre-wrap">
                    {selected.answer_text || <span className="text-slate-500 italic">No answer provided</span>}
                  </p>
                </div>

                {selected.model_answer && (
                  <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl p-4">
                    <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-2">Model Answer</p>
                    <p className="text-slate-300 text-sm whitespace-pre-wrap">{selected.model_answer}</p>
                  </div>
                )}

                <div>
                  <label className="label">
                    Marks Awarded (max: {selected.max_marks})
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    value={marks}
                    min={0}
                    max={selected.max_marks}
                    step={0.5}
                    onChange={e => setMarks(e.target.value)}
                    placeholder={`0 – ${selected.max_marks}`}
                  />
                </div>

                <div>
                  <label className="label">Evaluator Comment (optional)</label>
                  <textarea
                    className="input-field resize-none"
                    rows={3}
                    value={comment}
                    onChange={e => setComment(e.target.value)}
                    placeholder="Feedback for the candidate…"
                  />
                </div>

                <div className="flex gap-3">
                  <button
                    className="btn-primary flex-1"
                    onClick={handleSubmit}
                    disabled={submitting}
                  >
                    {submitting ? 'Saving…' : 'Save Evaluation'}
                  </button>
                  <button className="btn-secondary" onClick={() => setSelected(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <div className="glass-card p-10 text-center self-start">
                <p className="text-slate-500">Select an answer from the queue to evaluate it.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  )
}
