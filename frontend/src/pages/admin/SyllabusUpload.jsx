import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api, { examAPI, questionAPI } from "../../services/api";
import toast from "react-hot-toast";

// ── Icons ─────────────────────────────────────────────────────────────────────
const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-6 h-6">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
  </svg>
);
const SparkIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
    <path fillRule="evenodd" d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813A3.75 3.75 0 007.466 7.89l.813-2.846A.75.75 0 019 4.5zM18 1.5a.75.75 0 01.728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 010 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 01-1.456 0l-.258-1.036a2.625 2.625 0 00-1.91-1.91l-1.036-.258a.75.75 0 010-1.456l1.036-.258a2.625 2.625 0 001.91-1.91l.258-1.036A.75.75 0 0118 1.5z" clipRule="evenodd" />
  </svg>
);
const FileIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-8 h-8">
    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
  </svg>
);
const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
  </svg>
);
const ArrowRightIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
  </svg>
);
const ImportIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 8.25H7.5a2.25 2.25 0 00-2.25 2.25v9a2.25 2.25 0 002.25 2.25h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25H15M9 12l3 3m0 0l3-3m-3 3V2.25" />
  </svg>
);
// ── NEW: Search icon ──────────────────────────────────────────────────────────
const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-6 h-6">
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
  </svg>
);

const difficultyColor = {
  easy:   "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  hard:   "bg-red-100 text-red-700",
  mixed:  "bg-violet-100 text-violet-700",
};

// Map AI generator question_type → backend QuestionType enum
const typeMap = {
  mcq:          "mcq_single",
  mcq_single:   "mcq_single",
  mcq_multiple: "mcq_multiple",
  true_false:   "true_false",
  short_answer: "short_answer",
  fill_blank:   "fill_blank",
};

// ══════════════════════════════════════════════════════════════════════════════
export default function SyllabusUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [syllabusText, setSyllabusText] = useState("");
  const [searchTopics, setSearchTopics] = useState("");       // ← NEW
  const [inputMode, setInputMode] = useState("file");         // "file" | "text" | "search"
  const [dragging, setDragging] = useState(false);

  const [config, setConfig] = useState({
    num_questions: 10,
    difficulty: "medium",
    question_types: "mixed",
    time_limit: 30,
    exam_title: "",
    focus_topics: "",
  });

  const [step, setStep] = useState("upload"); // upload | generating | done | importing | imported | error
  const [progress, setProgress] = useState(0);
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0, label: "" });
  const [result, setResult] = useState(null);
  const [importedExamId, setImportedExamId] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  // ── Drag-and-drop ───────────────────────────────────────────────────────────
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  }, []);

  const acceptFile = (f) => {
    const allowed = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"];
    if (!allowed.includes(f.type) && !f.name.match(/\.(pdf|docx|txt)$/i)) {
      setErrorMsg("Only PDF, DOCX, or TXT files are supported.");
      return;
    }
    if (f.size > 10 * 1024 * 1024) { setErrorMsg("File must be under 10 MB."); return; }
    setErrorMsg("");
    setFile(f);
  };

  const updateConfig = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

  // ── Generate ────────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    // Validation per mode
    if (inputMode === "file" && !file) { setErrorMsg("Please upload a syllabus file."); return; }
    if (inputMode === "text" && syllabusText.trim().length < 50) { setErrorMsg("Please paste at least 50 characters."); return; }
    if (inputMode === "search" && searchTopics.trim().length < 3) { setErrorMsg("Please enter at least one topic to search."); return; }

    setStep("generating");
    setProgress(0);
    setErrorMsg("");

    const ticker = setInterval(() => {
      setProgress(p => p < 88 ? p + Math.random() * 7 : p);
    }, 600);

    try {
      let data;

      // ── Search mode: POST JSON to search-and-generate ──────────────────────
      if (inputMode === "search") {
        const res = await api.post("/api/syllabus/search-and-generate", {
          topics:         searchTopics,
          num_questions:  config.num_questions,
          difficulty:     config.difficulty,
          question_types: config.question_types,
          time_limit:     config.time_limit,
          exam_title:     config.exam_title || null,
          focus_topics:   config.focus_topics || null,
          extra_context:  "",
        });
        data = res.data;
      } else {
        // ── File / text mode: POST multipart to upload-and-generate ───────────
        const formData = new FormData();
        if (inputMode === "file" && file) {
          formData.append("file", file);
        } else {
          // wrap pasted text as a .txt blob
          const blob = new Blob([syllabusText], { type: "text/plain" });
          formData.append("file", blob, "syllabus.txt");
        }
        formData.append("num_questions",  config.num_questions);
        formData.append("difficulty",     config.difficulty);
        formData.append("question_types", config.question_types);
        formData.append("time_limit",     config.time_limit);
        if (config.exam_title)   formData.append("exam_title",   config.exam_title);
        if (config.focus_topics) formData.append("focus_topics", config.focus_topics);

        const res = await api.post("/api/syllabus/upload-and-generate", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        data = res.data;
      }

      clearInterval(ticker);
      setProgress(100);
      setResult(data);
      setStep("done");
    } catch (err) {
      clearInterval(ticker);
      setErrorMsg(err?.response?.data?.detail || "Generation failed. Please try again.");
      setStep("error");
    }
  };

  // ── Import — saves exam + sections + questions ──────────────────────────────
  const handleImport = async () => {
    if (!result?.exam) return;
    setStep("importing");

    try {
      const examData = result.exam;
      const allQuestions = (examData.sections || []).flatMap(s => s.questions || []);
      const total = allQuestions.length;
      setImportProgress({ current: 0, total, label: "Creating exam…" });

      const examPayload = {
        title:            examData.title || config.exam_title || "Generated Exam",
        description:      examData.description || "",
        instructions:     examData.instructions || "",
        duration_minutes: examData.duration_minutes || config.time_limit || 30,
        total_marks:      examData.total_marks || allQuestions.reduce((s, q) => s + (q.marks || 1), 0),
        pass_percentage:  examData.pass_percentage || 40,
        negative_marking: examData.negative_marking || false,
        shuffle_questions: false,
        shuffle_options:   false,
        max_attempts:      1,
        is_active:         true,
        is_public:         true,
        show_result_immediately: true,
      };

      const examRes = await examAPI.create(examPayload);
      const examId = examRes.data.id;

      let questionsDone = 0;

      for (let si = 0; si < (examData.sections || []).length; si++) {
        const section = examData.sections[si];
        setImportProgress({ current: questionsDone, total, label: `Creating section "${section.title}"…` });

        const sectionRes = await examAPI.addSection(examId, {
          title:       section.title || `Section ${si + 1}`,
          description: section.description || "",
          order:       si,
        });
        const sectionId = sectionRes.data.id;
        const sectionQuestions = section.questions || [];

        for (let qi = 0; qi < sectionQuestions.length; qi++) {
          const q = sectionQuestions[qi];
          setImportProgress({ current: questionsDone, total, label: `Saving question ${questionsDone + 1} of ${total}…` });

          const qType = typeMap[q.question_type] || "mcq_single";
          const options = (q.options || []).map((o, oi) => ({
            text:       o.text || `Option ${oi + 1}`,
            is_correct: Boolean(o.is_correct),
            order:      oi,
          }));

          if (qType === "true_false" && options.length === 0) {
            const correctAnswer = (q.correct_answer || "").toLowerCase();
            options.push(
              { text: "True",  is_correct: correctAnswer === "true",  order: 0 },
              { text: "False", is_correct: correctAnswer === "false", order: 1 },
            );
          }

          try {
            await questionAPI.create({
              section_id:     sectionId,
              question_type:  qType,
              text:           q.text || "Question",
              explanation:    q.explanation || "",
              marks:          Number(q.marks) || 1,
              negative_marks: 0,
              order:          qi,
              options,
            });
          } catch (qErr) {
            console.warn(`Question ${qi + 1} failed:`, qErr?.response?.data);
          }

          questionsDone++;
        }
      }

      setImportProgress({ current: total, total, label: "Done!" });
      setImportedExamId(examId);
      setStep("imported");
      toast.success(`Exam imported! ${total} questions saved.`);
    } catch (err) {
      console.error("Import error:", err);
      setErrorMsg(err?.response?.data?.detail || "Import failed. Please try again.");
      setStep("done");
      toast.error("Import failed — see error above.");
    }
  };

  const reset = () => {
    setStep("upload");
    setFile(null);
    setSyllabusText("");
    setSearchTopics("");
    setResult(null);
    setErrorMsg("");
    setProgress(0);
    setImportedExamId(null);
    setImportProgress({ current: 0, total: 0, label: "" });
    setConfig({ num_questions: 10, difficulty: "medium", question_types: "mixed", time_limit: 30, exam_title: "", focus_topics: "" });
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-5">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white">
              <SparkIcon />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">AI Exam Generator</h1>
              <p className="text-sm text-gray-500">Upload a syllabus or search topics → AI creates a full exam instantly</p>
            </div>
          </div>
          {/* ── Back button ── */}
          <button
            onClick={() => navigate("/admin")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors border border-gray-200"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* ════════ IMPORTED STATE ════════ */}
        {step === "imported" && (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-600 px-8 py-10 text-white text-center">
              <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckIcon />
              </div>
              <h2 className="text-2xl font-bold mb-1">Exam Saved to Database!</h2>
              <p className="text-emerald-100 text-sm">Live and visible to candidates immediately</p>
            </div>
            <div className="p-8 flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => navigate(`/admin/exams/${importedExamId}/edit`)}
                className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Edit Exam <ArrowRightIcon />
              </button>
              <button
                onClick={() => navigate("/admin/exams")}
                className="flex-1 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                All Exams
              </button>
              <button
                onClick={reset}
                className="flex-1 flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-600 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Generate Another
              </button>
            </div>
          </div>
        )}

        {/* ════════ IMPORTING STATE ════════ */}
        {step === "importing" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <div className="relative w-24 h-24 mx-auto mb-6">
              <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
                <circle cx="48" cy="48" r="40" fill="none" stroke="#e0e7ff" strokeWidth="8" />
                <circle cx="48" cy="48" r="40" fill="none" stroke="#10b981" strokeWidth="8"
                  strokeDasharray={`${2 * Math.PI * 40}`}
                  strokeDashoffset={`${2 * Math.PI * 40 * (1 - (importProgress.total ? importProgress.current / importProgress.total : 0))}`}
                  strokeLinecap="round"
                  style={{ transition: "stroke-dashoffset 0.3s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-emerald-600">
                  {importProgress.total ? Math.round(importProgress.current / importProgress.total * 100) : 0}%
                </span>
              </div>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">Saving to Database…</h2>
            <p className="text-sm text-gray-500 mb-2">{importProgress.label}</p>
            <p className="text-xs text-gray-400">{importProgress.current} of {importProgress.total} questions saved</p>
          </div>
        )}

        {/* ════════ DONE STATE ════════ */}
        {step === "done" && result && (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-8 py-10 text-white text-center">
              <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckIcon />
              </div>
              <h2 className="text-2xl font-bold mb-1">Exam Generated!</h2>
              <p className="text-indigo-200 text-sm">Preview below — click "Save to Database" to make it live</p>
            </div>

            {errorMsg && (
              <div className="mx-8 mt-6 flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 flex items-center justify-center font-bold text-red-600">!</span>
                {errorMsg}
              </div>
            )}

            {/* Stats */}
            <div className="p-8 grid grid-cols-2 sm:grid-cols-4 gap-4 border-b border-gray-100">
              {[
                { label: "Questions", value: (result.exam?.sections || []).flatMap(s => s.questions || []).length },
                { label: "Total Marks", value: result.exam?.total_marks },
                { label: "Duration", value: `${result.exam?.duration_minutes} min` },
                { label: "Sections", value: result.exam?.sections?.length },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>

            {/* Coverage report */}
            {result.coverage_report && (
              <div className="px-8 py-4 bg-gray-50 border-b border-gray-100 text-sm text-gray-600">
                Coverage: <span className="font-semibold text-indigo-600">{result.coverage_report.coverage_percentage}%</span>
                {result.coverage_report.note && <span className="ml-3 text-xs text-gray-400">{result.coverage_report.note}</span>}
              </div>
            )}

            {/* Preview first 5 questions */}
            {(result.exam?.sections || []).flatMap(s => s.questions || []).slice(0, 5).length > 0 && (
              <div className="px-8 py-6 space-y-4 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700">Question Preview (first 5)</h3>
                {(result.exam?.sections || []).flatMap(s => s.questions || []).slice(0, 5).map((q, i) => (
                  <div key={i} className="bg-gray-50 rounded-xl p-4">
                    <p className="text-sm font-medium text-gray-800 mb-2">{i + 1}. {q.text}</p>
                    {(q.options || []).map((o, oi) => (
                      <div key={oi} className={`text-xs px-3 py-1.5 rounded-lg mb-1 ${o.is_correct ? "bg-emerald-50 text-emerald-700 font-medium" : "text-gray-500"}`}>
                        {String.fromCharCode(65 + oi)}. {o.text}
                        {o.is_correct && <span className="ml-2 text-emerald-500">✓ correct</span>}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}

            {/* Action buttons */}
            <div className="p-8 flex flex-col sm:flex-row gap-3">
              <button
                onClick={handleImport}
                className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                <ImportIcon />
                Save to Database
              </button>
              <button
                onClick={() => navigate("/admin/exams")}
                className="flex-1 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                All Exams
              </button>
              <button
                onClick={reset}
                className="flex-1 flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-600 font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                Start Over
              </button>
            </div>
          </div>
        )}

        {/* ════════ GENERATING STATE ════════ */}
        {step === "generating" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <div className="relative w-24 h-24 mx-auto mb-6">
              <svg className="w-24 h-24 -rotate-90 animate-spin" style={{ animationDuration: "2s" }} viewBox="0 0 96 96">
                <circle cx="48" cy="48" r="40" fill="none" stroke="#e0e7ff" strokeWidth="8" />
                <circle cx="48" cy="48" r="40" fill="none" stroke="#4f46e5" strokeWidth="8"
                  strokeDasharray={`${2 * Math.PI * 40}`}
                  strokeDashoffset={`${2 * Math.PI * 40 * (1 - progress / 100)}`}
                  strokeLinecap="round"
                  style={{ transition: "stroke-dashoffset 0.5s ease" }}
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-lg font-bold text-indigo-600">{Math.round(progress)}%</span>
              </div>
            </div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">
              {inputMode === "search" ? "Searching & generating your exam…" : "Generating your exam…"}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              {inputMode === "search"
                ? "Searching the web for your topics and crafting questions. Takes ~15–30 seconds."
                : "Reading your syllabus and crafting questions. Takes ~10–20 seconds."}
            </p>
            <div className="space-y-2 max-w-xs mx-auto text-left">
              {(inputMode === "search"
                ? [
                    { label: "Searching web for topics", done: progress > 15 },
                    { label: "Extracting key content",   done: progress > 35 },
                    { label: "Generating questions",     done: progress > 65 },
                    { label: "Structuring exam format",  done: progress > 85 },
                    { label: "Finalising output",        done: progress >= 100 },
                  ]
                : [
                    { label: "Reading syllabus content", done: progress > 15 },
                    { label: "Identifying key topics",   done: progress > 35 },
                    { label: "Generating questions",     done: progress > 65 },
                    { label: "Structuring exam format",  done: progress > 85 },
                    { label: "Finalising output",        done: progress >= 100 },
                  ]
              ).map(({ label, done }) => (
                <div key={label} className="flex items-center gap-2.5 text-sm">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${done ? "bg-indigo-600 text-white" : "bg-gray-200"}`}>
                    {done && <CheckIcon />}
                  </span>
                  <span className={done ? "text-gray-900" : "text-gray-400"}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ════════ UPLOAD STATE ════════ */}
        {(step === "upload" || step === "error") && (
          <>
            {errorMsg && (
              <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 flex items-center justify-center font-bold text-red-600">!</span>
                {errorMsg}
                <button onClick={() => { setErrorMsg(""); setStep("upload"); }} className="ml-auto text-red-400 hover:text-red-600"><XIcon /></button>
              </div>
            )}

            {/* ── Syllabus Input ─────────────────────────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
                <h2 className="font-semibold text-gray-900">1. Syllabus Content</h2>
                {/* ── Three-tab switcher ── */}
                <div className="flex rounded-lg overflow-hidden border border-gray-200 text-sm">
                  <button
                    onClick={() => setInputMode("file")}
                    className={`px-4 py-1.5 font-medium transition-colors flex items-center gap-1.5 ${inputMode === "file" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                  >
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path d="M3 3.5A1.5 1.5 0 014.5 2h6.879a1.5 1.5 0 011.06.44l4.122 4.12A1.5 1.5 0 0117 7.622V16.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 013 16.5v-13z" /></svg>
                    Upload File
                  </button>
                  <button
                    onClick={() => setInputMode("text")}
                    className={`px-4 py-1.5 font-medium transition-colors flex items-center gap-1.5 ${inputMode === "text" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                  >
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" /></svg>
                    Paste Text
                  </button>
                  {/* ── NEW: Search tab ── */}
                  <button
                    onClick={() => setInputMode("search")}
                    className={`px-4 py-1.5 font-medium transition-colors flex items-center gap-1.5 ${inputMode === "search" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                  >
                    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" /></svg>
                    Search Topics
                  </button>
                </div>
              </div>

              <div className="p-6">
                {/* ── File upload panel ── */}
                {inputMode === "file" && (
                  file ? (
                    <div className="flex items-center gap-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl">
                      <div className="text-indigo-500"><FileIcon /></div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{file.name}</p>
                        <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                      </div>
                      <button onClick={() => setFile(null)} className="text-gray-400 hover:text-red-500 transition-colors"><XIcon /></button>
                    </div>
                  ) : (
                    <div
                      onDrop={handleDrop}
                      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                      onDragLeave={() => setDragging(false)}
                      onClick={() => fileInputRef.current?.click()}
                      className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${dragging ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"}`}
                    >
                      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={e => e.target.files[0] && acceptFile(e.target.files[0])} />
                      <div className={`inline-flex w-14 h-14 rounded-2xl items-center justify-center mb-4 transition-colors ${dragging ? "bg-indigo-100 text-indigo-600" : "bg-gray-100 text-gray-400"}`}><UploadIcon /></div>
                      <p className="font-semibold text-gray-700 mb-1">Drop your syllabus here</p>
                      <p className="text-sm text-gray-400">or click to browse — PDF, DOCX, or TXT up to 10 MB</p>
                    </div>
                  )
                )}

                {/* ── Paste text panel ── */}
                {inputMode === "text" && (
                  <div>
                    <textarea
                      value={syllabusText}
                      onChange={e => setSyllabusText(e.target.value)}
                      placeholder={"Paste your syllabus content here…\n\nExample:\nUnit 1: Introduction\n- Topic A, Topic B\nUnit 2: Advanced\n- Topic C, Topic D"}
                      className="w-full h-52 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    />
                    <p className="text-xs text-gray-400 mt-1.5">
                      {syllabusText.length} characters{" "}
                      {syllabusText.length < 50 && syllabusText.length > 0 && <span className="text-amber-500">(need at least 50)</span>}
                    </p>
                  </div>
                )}

                {/* ── NEW: Search topics panel ── */}
                {inputMode === "search" && (
                  <div className="space-y-4">
                    <div className="flex items-start gap-3 p-4 bg-indigo-50 border border-indigo-100 rounded-xl">
                      <div className="text-indigo-500 mt-0.5 flex-shrink-0"><SearchIcon /></div>
                      <div>
                        <p className="text-sm font-medium text-indigo-800 mb-0.5">Web Search Mode</p>
                        <p className="text-xs text-indigo-600">
                          Enter topics and the AI will search the web for current content, then generate questions from what it finds. Great for any subject — no file needed.
                        </p>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Topics to search <span className="text-red-400">*</span>
                      </label>
                      <textarea
                        value={searchTopics}
                        onChange={e => setSearchTopics(e.target.value)}
                        placeholder={"Enter topics separated by commas or new lines…\n\nExamples:\nOdisha History, Indian Constitution, General Science\nMathematics - Algebra, Trigonometry\nEnglish Grammar, Comprehension"}
                        className="w-full h-36 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                      />
                      <p className="text-xs text-gray-400 mt-1.5">
                        {searchTopics.trim().length} characters
                        {searchTopics.trim().length > 0 && searchTopics.trim().length < 3 && (
                          <span className="text-amber-500 ml-1">(enter at least one topic)</span>
                        )}
                      </p>
                    </div>
                    <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-amber-700">
                      💡 <strong>Tip:</strong> More specific topics = better questions. Try "Odisha Geography — rivers and mountains" instead of just "Geography".
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── Exam Configuration ─────────────────────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">2. Exam Configuration</h2>
              </div>
              <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Exam Title <span className="text-gray-400 font-normal">(optional)</span></label>
                  <input
                    type="text"
                    value={config.exam_title}
                    onChange={e => updateConfig("exam_title", e.target.value)}
                    placeholder="e.g. OSSSC RI/ARI Mock Test"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Questions: <span className="text-indigo-600 font-bold">{config.num_questions}</span></label>
                  <input type="range" min={3} max={300} value={config.num_questions} onChange={e => updateConfig("num_questions", Number(e.target.value))} className="w-full accent-indigo-600" />
                  <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>3</span><span>300</span></div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Time: <span className="text-indigo-600 font-bold">{config.time_limit} min</span></label>
                  <input type="range" min={5} max={180} step={5} value={config.time_limit} onChange={e => updateConfig("time_limit", Number(e.target.value))} className="w-full accent-indigo-600" />
                  <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>5 min</span><span>3 hr</span></div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Difficulty</label>
                  <div className="grid grid-cols-2 gap-2">
                    {["easy","medium","hard","mixed"].map(d => (
                      <button key={d} onClick={() => updateConfig("difficulty", d)} className={`py-2 rounded-xl text-sm font-medium border transition-all capitalize ${config.difficulty === d ? "border-indigo-600 bg-indigo-50 text-indigo-700" : "border-gray-200 text-gray-600 hover:border-gray-300"}`}>
                        <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${d==="easy"?"bg-emerald-400":d==="medium"?"bg-amber-400":d==="hard"?"bg-red-400":"bg-violet-400"}`} />{d}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Question Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[{val:"mcq",label:"MCQ Only"},{val:"mixed",label:"Mixed"},{val:"true_false",label:"True/False"},{val:"short",label:"Short Answer"}].map(({val,label}) => (
                      <button key={val} onClick={() => updateConfig("question_types", val)} className={`py-2 rounded-xl text-sm font-medium border transition-all ${config.question_types===val?"border-indigo-600 bg-indigo-50 text-indigo-700":"border-gray-200 text-gray-600 hover:border-gray-300"}`}>{label}</button>
                    ))}
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Focus Topics <span className="text-gray-400 font-normal">(optional, comma-separated)</span>
                  </label>
                  <input
                    type="text"
                    value={config.focus_topics}
                    onChange={e => updateConfig("focus_topics", e.target.value)}
                    placeholder="e.g. Odisha Geography, Indian History"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
              </div>
            </div>

            {/* ── Review & Generate ──────────────────────────────────────────── */}
            <div className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="font-semibold text-gray-900 mb-4">3. Review & Generate</h2>
              <div className="flex flex-wrap gap-2 mb-6">
                <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm">{config.num_questions} questions</span>
                <span className={`px-3 py-1 rounded-full text-sm capitalize ${difficultyColor[config.difficulty]}`}>{config.difficulty}</span>
                <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm">{config.time_limit} min</span>
                {inputMode === "file" && file && (
                  <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm">📄 {file.name}</span>
                )}
                {inputMode === "search" && searchTopics.trim() && (
                  <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">🔍 Web search</span>
                )}
                {inputMode === "text" && syllabusText.trim() && (
                  <span className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm">📝 Pasted text</span>
                )}
              </div>
              <button
                onClick={handleGenerate}
                className="w-full flex items-center justify-center gap-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold py-4 rounded-xl text-base transition-all"
              >
                <SparkIcon />
                {inputMode === "search" ? "Search & Generate Exam" : "Generate Exam"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
