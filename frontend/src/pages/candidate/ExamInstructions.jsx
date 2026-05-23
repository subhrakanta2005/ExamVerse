import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { examAPI, attemptAPI } from '../../services/api'
import toast from 'react-hot-toast'

export default function ExamInstructions() {
  const { examId } = useParams()
  const navigate = useNavigate()
  const [exam, setExam] = useState(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [agreed, setAgreed] = useState(false)

  useEffect(() => {
    examAPI.getForCandidate(examId)
      .then(res => setExam(res.data))
      .catch(() => { toast.error('Exam not found'); navigate('/dashboard') })
      .finally(() => setLoading(false))
  }, [examId])

  const handleStart = async () => {
    if (!agreed) return toast.error('Please accept the instructions first')
    setStarting(true)
    try {
      const res = await attemptAPI.start(parseInt(examId))
      navigate(`/exam/${examId}/attempt/${res.data.id}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Cannot start exam')
    } finally {
      setStarting(false)
    }
  }

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    </AppLayout>
  )

  const totalQuestions = exam.sections?.reduce((a, s) => a + (s.questions?.length || 0), 0) || 0

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto animate-slide-up">
        {/* Header */}
        <div className="glass-card p-8 mb-6">
          <span className="badge-blue mb-3 inline-flex">Exam Instructions</span>
          <h1 className="font-display text-3xl font-bold text-white mb-2">{exam.title}</h1>
          <p className="text-slate-400">{exam.description}</p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
            {[
              { label: 'Duration', value: `${exam.duration_minutes} min` },
              { label: 'Total Marks', value: exam.total_marks },
              { label: 'Questions', value: totalQuestions },
              { label: 'Pass Mark', value: `${exam.pass_percentage}%` },
            ].map(({ label, value }) => (
              <div key={label} className="bg-slate-800/50 rounded-xl p-4 text-center">
                <p className="font-display text-2xl font-bold text-brand-400">{value}</p>
                <p className="text-xs text-slate-500 mt-1">{label}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Sections overview */}
        {exam.sections?.length > 0 && (
          <div className="glass-card p-6 mb-6">
            <h2 className="font-semibold text-white mb-4">Sections</h2>
            <div className="space-y-3">
              {exam.sections.map((s, i) => (
                <div key={s.id} className="flex items-center justify-between py-2 border-b border-slate-800 last:border-0">
                  <span className="text-slate-300 flex items-center gap-2">
                    <span className="w-6 h-6 bg-brand-600/20 rounded text-brand-400 text-xs flex items-center justify-center font-mono">{i + 1}</span>
                    {s.title}
                  </span>
                  <span className="text-slate-500 text-sm">{s.questions?.length || 0} questions</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Instructions text */}
        {exam.instructions && (
          <div className="glass-card p-6 mb-6">
            <h2 className="font-semibold text-white mb-4">General Instructions</h2>
            <div className="text-slate-300 text-sm leading-relaxed whitespace-pre-line">
              {exam.instructions}
            </div>
          </div>
        )}

        {/* Exam rules */}
        <div className="glass-card p-6 mb-6">
          <h2 className="font-semibold text-white mb-4">Important Rules</h2>
          <ul className="space-y-2 text-sm text-slate-300">
            {[
              `The exam timer starts as soon as you click "Start Exam"`,
              'Do NOT switch browser tabs or windows — every violation is recorded',
              exam.negative_marking ? `Negative marking applies: -${exam.negative_marks_per_question} marks per wrong answer` : 'No negative marking',
              'Auto-save is enabled — your answers are saved automatically',
              `Maximum ${exam.max_attempts} attempt(s) allowed`,
              exam.shuffle_questions ? 'Questions are randomized for each attempt' : null,
              'Ensure stable internet before starting',
            ].filter(Boolean).map((rule, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-brand-400 flex-shrink-0">▸</span>
                {rule}
              </li>
            ))}
          </ul>
        </div>

        {/* Agreement + Start */}
        <div className="glass-card p-6">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={agreed}
              onChange={e => setAgreed(e.target.checked)}
              className="mt-1 w-4 h-4 accent-brand-500 cursor-pointer"
            />
            <span className="text-slate-300 text-sm">
              I have read and understood all instructions. I agree to the examination rules and understand that violations will be recorded.
            </span>
          </label>

          <div className="flex gap-3 mt-5">
            <button onClick={() => navigate('/dashboard')} className="btn-secondary flex-1">
              ← Back
            </button>
            <button
              onClick={handleStart}
              disabled={!agreed || starting}
              className="btn-primary flex-1 py-3"
            >
              {starting ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Starting…
                </span>
              ) : 'Start Exam →'}
            </button>
          </div>
        </div>
      </div>
    </AppLayout>
  )
}
