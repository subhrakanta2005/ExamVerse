import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { examAPI, attemptAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

// ── Question renderer ─────────────────────────────────────────────────────────
function QuestionView({ question, answer, onAnswer }) {
  if (!question) return null
  const { question_type, text, options, marks } = question

  const toggleOption = (optId) => {
    if (question_type === 'mcq_single' || question_type === 'true_false') {
      onAnswer({ selected_option_ids: [optId] })
    } else if (question_type === 'mcq_multi') {
      const current = answer?.selected_option_ids || []
      const next = current.includes(optId)
        ? current.filter(id => id !== optId)
        : [...current, optId]
      onAnswer({ selected_option_ids: next })
    }
  }

  const isSelected = (optId) => (answer?.selected_option_ids || []).includes(optId)

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-3">
            <span className="badge-blue">{marks} mark{marks !== 1 ? 's' : ''}</span>
            <span className="badge-gray text-xs">{question_type.replace(/_/g, ' ').toUpperCase()}</span>
          </div>
          <p className="text-white text-lg leading-relaxed">{text}</p>
        </div>
      </div>

      {/* MCQ options */}
      {(question_type === 'mcq_single' || question_type === 'mcq_multi' || question_type === 'true_false') && (
        <div className="space-y-3">
          {(question_type === 'mcq_multi') && (
            <p className="text-xs text-amber-400">Select all that apply</p>
          )}
          {options?.map((opt) => (
            <button
              key={opt.id}
              onClick={() => toggleOption(opt.id)}
              className={clsx(
                'w-full text-left px-5 py-4 rounded-xl border text-sm transition-all duration-150',
                isSelected(opt.id)
                  ? 'bg-brand-600/20 border-brand-500 text-white'
                  : 'bg-slate-800/40 border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800/60'
              )}
            >
              <span className={clsx(
                'inline-flex w-5 h-5 rounded-full border mr-3 items-center justify-center text-xs flex-shrink-0',
                isSelected(opt.id) ? 'border-brand-400 bg-brand-500' : 'border-slate-600'
              )}>
                {isSelected(opt.id) && '✓'}
              </span>
              {opt.text}
            </button>
          ))}
        </div>
      )}

      {/* Fill in blank / Short answer */}
      {(question_type === 'fill_blank' || question_type === 'short_answer') && (
        <input
          type="text"
          className="input-field"
          placeholder={question_type === 'fill_blank' ? 'Type your answer…' : 'Short answer (max 200 chars)'}
          maxLength={question_type === 'short_answer' ? 200 : undefined}
          value={answer?.text_answer || ''}
          onChange={e => onAnswer({ text_answer: e.target.value })}
        />
      )}

      {/* Long answer */}
      {question_type === 'long_answer' && (
        <textarea
          className="input-field resize-none"
          rows={6}
          placeholder="Write your detailed answer here…"
          value={answer?.text_answer || ''}
          onChange={e => onAnswer({ text_answer: e.target.value })}
        />
      )}

      {/* Numeric */}
      {question_type === 'numeric' && (
        <input
          type="number"
          className="input-field max-w-xs"
          placeholder="Enter numeric answer…"
          value={answer?.numeric_answer ?? ''}
          onChange={e => onAnswer({ numeric_answer: parseFloat(e.target.value) })}
          step="any"
        />
      )}

      {/* File upload placeholder */}
      {question_type === 'file_upload' && (
        <div className="border-2 border-dashed border-slate-700 rounded-xl p-8 text-center">
          <p className="text-slate-500 text-sm">File upload requires backend storage integration.</p>
          <p className="text-slate-600 text-xs mt-1">Connect cloud storage (S3, GCS) to enable.</p>
        </div>
      )}
    </div>
  )
}

// ── Timer ────────────────────────────────────────────────────────────────────
function Timer({ durationMinutes, startedAt, onExpire }) {
  const [remaining, setRemaining] = useState(null)

  useEffect(() => {
    const endTime = new Date(startedAt).getTime() + durationMinutes * 60 * 1000
    const tick = () => {
      const diff = Math.max(0, endTime - Date.now())
      setRemaining(diff)
      if (diff === 0) onExpire()
    }
    tick()
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [startedAt, durationMinutes, onExpire])

  if (remaining === null) return null
  const mins = Math.floor(remaining / 60000)
  const secs = Math.floor((remaining % 60000) / 1000)
  const critical = remaining < 5 * 60 * 1000

  return (
    <div className={clsx(
      'flex items-center gap-2 px-4 py-2 rounded-xl font-mono font-bold text-lg',
      critical ? 'bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse' : 'bg-slate-800 text-white'
    )}>
      <span>⏱</span>
      {String(mins).padStart(2, '0')}:{String(secs).padStart(2, '0')}
    </div>
  )
}

// ── Main ExamRoom ────────────────────────────────────────────────────────────
export default function ExamRoom() {
  const { examId, attemptId } = useParams()
  const navigate = useNavigate()
  const [exam, setExam] = useState(null)
  const [attempt, setAttempt] = useState(null)
  const [allQuestions, setAllQuestions] = useState([])
  const [currentIdx, setCurrentIdx] = useState(0)
  const [answers, setAnswers] = useState({}) // questionId -> answer data
  const [markedReview, setMarkedReview] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false)
  const [tabWarning, setTabWarning] = useState(false)
  const saveTimer = useRef(null)

  useEffect(() => {
    Promise.all([
      examAPI.getForCandidate(examId),
      attemptAPI.getOne(attemptId),
      attemptAPI.getAnswers(attemptId)
    ]).then(([exRes, atRes, ansRes]) => {
      setExam(exRes.data)
      setAttempt(atRes.data)

      // Flatten questions respecting shuffled order
      const sections = exRes.data.sections || []
      const flat = sections.flatMap(s => s.questions || [])
      const order = atRes.data.question_order || flat.map(q => q.id)
      const sorted = order.map(id => flat.find(q => q.id === id)).filter(Boolean)
      setAllQuestions(sorted)

      // Pre-populate saved answers
      const saved = {}
      const reviewSet = new Set()
      ansRes.data.forEach(a => {
        saved[a.question_id] = a
        if (a.is_marked_review) reviewSet.add(a.question_id)
      })
      setAnswers(saved)
      setMarkedReview(reviewSet)
    }).catch(() => {
      toast.error('Failed to load exam')
      navigate('/dashboard')
    }).finally(() => setLoading(false))
  }, [examId, attemptId])

  // Tab visibility detection
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        attemptAPI.recordTabSwitch(attemptId)
        setTabWarning(true)
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [attemptId])

  const currentQuestion = allQuestions[currentIdx]

  const handleAnswer = useCallback((data) => {
    const qId = currentQuestion?.id
    if (!qId) return
    setAnswers(prev => ({ ...prev, [qId]: { ...prev[qId], ...data, question_id: qId } }))

    // Debounced auto-save
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      attemptAPI.saveAnswer(attemptId, {
        question_id: qId,
        ...data,
        is_marked_review: markedReview.has(qId)
      }).catch(() => {})
    }, 800)
  }, [currentQuestion, attemptId, markedReview])

  const toggleReview = () => {
    const qId = currentQuestion?.id
    if (!qId) return
    setMarkedReview(prev => {
      const next = new Set(prev)
      next.has(qId) ? next.delete(qId) : next.add(qId)
      return next
    })
  }

  const getQuestionStatus = (q) => {
    const a = answers[q.id]
    const hasAnswer = a && (
      (a.selected_option_ids?.length > 0) ||
      a.text_answer?.trim() ||
      a.numeric_answer !== undefined
    )
    if (markedReview.has(q.id)) return hasAnswer ? 'answered-review' : 'review'
    if (hasAnswer) return 'answered'
    return 'unanswered'
  }

  const doSubmit = async (auto = false) => {
    setSubmitting(true)
    try {
      // Save current answer first
      if (currentQuestion) {
        const a = answers[currentQuestion.id]
        if (a) {
          await attemptAPI.saveAnswer(attemptId, {
            question_id: currentQuestion.id,
            ...a,
            is_marked_review: markedReview.has(currentQuestion.id)
          })
        }
      }
      await attemptAPI.submit(attemptId, auto)
      toast.success(auto ? 'Time up! Exam auto-submitted.' : 'Exam submitted successfully!')
      navigate(`/result/${attemptId}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Submission failed')
      setSubmitting(false)
    }
  }

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-slate-400">Loading exam…</p>
      </div>
    </div>
  )

  const answeredCount = allQuestions.filter(q => {
    const a = answers[q.id]
    return a && ((a.selected_option_ids?.length > 0) || a.text_answer?.trim() || a.numeric_answer !== undefined)
  }).length

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Tab warning banner */}
      {tabWarning && (
        <div className="bg-red-500/90 text-white px-6 py-3 flex items-center justify-between text-sm font-medium">
          <span>⚠️ Tab switch detected! This violation has been recorded.</span>
          <button onClick={() => setTabWarning(false)} className="hover:text-red-200">✕</button>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-30 bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center gap-4">
        <div className="flex-1">
          <p className="font-display font-bold text-white">{exam?.title}</p>
          <p className="text-xs text-slate-500">{answeredCount}/{allQuestions.length} answered</p>
        </div>
        {attempt && exam && (
          <Timer
            durationMinutes={exam.duration_minutes}
            startedAt={attempt.started_at}
            onExpire={() => doSubmit(true)}
          />
        )}
        <button
          onClick={() => setShowSubmitConfirm(true)}
          className="btn-primary"
          disabled={submitting}
        >
          Submit Exam
        </button>
      </header>

      <div className="flex-1 flex">
        {/* Main question area */}
        <main className="flex-1 p-6 max-w-3xl">
          <div className="glass-card p-8 animate-fade-in">
            <div className="flex items-center justify-between mb-6">
              <span className="font-mono text-slate-500 text-sm">
                Question {currentIdx + 1} of {allQuestions.length}
              </span>
              <button
                onClick={toggleReview}
                className={clsx(
                  'text-sm px-4 py-1.5 rounded-lg border transition-all',
                  markedReview.has(currentQuestion?.id)
                    ? 'bg-amber-500/20 border-amber-500/50 text-amber-400'
                    : 'border-slate-700 text-slate-500 hover:text-slate-300'
                )}
              >
                {markedReview.has(currentQuestion?.id) ? '★ Marked' : '☆ Mark for review'}
              </button>
            </div>

            <QuestionView
              question={currentQuestion}
              answer={answers[currentQuestion?.id]}
              onAnswer={handleAnswer}
            />

            <div className="flex gap-3 mt-8">
              <button
                className="btn-secondary flex-1"
                disabled={currentIdx === 0}
                onClick={() => setCurrentIdx(i => i - 1)}
              >
                ← Previous
              </button>
              <button
                className="btn-primary flex-1"
                disabled={currentIdx === allQuestions.length - 1}
                onClick={() => setCurrentIdx(i => i + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        </main>

        {/* Question palette */}
        <aside className="hidden lg:flex w-72 border-l border-slate-800 p-5 flex-col gap-4">
          <p className="text-sm font-semibold text-slate-400">Question Palette</p>

          {/* Legend */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              { color: 'bg-emerald-500', label: 'Answered' },
              { color: 'bg-slate-700', label: 'Unanswered' },
              { color: 'bg-amber-500', label: 'Marked' },
              { color: 'bg-brand-500', label: 'Current' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5 text-slate-500">
                <div className={`w-3 h-3 rounded ${color}`} />
                {label}
              </div>
            ))}
          </div>

          {/* Palette grid */}
          <div className="flex flex-wrap gap-2">
            {allQuestions.map((q, i) => {
              const status = getQuestionStatus(q)
              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentIdx(i)}
                  className={clsx(
                    'w-9 h-9 rounded-lg text-xs font-mono font-bold transition-all border',
                    i === currentIdx && 'ring-2 ring-brand-400',
                    status === 'answered' && 'bg-emerald-600/30 border-emerald-500/50 text-emerald-400',
                    status === 'review' && 'bg-amber-600/30 border-amber-500/50 text-amber-400',
                    status === 'answered-review' && 'bg-brand-600/30 border-brand-500/50 text-brand-400',
                    status === 'unanswered' && 'bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600',
                  )}
                >
                  {i + 1}
                </button>
              )
            })}
          </div>

          {/* Summary */}
          <div className="mt-auto space-y-2 text-xs text-slate-500 border-t border-slate-800 pt-4">
            <div className="flex justify-between">
              <span>Answered</span>
              <span className="text-emerald-400 font-semibold">{answeredCount}</span>
            </div>
            <div className="flex justify-between">
              <span>Unanswered</span>
              <span className="text-slate-400 font-semibold">{allQuestions.length - answeredCount}</span>
            </div>
            <div className="flex justify-between">
              <span>Marked</span>
              <span className="text-amber-400 font-semibold">{markedReview.size}</span>
            </div>
          </div>
        </aside>
      </div>

      {/* Submit confirmation modal */}
      {showSubmitConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="glass-card p-8 max-w-md w-full border border-slate-700 animate-slide-up">
            <h3 className="font-display text-2xl font-bold text-white mb-2">Submit Exam?</h3>
            <p className="text-slate-400 mb-4">This action cannot be undone.</p>
            <div className="grid grid-cols-3 gap-3 mb-6 text-center text-sm">
              <div className="bg-slate-800/60 rounded-xl p-3">
                <p className="font-bold text-emerald-400">{answeredCount}</p>
                <p className="text-slate-500 text-xs">Answered</p>
              </div>
              <div className="bg-slate-800/60 rounded-xl p-3">
                <p className="font-bold text-slate-400">{allQuestions.length - answeredCount}</p>
                <p className="text-slate-500 text-xs">Unanswered</p>
              </div>
              <div className="bg-slate-800/60 rounded-xl p-3">
                <p className="font-bold text-amber-400">{markedReview.size}</p>
                <p className="text-slate-500 text-xs">Marked</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setShowSubmitConfirm(false)}>
                Continue Exam
              </button>
              <button
                className="btn-primary flex-1"
                onClick={() => { setShowSubmitConfirm(false); doSubmit(false) }}
                disabled={submitting}
              >
                {submitting ? 'Submitting…' : 'Submit Now'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
