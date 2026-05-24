import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../../services/api";

// ── Icons (inline SVGs — no extra dep) ────────────────────────────────────────
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

// ── Difficulty badge color ─────────────────────────────────────────────────────
const difficultyColor = {
  easy:   "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  hard:   "bg-red-100 text-red-700",
  mixed:  "bg-violet-100 text-violet-700",
};

// ══════════════════════════════════════════════════════════════════════════════
export default function SyllabusUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  // ── Form state ──────────────────────────────────────────────────────────────
  const [file, setFile] = useState(null);
  const [syllabusText, setSyllabusText] = useState("");
  const [inputMode, setInputMode] = useState("file"); // "file" | "text"
  const [dragging, setDragging] = useState(false);

  const [config, setConfig] = useState({
    num_questions: 10,
    difficulty: "medium",
    question_types: "mixed",
    time_limit: 30,
    exam_title: "",
    focus_topics: "",
  });

  // ── UI state ────────────────────────────────────────────────────────────────
  const [step, setStep] = useState("upload"); // "upload" | "generating" | "done" | "error"
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");

  // ── Drag-and-drop handlers ──────────────────────────────────────────────────
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = () => setDragging(false);

  const acceptFile = (f) => {
    const allowed = ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain"];
    if (!allowed.includes(f.type) && !f.name.match(/\.(pdf|docx|txt)$/i)) {
      setErrorMsg("Only PDF, DOCX, or TXT files are supported.");
      return;
    }
    if (f.size > 10 * 1024 * 1024) {
      setErrorMsg("File must be under 10 MB.");
      return;
    }
    setErrorMsg("");
    setFile(f);
  };

  // ── Config helpers ──────────────────────────────────────────────────────────
  const updateConfig = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

  // ── Submit ──────────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (inputMode === "file" && !file) { setErrorMsg("Please upload a syllabus file."); return; }
    if (inputMode === "text" && syllabusText.trim().length < 50) { setErrorMsg("Please paste at least 50 characters of syllabus content."); return; }

    setStep("generating");
    setProgress(0);
    setErrorMsg("");

    // Fake progress while waiting for AI
    const ticker = setInterval(() => {
      setProgress(p => p < 88 ? p + Math.random() * 7 : p);
    }, 600);

    try {
      const formData = new FormData();
      if (inputMode === "file" && file) formData.append("file", file);
      if (inputMode === "text") formData.append("syllabus_text", syllabusText);
      formData.append("num_questions", config.num_questions);
      formData.append("difficulty", config.difficulty);
      formData.append("question_types", config.question_types);
      formData.append("time_limit", config.time_limit);
      if (config.exam_title) formData.append("exam_title", config.exam_title);
      if (config.focus_topics) formData.append("focus_topics", config.focus_topics);

      const { data } = await api.post("/api/syllabus/upload-and-generate", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

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

  const reset = () => {
    setStep("upload");
    setFile(null);
    setSyllabusText("");
    setResult(null);
    setErrorMsg("");
    setProgress(0);
    setConfig({ num_questions: 10, difficulty: "medium", question_types: "mixed", time_limit: 30, exam_title: "", focus_topics: "" });
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Header ── */}
      <div className="bg-white border-b border-gray-200 px-6 py-5">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white">
            <SparkIcon />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">AI Exam Generator</h1>
            <p className="text-sm text-gray-500">Upload a syllabus → Gemini AI creates a full exam instantly</p>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* ════════ DONE STATE ════════ */}
        {step === "done" && result && (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-indigo-600 to-violet-600 px-8 py-10 text-white text-center">
              <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckIcon />
              </div>
              <h2 className="text-2xl font-bold mb-1">Exam Generated!</h2>
              <p className="text-indigo-200 text-sm">Saved to your exam library and ready to publish</p>
            </div>
            <div className="p-8 grid grid-cols-2 sm:grid-cols-4 gap-4 border-b border-gray-100">
              {[
                { label: "Exam Title",  value: result.exam?.title },
                { label: "Total Marks", value: result.exam?.total_marks },
                { label: "Duration",    value: `${result.exam?.duration_minutes} min` },
                { label: "Sections",    value: result.exam?.sections?.length },
              ].map(({ label, value }) => (
                <div key={label} className="text-center">
                  <p className="text-2xl font-bold text-gray-900">{value}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                </div>
              ))}
            </div>
            <div className="p-8 flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => navigate("/exam/take", { state: { exam: result.exam } })}
                className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors"
              >
                View Exam <ArrowRightIcon />
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

        {/* ════════ GENERATING STATE ════════ */}
        {step === "generating" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <div className="relative w-24 h-24 mx-auto mb-6">
              {/* Spinning ring */}
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
            <h2 className="text-xl font-bold text-gray-900 mb-2">Generating your exam…</h2>
            <p className="text-sm text-gray-500 mb-6">Gemini AI is reading your syllabus and crafting questions. This takes about 10–20 seconds.</p>
            <div className="space-y-2 max-w-xs mx-auto text-left">
              {[
                { label: "Reading syllabus content", done: progress > 15 },
                { label: "Identifying key topics",    done: progress > 35 },
                { label: "Generating questions",      done: progress > 65 },
                { label: "Structuring exam format",   done: progress > 85 },
                { label: "Saving to database",        done: progress >= 100 },
              ].map(({ label, done }) => (
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
            {/* Error banner */}
            {errorMsg && (
              <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-red-100 flex items-center justify-center font-bold text-red-600">!</span>
                {errorMsg}
                <button onClick={() => { setErrorMsg(""); setStep("upload"); }} className="ml-auto text-red-400 hover:text-red-600"><XIcon /></button>
              </div>
            )}

            {/* ── Syllabus Input ── */}
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">1. Syllabus Content</h2>
                <div className="flex rounded-lg overflow-hidden border border-gray-200 text-sm">
                  <button
                    onClick={() => setInputMode("file")}
                    className={`px-4 py-1.5 font-medium transition-colors ${inputMode === "file" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                  >Upload File</button>
                  <button
                    onClick={() => setInputMode("text")}
                    className={`px-4 py-1.5 font-medium transition-colors ${inputMode === "text" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                  >Paste Text</button>
                </div>
              </div>

              <div className="p-6">
                {inputMode === "file" ? (
                  file ? (
                    // File selected
                    <div className="flex items-center gap-4 p-4 bg-indigo-50 border border-indigo-200 rounded-xl">
                      <div className="text-indigo-500"><FileIcon /></div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{file.name}</p>
                        <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                      </div>
                      <button onClick={() => setFile(null)} className="text-gray-400 hover:text-red-500 transition-colors"><XIcon /></button>
                    </div>
                  ) : (
                    // Drop zone
                    <div
                      onDrop={handleDrop}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onClick={() => fileInputRef.current?.click()}
                      className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${dragging ? "border-indigo-400 bg-indigo-50" : "border-gray-200 hover:border-indigo-300 hover:bg-gray-50"}`}
                    >
                      <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={e => e.target.files[0] && acceptFile(e.target.files[0])} />
                      <div className={`inline-flex w-14 h-14 rounded-2xl items-center justify-center mb-4 transition-colors ${dragging ? "bg-indigo-100 text-indigo-600" : "bg-gray-100 text-gray-400"}`}>
                        <UploadIcon />
                      </div>
                      <p className="font-semibold text-gray-700 mb-1">Drop your syllabus here</p>
                      <p className="text-sm text-gray-400">or click to browse — PDF, DOCX, or TXT up to 10 MB</p>
                    </div>
                  )
                ) : (
                  // Paste text
                  <div>
                    <textarea
                      value={syllabusText}
                      onChange={e => setSyllabusText(e.target.value)}
                      placeholder="Paste your syllabus content here…&#10;&#10;Example:&#10;Unit 1: Introduction to Data Structures&#10;- Arrays, Linked Lists, Stacks, Queues&#10;Unit 2: Sorting Algorithms&#10;- Bubble Sort, Merge Sort, Quick Sort…"
                      className="w-full h-52 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
                    />
                    <p className="text-xs text-gray-400 mt-1.5">{syllabusText.length} characters {syllabusText.length < 50 && syllabusText.length > 0 && <span className="text-amber-500">(need at least 50)</span>}</p>
                  </div>
                )}
              </div>
            </div>

            {/* ── Exam Configuration ── */}
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-100">
                <h2 className="font-semibold text-gray-900">2. Exam Configuration</h2>
              </div>
              <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-5">

                {/* Exam Title */}
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Exam Title <span className="text-gray-400 font-normal">(optional — AI will auto-generate if blank)</span></label>
                  <input
                    type="text"
                    value={config.exam_title}
                    onChange={e => updateConfig("exam_title", e.target.value)}
                    placeholder="e.g. Data Structures Mid-Term Exam"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>

                {/* Number of questions */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Number of Questions: <span className="text-indigo-600 font-bold">{config.num_questions}</span>
                  </label>
                  <input
                    type="range" min={3} max={50} value={config.num_questions}
                    onChange={e => updateConfig("num_questions", Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>3</span><span>50</span></div>
                </div>

                {/* Time limit */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    Time Limit: <span className="text-indigo-600 font-bold">{config.time_limit} min</span>
                  </label>
                  <input
                    type="range" min={5} max={180} step={5} value={config.time_limit}
                    onChange={e => updateConfig("time_limit", Number(e.target.value))}
                    className="w-full accent-indigo-600"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-0.5"><span>5 min</span><span>3 hr</span></div>
                </div>

                {/* Difficulty */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Difficulty</label>
                  <div className="grid grid-cols-2 gap-2">
                    {["easy", "medium", "hard", "mixed"].map(d => (
                      <button
                        key={d}
                        onClick={() => updateConfig("difficulty", d)}
                        className={`py-2 rounded-xl text-sm font-medium border transition-all capitalize ${
                          config.difficulty === d
                            ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                            : "border-gray-200 text-gray-600 hover:border-gray-300"
                        }`}
                      >
                        <span className={`inline-block w-2 h-2 rounded-full mr-1.5 ${
                          d === "easy" ? "bg-emerald-400" : d === "medium" ? "bg-amber-400" : d === "hard" ? "bg-red-400" : "bg-violet-400"
                        }`} />
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Question Types */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Question Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { val: "mcq",        label: "MCQ Only" },
                      { val: "mixed",      label: "Mixed" },
                      { val: "true_false", label: "True / False" },
                      { val: "short",      label: "Short Answer" },
                    ].map(({ val, label }) => (
                      <button
                        key={val}
                        onClick={() => updateConfig("question_types", val)}
                        className={`py-2 rounded-xl text-sm font-medium border transition-all ${
                          config.question_types === val
                            ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                            : "border-gray-200 text-gray-600 hover:border-gray-300"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Focus topics */}
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">Focus Topics <span className="text-gray-400 font-normal">(optional — comma-separated)</span></label>
                  <input
                    type="text"
                    value={config.focus_topics}
                    onChange={e => updateConfig("focus_topics", e.target.value)}
                    placeholder="e.g. sorting algorithms, binary trees, recursion"
                    className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  />
                </div>
              </div>
            </div>

            {/* ── Summary + Generate button ── */}
            <div className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="font-semibold text-gray-900 mb-4">3. Review & Generate</h2>
              <div className="flex flex-wrap gap-2 mb-6">
                <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm">{config.num_questions} questions</span>
                <span className={`px-3 py-1 rounded-full text-sm capitalize ${difficultyColor[config.difficulty]}`}>{config.difficulty}</span>
                <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm capitalize">{config.question_types === "mcq" ? "MCQ only" : config.question_types === "true_false" ? "True/False" : config.question_types === "short" ? "Short answer" : "Mixed types"}</span>
                <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm">{config.time_limit} min</span>
                {inputMode === "file" && file && <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm">📄 {file.name}</span>}
                {inputMode === "text" && syllabusText.length > 0 && <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm">✏️ {syllabusText.length} chars pasted</span>}
              </div>
              <button
                onClick={handleGenerate}
                className="w-full flex items-center justify-center gap-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold py-4 rounded-xl text-base transition-all"
              >
                <SparkIcon />
                Generate Exam with AI
              </button>
              <p className="text-center text-xs text-gray-400 mt-3">Powered by Google Gemini · Free · ~10–20 seconds</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
