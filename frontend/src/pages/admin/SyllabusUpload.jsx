import React, { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../../components/layout/AppLayout'
import { syllabusAPI, examAPI, questionAPI } from '../../services/api'
import toast from 'react-hot-toast'

const DIFFICULTIES  = ['easy', 'medium', 'hard', 'mixed']
const QTYPES        = ['mcq', 'true_false', 'short', 'mixed']
const QTYPE_LABELS  = { mcq: 'MCQ', true_false: 'True / False', short: 'Short Answer', mixed: 'Mixed' }

// ─── Shared settings row ──────────────────────────────────────────────────────

function Settings({ s, set }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div>
        <label className="label">Questions (1–300)</label>
        <input
          type="number" min={1} max={300}
          className="input-field"
          value={s.num_questions}
          onChange={e => set('num_questions', Math.min(300, Math.max(1, Number(e.target.value))))}
        />
      </div>
      <div>
        <label className="label">Difficulty</label>
        <select className="input-field" value={s.difficulty} onChange={e => set('difficulty', e.target.value)}>
          {DIFFICULTIES.map(d => <option key={d} value={d}>{d.charAt(0).toUpperCase() + d.slice(1)}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Question Types</label>
        <select className="input-field" value={s.question_types} onChange={e => set('question_types', e.target.value)}>
          {QTYPES.map(t => <option key={t} value={t}>{QTYPE_LABELS[t]}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Time Limit (min)</label>
        <input
          type="number" min={5} max={300}
          className="input-field"
          value={s.time_limit}
          onChange={e => set('time_limit', Math.max(5, Number(e.target.value)))}
        />
      </div>
      <div className="col-span-2">
        <label className="label">Exam Title (optional)</label>
        <input
          type="text" className="input-field"
          value={s.exam_title}
          onChange={e => set('exam_title', e.target.value)}
          placeholder="Auto-detected from content if blank"
        />
      </div>
      <div className="col-span-2">
        <label className="label">Focus Topics (optional)</label>
        <input
          type="text" className="input-field"
          value={s.focus_topics}
          onChange={e => set('focus_topics', e.target.value)}
          placeholder="Comma-separated, e.g. Geography, History"
        />
      </div>
    </div>
  )
}

// ─── Tab 1: Upload file ───────────────────────────────────────────────────────

function UploadTab({ settings, setField, onResult }) {
  const [file, setFile]         = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading]   = useState(false)
  const inputRef                = useRef()

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }, [])

  const handleSubmit = async () => {
    if (!file) return toast.error('Please select a file first')
    setLoading(true)
    try {
      const res = await syllabusAPI.uploadAndGenerate(file, settings)
      toast.success('Exam generated!')
      onResult(res.data)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-all
          ${dragging ? 'border-brand-400 bg-brand-500/10'
            : file    ? 'border-green-500 bg-green-500/10'
                      : 'border-slate-700 hover:border-brand-500/50 hover:bg-slate-800/60'}`}
      >
        <input
          ref={inputRef} type="file"
          accept=".txt,.pdf,.docx,.doc"
          className="hidden"
          onChange={e => setFile(e.target.files[0])}
        />
        {file ? (
          <div className="space-y-1">
            <p className="text-2xl">📄</p>
            <p className="font-semibold text-green-400">{file.name}</p>
            <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB — click to change</p>
          </div>
        ) : (
          <div className="space-y-1">
            <p className="text-2xl">⬆️</p>
            <p className="text-slate-300 font-medium">Drop syllabus here or click to browse</p>
            <p className="text-xs text-slate-500">TXT · PDF · DOCX — max 10 MB</p>
          </div>
        )}
      </div>

      <Settings s={settings} set={setField} />

      <div className="flex justify-end">
        <button className="btn-primary" onClick={handleSubmit} disabled={!file || loading}>
          {loading ? 'Generating…' : 'Generate Exam →'}
        </button>
      </div>
    </div>
  )
}

// ─── Tab 2: Search by topics ──────────────────────────────────────────────────

function SearchTab({ settings, setField, onResult }) {
  const [topics, setTopics]   = useState([''])
  const [extra, setExtra]     = useState('')
  const [loading, setLoading] = useState(false)

  const setTopic    = (i, v) => setTopics(ts => ts.map((t, idx) => idx === i ? v : t))
  const addTopic    = ()     => setTopics(ts => [...ts, ''])
  const removeTopic = (i)    => setTopics(ts => ts.filter((_, idx) => idx !== i))

  const handleSubmit = async () => {
    const cleaned = topics.map(t => t.trim()).filter(Boolean)
    if (!cleaned.length) return toast.error('Add at least one topic')
    setLoading(true)
    try {
      const res = await syllabusAPI.searchAndGenerate({
        ...settings,
        topics: cleaned,
        extra_context: extra,
      })
      toast.success(res.data.search_enabled ? 'Exam generated from web search!' : 'Exam generated (fallback mode)')
      onResult(res.data)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Generation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="label">Topics to search</label>
        <div className="space-y-2">
          {topics.map((t, i) => (
            <div key={i} className="flex gap-2">
              <input
                type="text" className="input-field"
                value={t}
                onChange={e => setTopic(i, e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addTopic()}
                placeholder={`Topic ${i + 1}, e.g. Odisha Geography`}
              />
              {topics.length > 1 && (
                <button
                  onClick={() => removeTopic(i)}
                  className="text-red-500 hover:text-red-400 px-2 text-lg transition-colors"
                >×</button>
              )}
            </div>
          ))}
          <button onClick={addTopic} className="btn-ghost text-xs text-slate-400">+ Add topic</button>
        </div>
      </div>

      <div>
        <label className="label">Extra context (optional)</label>
        <input
          type="text" className="input-field"
          value={extra}
          onChange={e => setExtra(e.target.value)}
          placeholder='Narrows the search, e.g. "OSSSC exam Odisha" or "Class 10 CBSE"'
        />
      </div>

      <Settings s={settings} set={setField} />

      <div className="flex justify-end">
        <button className="btn-primary" onClick={handleSubmit} disabled={topics.every(t => !t.trim()) || loading}>
          {loading ? 'Searching & Generating…' : 'Search & Generate →'}
        </button>
      </div>
    </div>
  )
}

// ─── Result preview + import to exam ─────────────────────────────────────────

function ResultPreview({ result, onImported }) {
  const navigate              = useNavigate()
  const [importing, setImporting] = useState(false)

  const exam    = result.exam
  const report  = result.coverage_report || {}
  const totalQs = exam?.sections?.reduce((n, s) => n + (s.questions?.length ?? 0), 0) ?? 0
  const pct     = report.coverage_percentage ?? 0
  const pctCls  = pct >= 70 ? 'text-green-400' : pct >= 40 ? 'text-yellow-400' : 'text-red-400'

  const handleImport = async () => {
    setImporting(true)
    try {
      // 1. Create exam shell
      const examRes = await examAPI.create({
        title:            exam.title,
        description:      exam.description,
        duration_minutes: exam.duration_minutes,
        total_marks:      exam.total_marks,
        pass_percentage:  exam.pass_percentage,
        negative_marking: exam.negative_marking,
      })
      const newExamId = examRes.data.id

      // 2. Create sections + questions
      for (const sec of (exam.sections || [])) {
        const secRes    = await examAPI.addSection(newExamId, { title: sec.title, order_index: 0 })
        const sectionId = secRes.data.id

        for (const q of (sec.questions || [])) {
          await questionAPI.create({
            section_id:     sectionId,
            question_type:  q.question_type === 'mcq' ? 'mcq_single' : q.question_type,
            text:           q.text,
            marks:          q.marks ?? 1,
            negative_marks: 0,
            difficulty:     q.difficulty ?? 'medium',
            explanation:    q.explanation ?? '',
            correct_answer: q.correct_answer ?? '',
            options:        (q.options || []).map(o => ({ text: o.text, is_correct: o.is_correct })),
          })
        }
      }

      toast.success('Exam imported! Opening editor…')
      onImported?.()
      navigate(`/admin/exams/${newExamId}/edit`)
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Import failed')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="glass-card p-6 space-y-5">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-semibold text-white text-lg">{exam?.title}</h2>
          <p className="text-slate-400 text-sm">{exam?.description}</p>
        </div>
        <div className="flex items-center gap-2">
          {result.source === 'web_search' && (
            <span className="badge-blue text-xs">🌐 Web search</span>
          )}
          <button className="btn-primary text-sm" onClick={handleImport} disabled={importing}>
            {importing ? 'Importing…' : '⬆ Import to Exams'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
        {[
          { label: 'Questions', value: totalQs },
          { label: 'Marks',     value: exam?.total_marks },
          { label: 'Duration',  value: `${exam?.duration_minutes}m` },
          { label: 'Coverage',  value: `${pct}%`, cls: pctCls },
          { label: 'Topics',    value: `${report.topics_covered ?? 0}/${report.total_topics_in_syllabus ?? 0}` },
        ].map(({ label, value, cls }) => (
          <div key={label} className="bg-slate-800/50 rounded-xl p-3 text-center">
            <p className={`text-xl font-bold ${cls ?? 'text-white'}`}>{value}</p>
            <p className="text-xs text-slate-500 mt-0.5">{label}</p>
          </div>
        ))}
      </div>

      {/* Queries used */}
      {result.queries_used?.length > 0 && (
        <div>
          <p className="label mb-2">Queries used</p>
          <div className="flex flex-wrap gap-2">
            {result.queries_used.map((q, i) => (
              <span key={i} className="badge-gray text-xs">{q}</span>
            ))}
          </div>
        </div>
      )}

      {/* Weak areas */}
      {report.weak_areas?.length > 0 && (
        <div>
          <p className="label mb-2">Weak coverage areas</p>
          <div className="space-y-1">
            {report.weak_areas.slice(0, 3).map((w, i) => (
              <div key={i} className="text-xs text-yellow-400 bg-yellow-500/10 rounded-lg px-3 py-2">
                {w.section} — {w.questions_generated} q / {w.topics_in_syllabus} topics
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Question preview */}
      <div>
        <p className="label mb-2">Preview (first 5 questions)</p>
        <div className="space-y-2">
          {exam?.sections?.flatMap(s => s.questions || []).slice(0, 5).map((q, i) => (
            <div key={i} className="bg-slate-800/40 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-1">
                <span className="badge-gray text-xs">{i + 1}</span>
                <span className="badge-blue text-xs">{q.question_type}</span>
                <span className="text-slate-500 text-xs">{q.marks} mark{q.marks !== 1 ? 's' : ''}</span>
              </div>
              <p className="text-slate-300 text-sm">{q.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function SyllabusUpload() {
  const [tab, setTab]       = useState('upload')
  const [result, setResult] = useState(null)
  const [settings, setSettings] = useState({
    num_questions:  10,
    difficulty:     'mixed',
    question_types: 'mixed',
    time_limit:     30,
    exam_title:     '',
    focus_topics:   '',
  })

  const setField = (k, v) => setSettings(s => ({ ...s, [k]: v }))

  return (
    <AppLayout>
      <div className="max-w-3xl mx-auto space-y-8">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Generate from Syllabus</h1>
            <p className="text-slate-400 text-sm mt-0.5">
              Upload a file or search by topic — we'll auto-generate exam questions.
            </p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex rounded-xl overflow-hidden border border-slate-700 w-fit">
          {[
            { key: 'upload', label: '📄 Upload File' },
            { key: 'search', label: '🔍 Search Topics' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => { setTab(key); setResult(null) }}
              className={`px-6 py-2.5 text-sm font-medium transition-all
                ${tab === key ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="glass-card p-6">
          {tab === 'upload'
            ? <UploadTab settings={settings} setField={setField} onResult={setResult} />
            : <SearchTab settings={settings} setField={setField} onResult={setResult} />
          }
        </div>

        {/* Result */}
        {result?.success && (
          <ResultPreview result={result} onImported={() => setResult(null)} />
        )}

      </div>
    </AppLayout>
  )
}
