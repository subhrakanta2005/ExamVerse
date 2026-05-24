import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { examAPI, questionAPI } from '../../services/api'
import toast from 'react-hot-toast'
import clsx from 'clsx'

const QUESTION_TYPES = [
  { value: 'mcq_single', label: 'MCQ — Single Correct' },
  { value: 'mcq_multiple', label: 'MCQ — Multiple Correct' },
  { value: 'true_false', label: 'True / False' },
  { value: 'fill_blank', label: 'Fill in the Blank' },
  { value: 'short_answer', label: 'Short Answer' },
  { value: 'long_answer', label: 'Long / Descriptive' },
  { value: 'numeric', label: 'Numeric Answer' },
  { value: 'match', label: 'Match the Following' },
  { value: 'assertion_reason', label: 'Assertion & Reason' },
  { value: 'file_upload', label: 'File Upload' },
]

function QuestionForm({ sectionId, onSaved, onCancel }) {
  const [form, setForm] = useState({
    question_type: 'mcq_single',
    text: '',
    marks: 1,
    negative_marks: 0,
    options: [{ text: '', is_correct: false }, { text: '', is_correct: false }, { text: '', is_correct: false }, { text: '', is_correct: false }],
    correct_answer: '',
    explanation: '',
    difficulty: 'medium',
  })
  const [saving, setSaving] = useState(false)
  const needsOptions = ['mcq_single', 'mcq_multiple', 'true_false', 'assertion_reason'].includes(form.question_type)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const setOption = (i, k, v) => setForm(f => {
    const opts = [...f.options]
    if (k === 'is_correct' && form.question_type === 'mcq_single') {
      opts.forEach((o, idx) => { opts[idx] = { ...o, is_correct: idx === i } })
    } else {
      opts[i] = { ...opts[i], [k]: v }
    }
    return { ...f, options: opts }
  })

  const addOption = () => setForm(f => ({ ...f, options: [...f.options, { text: '', is_correct: false }] }))
  const removeOption = (i) => setForm(f => ({ ...f, options: f.options.filter((_, idx) => idx !== i) }))

  const handleSave = async () => {
    if (!form.text.trim()) return toast.error('Question text is required')
    setSaving(true)
    try {
      const payload = {
        section_id: sectionId,
        question_type: form.question_type,
        text: form.text,
        marks: Number(form.marks),
        negative_marks: Number(form.negative_marks),
        difficulty: form.difficulty,
        explanation: form.explanation,
        options: needsOptions ? form.options.filter(o => o.text.trim()) : [],
        correct_answer: form.correct_answer,
      }
      const res = await questionAPI.create(payload)
      toast.success('Question saved')
      onSaved(res.data)
    } catch (e) {
      const detail = e.response?.data?.detail
toast.error(Array.isArray(detail) ? detail.map(d => d.msg).join('; ') : (detail || 'Failed to save question'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="glass-card p-6 border border-brand-500/20 space-y-4">
      <h4 className="font-semibold text-white text-sm">New Question</h4>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">Type</label>
          <select className="input-field" value={form.question_type} onChange={e => set('question_type', e.target.value)}>
            {QUESTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="label">Marks</label>
            <input type="number" className="input-field" value={form.marks} min={0} step={0.5} onChange={e => set('marks', e.target.value)} />
          </div>
          <div>
            <label className="label">Negative</label>
            <input type="number" className="input-field" value={form.negative_marks} min={0} step={0.25} onChange={e => set('negative_marks', e.target.value)} />
          </div>
        </div>
      </div>

      <div>
        <label className="label">Question Text</label>
        <textarea
          className="input-field resize-none"
          rows={3}
          value={form.text}
          onChange={e => set('text', e.target.value)}
          placeholder="Enter the question..."
        />
      </div>

      {needsOptions && (
        <div>
          <label className="label">Options {form.question_type === 'mcq_single' ? '(select correct)' : '(select all correct)'}</label>
          <div className="space-y-2">
            {form.options.map((opt, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type={form.question_type === 'mcq_multiple' ? 'checkbox' : 'radio'}
                  name="correct_opt"
                  checked={opt.is_correct}
                  onChange={e => setOption(i, 'is_correct', form.question_type === 'mcq_multiple' ? e.target.checked : true)}
                  className="accent-brand-500 w-4 h-4 flex-shrink-0"
                />
                <input
                  type="text"
                  className="input-field text-sm py-2"
                  value={opt.text}
                  onChange={e => setOption(i, 'text', e.target.value)}
                  placeholder={`Option ${i + 1}`}
                />
                {form.options.length > 2 && (
                  <button onClick={() => removeOption(i)} className="text-red-500 hover:text-red-400 text-lg px-1">×</button>
                )}
              </div>
            ))}
            <button onClick={addOption} className="btn-ghost text-xs text-slate-400">+ Add option</button>
          </div>
        </div>
      )}

      {!needsOptions && (
        <div>
          <label className="label">Correct Answer (for auto-grading)</label>
          <input
            type="text"
            className="input-field"
            value={form.correct_answer}
            onChange={e => set('correct_answer', e.target.value)}
            placeholder="Leave blank for manual grading"
          />
        </div>
      )}

      <div>
        <label className="label">Explanation (shown after result)</label>
        <textarea className="input-field resize-none" rows={2} value={form.explanation} onChange={e => set('explanation', e.target.value)} placeholder="Optional..." />
      </div>

      <div className="flex gap-3">
        <button className="btn-primary text-sm" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save Question'}
        </button>
        <button className="btn-secondary text-sm" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}

export default function AdminExamEditor() {
  const { examId } = useParams()
  const navigate = useNavigate()
  const isEdit = Boolean(examId)

  const [form, setForm] = useState({
  title: '', description: '', instructions: '',
  duration_minutes: 60, total_marks: 100, pass_percentage: 40,
  negative_marking: false, shuffle_questions: false, shuffle_options: false,
  max_attempts: 1, show_result_immediately: true, is_active: false, is_public: false,
  start_time: '', end_time: '',
  })
  const [sections, setSections] = useState([])
  const [questions, setQuestions] = useState({}) // sectionId -> []
  const [addingQuestion, setAddingQuestion] = useState(null) // sectionId
  const [newSectionTitle, setNewSectionTitle] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(isEdit)
  const [saved, setSaved] = useState(null) // exam id after initial save

  const examIdToUse = examId || saved

  useEffect(() => {
    if (!isEdit) return
    examAPI.getOne(examId)
      .then(r => {
        const e = r.data
        setForm({
  title: e.title || '', description: e.description || '',
  instructions: e.instructions || '',
  duration_minutes: e.duration_minutes || 60,
  total_marks: e.total_marks || 100,
  pass_percentage: e.pass_percentage || 40,
  negative_marking: e.negative_marking || false,
  shuffle_questions: e.shuffle_questions || false,
  shuffle_options: e.shuffle_options || false,
  max_attempts: e.max_attempts || 1,
  show_result_immediately: e.show_result_immediately !== false,
  is_active: e.is_active || false,
  is_public: e.is_public || false,
  start_time: e.start_time ? e.start_time.substring(0, 16) : '',
  end_time: e.end_time ? e.end_time.substring(0, 16) : '',
})
        setSections(e.sections || [])
        // load questions for each section
        const qMap = {}
        ;(e.sections || []).forEach(s => { qMap[s.id] = s.questions || [] })
        setQuestions(qMap)
      })
      .finally(() => setLoading(false))
  }, [examId, isEdit])

  const setField = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    if (!form.title.trim()) return toast.error('Title is required')
    setSaving(true)
    try {
      const payload = { ...form }
      if (!payload.start_time) payload.start_time = null
      if (!payload.end_time) payload.end_time = null
      let res
      if (examIdToUse) {
        res = await examAPI.update(examIdToUse, payload)
        toast.success('Exam updated')
      } else {
        res = await examAPI.create(payload)
        setSaved(res.data.id)
        toast.success('Exam created! Now add sections and questions.')
      }
    } catch (e) {
      const detail = e.response?.data?.detail
      toast.error(Array.isArray(detail) ? detail.map(d => d.msg).join('; ') : (detail || 'Failed to save exam'))
    } finally {
      setSaving(false)
    }
  }

  const handleAddSection = async () => {
    if (!newSectionTitle.trim()) return
    if (!examIdToUse) return toast.error('Save exam details first')
    try {
      const res = await examAPI.addSection(examIdToUse, {
        title: newSectionTitle,
        order_index: sections.length,
      })
      setSections(s => [...s, res.data])
      setQuestions(q => ({ ...q, [res.data.id]: [] }))
      setNewSectionTitle('')
      toast.success('Section added')
    } catch {
      toast.error('Failed to add section')
    }
  }

  const handleDeleteSection = async (sectionId) => {
    if (!window.confirm('Delete this section and all its questions?')) return
    try {
      await examAPI.deleteSection(examIdToUse, sectionId)
      setSections(s => s.filter(sec => sec.id !== sectionId))
      setQuestions(q => { const nq = { ...q }; delete nq[sectionId]; return nq })
      toast.success('Section deleted')
    } catch {
      toast.error('Failed to delete section')
    }
  }

  const handleQuestionSaved = (sectionId, question) => {
    setQuestions(q => ({ ...q, [sectionId]: [...(q[sectionId] || []), question] }))
    setAddingQuestion(null)
  }

  const handleDeleteQuestion = async (sectionId, questionId) => {
    try {
      await questionAPI.delete(questionId)
      setQuestions(q => ({ ...q, [sectionId]: q[sectionId].filter(qq => qq.id !== questionId) }))
      toast.success('Question deleted')
    } catch {
      toast.error('Failed to delete question')
    }
  }

  if (loading) return (
    <AppLayout>
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    </AppLayout>
  )

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">{isEdit ? 'Edit Exam' : 'Create Exam'}</h1>
            <p className="text-slate-400 text-sm mt-0.5">Fill in details, then add sections and questions.</p>
          </div>
          <button onClick={() => navigate('/admin/exams')} className="btn-ghost text-sm">← Back</button>
        </div>

        {/* Exam Details */}
        <div className="glass-card p-6 space-y-5">
          <h2 className="font-semibold text-white">Exam Details</h2>

          <div>
            <label className="label">Title *</label>
            <input type="text" className="input-field" value={form.title} onChange={e => setField('title', e.target.value)} placeholder="e.g. Final Semester Exam — Mathematics" />
          </div>

          <div>
            <label className="label">Description</label>
            <textarea className="input-field resize-none" rows={2} value={form.description} onChange={e => setField('description', e.target.value)} placeholder="Brief overview visible to candidates" />
          </div>

          <div>
            <label className="label">Instructions</label>
            <textarea className="input-field resize-none" rows={4} value={form.instructions} onChange={e => setField('instructions', e.target.value)} placeholder="Full instructions shown before the exam starts..." />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <label className="label">Duration (min)</label>
              <input type="number" className="input-field" value={form.duration_minutes} min={5} onChange={e => setField('duration_minutes', Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Total Marks</label>
              <input type="number" className="input-field" value={form.total_marks} min={1} onChange={e => setField('total_marks', Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Pass % </label>
              <input type="number" className="input-field" value={form.pass_percentage} min={0} max={100} onChange={e => setField('pass_percentage', Number(e.target.value))} />
            </div>
            <div>
              <label className="label">Max Attempts</label>
              <input type="number" className="input-field" value={form.max_attempts} min={1} onChange={e => setField('max_attempts', Number(e.target.value))} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Available From</label>
              <input type="datetime-local" className="input-field" value={form.start_time} onChange={e => setField('start_time', e.target.value)} />
            </div>
            <div>
              <label className="label">Available Until</label>
              <input type="datetime-local" className="input-field" value={form.end_time} onChange={e => setField('end_time', e.target.value)} />
            </div>
          </div>

          {/* Toggles */}
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            {[
              { label: 'Negative marking', key: 'negative_marking' },
              { label: 'Shuffle questions', key: 'shuffle_questions' },
              { label: 'Shuffle options', key: 'shuffle_options' },
              { label: 'Show result to candidate', key: 'show_result_immediately' },
              { label: 'Published (visible to candidates)', key: 'is_active' },
              { label: 'Public (open to all candidates)', key: 'is_public' },
            ].map(({ label, key }) => (
              <label key={key} className="flex items-center gap-2 cursor-pointer">
                <div
                  onClick={() => setField(key, !form[key])}
                  className={clsx(
                    'w-10 h-5 rounded-full transition-colors duration-200 relative',
                    form[key] ? 'bg-brand-600' : 'bg-slate-700'
                  )}
                >
                  <span className={clsx(
                    'absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200',
                    form[key] ? 'translate-x-5' : 'translate-x-0'
                  )} />
                </div>
                <span className="text-sm text-slate-300">{label}</span>
              </label>
            ))}
          </div>

          <div className="flex gap-3 pt-2">
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving…' : examIdToUse ? 'Update Exam' : 'Save & Continue'}
            </button>
          </div>
        </div>

        {/* Sections & Questions */}
        {examIdToUse && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-white">Sections & Questions</h2>
            </div>

            {sections.map(section => (
              <div key={section.id} className="glass-card p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-white">{section.title}</h3>
                  <button onClick={() => handleDeleteSection(section.id)} className="text-red-500 hover:text-red-400 text-sm transition-colors">Delete section</button>
                </div>

                {/* Questions list */}
                {(questions[section.id] || []).map((q, i) => (
                  <div key={q.id} className="flex items-start justify-between bg-slate-800/40 rounded-xl p-4 gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="badge-gray text-xs">{i + 1}</span>
                        <span className="badge-blue text-xs">{q.question_type}</span>
                        <span className="text-slate-500 text-xs">{q.marks} mark{q.marks !== 1 ? 's' : ''}</span>
                      </div>
                      <p className="text-slate-300 text-sm line-clamp-2">{q.text}</p>
                    </div>
                    <button
                      onClick={() => handleDeleteQuestion(section.id, q.id)}
                      className="text-red-500 hover:text-red-400 text-sm flex-shrink-0 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                ))}

                {addingQuestion === section.id ? (
                  <QuestionForm
                    sectionId={section.id}
                    onSaved={(q) => handleQuestionSaved(section.id, q)}
                    onCancel={() => setAddingQuestion(null)}
                  />
                ) : (
                  <button
                    className="btn-ghost text-sm text-slate-400 border border-dashed border-slate-700 w-full justify-center py-3 rounded-xl hover:border-brand-500/50 hover:text-brand-400"
                    onClick={() => setAddingQuestion(section.id)}
                  >
                    + Add Question
                  </button>
                )}
              </div>
            ))}

            {/* Add Section */}
            <div className="glass-card p-5">
              <h3 className="text-sm font-semibold text-slate-400 mb-3">Add Section</h3>
              <div className="flex gap-3">
                <input
                  type="text"
                  className="input-field"
                  value={newSectionTitle}
                  onChange={e => setNewSectionTitle(e.target.value)}
                  placeholder="Section title, e.g. Quantitative Aptitude"
                  onKeyDown={e => e.key === 'Enter' && handleAddSection()}
                />
                <button className="btn-primary text-sm whitespace-nowrap" onClick={handleAddSection}>Add Section</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}
