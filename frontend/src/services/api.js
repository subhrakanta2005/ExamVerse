import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
})

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('examforge_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Handle auth errors globally
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('examforge_token')
      localStorage.removeItem('examforge_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authAPI = {
  signup:        (data)  => api.post('/api/auth/signup', data),
  login:         (data)  => api.post('/api/auth/login', data),
  me:            ()      => api.get('/api/auth/me'),
  forgotPassword:(email) => api.post('/api/auth/forgot-password', { email }),
  resetPassword: (data)  => api.post('/api/auth/reset-password', data),
}

// ── Exams ─────────────────────────────────────────────────────────────────────
export const examAPI = {
  getAvailable:    ()                   => api.get('/api/exams/available'),
  getAdminAll:     (skip=0, limit=20)   => api.get(`/api/exams/admin/all?skip=${skip}&limit=${limit}`),
  // getOne routes to the admin endpoint (full detail with answers)
  getOne:          (id)                 => api.get(`/api/exams/${id}`),
  getForCandidate: (id)                 => api.get(`/api/exams/${id}/candidate`),
  create:          (data)               => api.post('/api/exams/', data),
  update:          (id, data)           => api.put(`/api/exams/${id}`, data),
  delete:          (id)                 => api.delete(`/api/exams/${id}`),
  addSection:      (examId, data)       => api.post(`/api/exams/${examId}/sections`, data),
  // deleteSection — was missing, now wired to backend DELETE /{examId}/sections/{sectionId}
  deleteSection:   (examId, sectionId)  => api.delete(`/api/exams/${examId}/sections/${sectionId}`),
  assign:          (examId, userIds)    => api.post(`/api/exams/${examId}/assign`, userIds),
}

// ── Questions ─────────────────────────────────────────────────────────────────
export const questionAPI = {
  create:        (data)     => api.post('/api/questions/', data),
  update:        (id, data) => api.put(`/api/questions/${id}`, data),
  delete:        (id)       => api.delete(`/api/questions/${id}`),
  getBySectionId:(sectionId)=> api.get(`/api/questions/section/${sectionId}`),
}

// ── Attempts ──────────────────────────────────────────────────────────────────
export const attemptAPI = {
  start:           (examId)       => api.post('/api/attempts/start', { exam_id: examId }),
  getMyAttempts:   ()             => api.get('/api/attempts/my'),
  getOne:          (id)           => api.get(`/api/attempts/${id}`),
  getAnswers:      (attemptId)    => api.get(`/api/attempts/${attemptId}/answers`),
  saveAnswer:      (attemptId, d) => api.post(`/api/attempts/${attemptId}/answer`, d),
  recordTabSwitch: (attemptId)    => api.post(`/api/attempts/${attemptId}/tab-switch`),
  submit:          (attemptId, auto=false) =>
    api.post(`/api/attempts/${attemptId}/submit?auto_submit=${auto}`),
}

// ── Results ───────────────────────────────────────────────────────────────────
export const resultAPI = {
  getMy:       ()          => api.get('/api/results/my'),
  getOne:      (id)        => api.get(`/api/results/${id}`),
  getByAttempt:(attemptId) => api.get(`/api/results/attempt/${attemptId}`),
  adminGetAll: (examId)    =>
    api.get(`/api/results/admin/all${examId ? `?exam_id=${examId}` : ''}`),
  publish:     (resultId)  => api.post(`/api/results/admin/${resultId}/publish`),
  // evaluate — payload uses marks_obtained (matches EvaluateAnswer schema)
  evaluate:    (data)      => api.post('/api/results/admin/evaluate', {
    answer_id:          data.answer_id,
    marks_obtained:     data.awarded_marks ?? data.marks_obtained,
    is_correct:         (data.awarded_marks ?? data.marks_obtained) > 0,
    evaluator_comment:  data.evaluator_comment ?? null,
  }),
}

// ── Admin ─────────────────────────────────────────────────────────────────────
export const adminAPI = {
  overview:       ()               => api.get('/api/admin/analytics/overview'),
  examAnalytics:  (examId)         => api.get(`/api/admin/analytics/exam/${examId}`),
  leaderboard:    (examId, limit=10) =>
    api.get(`/api/admin/analytics/leaderboard/${examId}?limit=${limit}`),
  manualQueue:    ()               => api.get('/api/admin/manual-queue'),
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const userAPI = {
  getAll:  (skip=0, limit=50) => api.get(`/api/users/?skip=${skip}&limit=${limit}`),
  update:  (id, data)         => api.patch(`/api/users/${id}`, data),
  delete:  (id)               => api.delete(`/api/users/${id}`),
}

// ── Syllabus / AI Generation ──────────────────────────────────────────────────
export const syllabusAPI = {
  uploadAndGenerate: (file, settings) => {
    const form = new FormData()
    form.append('file', file)
    form.append('num_questions',  String(settings.num_questions  ?? 10))
    form.append('difficulty',     settings.difficulty            ?? 'mixed')
    form.append('question_types', settings.question_types        ?? 'mixed')
    form.append('time_limit',     String(settings.time_limit     ?? 30))
    if (settings.exam_title)   form.append('exam_title',   settings.exam_title)
    if (settings.focus_topics) form.append('focus_topics', settings.focus_topics)
    return api.post('/api/syllabus/upload-and-generate', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  searchAndGenerate: (params) =>
    api.post('/api/syllabus/search-and-generate', {
      topics:         params.topics,
      num_questions:  params.num_questions  ?? 10,
      difficulty:     params.difficulty     ?? 'mixed',
      question_types: params.question_types ?? 'mixed',
      time_limit:     params.time_limit     ?? 30,
      exam_title:     params.exam_title     || null,
      focus_topics:   params.focus_topics   || null,
      extra_context:  params.extra_context  ?? '',
    }),
}

export default api
