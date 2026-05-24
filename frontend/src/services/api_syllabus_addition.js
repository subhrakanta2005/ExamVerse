// ── Syllabus / AI Generation ──────────────────────────────────────────────────
// Add this block to your existing api.js, after the userAPI block.

export const syllabusAPI = {
  // Upload a file (TXT/PDF/DOCX) and generate an exam from it
  uploadAndGenerate: (file, settings) => {
    const form = new FormData()
    form.append('file', file)
    form.append('num_questions',  String(settings.num_questions  ?? 10))
    form.append('difficulty',     settings.difficulty            ?? 'mixed')
    form.append('question_types', settings.question_types        ?? 'mixed')
    form.append('time_limit',     String(settings.time_limit     ?? 30))
    if (settings.exam_title)   form.append('exam_title',   settings.exam_title)
    if (settings.focus_topics) form.append('focus_topics', settings.focus_topics)
    // Must NOT pass Content-Type header — axios will set it with the boundary
    return api.post('/api/syllabus/upload-and-generate', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  // Search web topics (Tavily) and generate an exam from fetched content
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
