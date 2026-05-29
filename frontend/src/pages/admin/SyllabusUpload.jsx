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

const typeMap = {
  mcq:          "mcq_single",
  mcq_single:   "mcq_single",
  mcq_multiple: "mcq_multiple",
  true_false:   "true_false",
  short_answer: "short_answer",
  fill_blank:   "fill_blank",
};

// ── Browser-side PDF text extraction (keeps Render memory under 200MB) ────────
async function extractTextFromPDF(file) {
  if (!window.pdfjsLib) {
    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js";
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    window.pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  }
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
  const maxPages = Math.min(pdf.numPages, 60);
  const pageTexts = [];
  for (let i = 1; i <= maxPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    pageTexts.push(content.items.map((item, idx) => {
        const next = content.items[idx + 1];
        // Insert a newline when the next item starts a new visual line (different Y position)
        const gap = next ? Math.abs((next.transform[5] || 0) - (item.transform[5] || 0)) : 0;
        return item.str + (gap > 2 ? "\n" : " ");
      }).join(""));
  }
  return pageTexts.join("\n");
}

// ══════════════════════════════════════════════════════════════════════════════
export default function SyllabusUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
// ══════════════════════════════════════════════════════════════════════════════
export default function SyllabusUpload() {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [syllabusText, setSyllabusText] = useState("");
  const [searchTopics, setSearchTopics] = useState("");
  const [inputMode, setInputMode] = useState("file");
  const [dragging, setDragging] = useState(false);

  const [config, setConfig] = useState({
    num_questions: 90,
    difficulty: "medium",
    question_types: "mixed",
    time_limit: 30,
    exam_title: "",
    focus_topics: "",
  });

  const [step, setStep] = useState("upload");
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
    if (f.size > 20 * 1024 * 1024) { setErrorMsg("File must be under 20 MB."); return; }
    setErrorMsg("");
    setFile(f);
  };

  const updateConfig = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

  // ── Generate ────────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (inputMode === "file" && !file) { setErrorMsg("Please upload a syllabus file."); return; }
    if (inputMode === "text" && syllabusText.trim().length < 50) { setErrorMsg("Please paste at least 50 characters."); return; }
    if (inputMode === "search" && searchTopics.trim().length < 3) { setErrorMsg("Please enter at least one topic to search."); return; }

    setStep("generating");
    setProgress(0);
    setErrorMsg("");

    // Cap at 92 so the bar visually reaches near-done but never freezes at 88
    const ticker = setInterval(() => {
      setProgress(p => p < 92 ? p + Math.random() * 5 : p);
    }, 800);

    try {
      let data;

      if (inputMode === "search") {
        // ── Search mode ──────────────────────────────────────────────────────
        // Backend expects topics as list[str], not a raw string
        const topicsArray = searchTopics
          .split(/[\n,]+/)
          .map(t => t.trim())
          .filter(Boolean);

        const res = await api.post("/api/syllabus/search-and-generate", {
          topics:         topicsArray,
          num_questions:  config.num_questions,
          difficulty:     config.difficulty,
          question_types: config.question_types,
          time_limit:     config.time_limit,
          exam_title:     config.exam_title  || null,
          focus_topics:   config.focus_topics || null,
          extra_context:  "",
        }, { timeout: 180000 });
        data = res.data;

      } else if (inputMode === "file" && file && (file.type === "application/pdf" || file.name.match(/\.pdf$/i))) {
        // ── PDF mode: extract text in browser, send as plain text ────────────
        setProgress(8);
        const extractedText = await extractTextFromPDF(file);
        const formData = new FormData();
        const blob = new Blob([extractedText], { type: "text/plain" });
        formData.append("file", blob, "syllabus.txt");
        formData.append("num_questions",  config.num_questions);
        formData.append("difficulty",     config.difficulty);
        formData.append("question_types", config.question_types);
        formData.append("time_limit",     config.time_limit);
        if (config.exam_title)   formData.append("exam_title",   config.exam_title);
        if (config.focus_topics) formData.append("focus_topics", config.focus_topics);
        const res = await api.post("/api/syllabus/upload-and-generate", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 180000,
        });
        data = res.data;

      } else {
        // ── DOCX / TXT / paste text mode ─────────────────────────────────────
        const formData = new FormData();
        if (inputMode === "file" && file) {
          formData.append("file", file);
        } else {
          const blob = new Blob([syllabusText], { type: "text/plain" });
          formData.append("file", blob, "syllabus.txt");
        }
        formData.append("num_questions",  config.num_questions);
        formData.append("difficulty",     config.difficulty);
        formData.append("question_types", config.question_types);
        formData.append("time_limit",     config.time_limit);
        if (config.exam_title)   formData.append("exam_title",   config.exam_title);
        if (config.focus_topics) formData.append("focus_topics", config.focus_topics);
if (config.focus_topics) formData.append("focus_topics", config.focus_topics);
        const res = await api.post("/api/syllabus/upload-and-generate", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 180000,
        });
        data = res.data;
      }

      clearInterval(ticker);
      setProgress(100);
      setResult(data);
      setStep("done");
    } catch (err) {
      clearInterval(ticker);
      setProgress(0);
      // FastAPI validation errors arrive as err.response.data.detail (array or string)
      const rawDetail = err?.response?.data?.detail;
      let msg = "Generation failed. Please try again.";
      if (typeof rawDetail === "string") {
        msg = rawDetail;
      } else if (Array.isArray(rawDetail)) {
        // Pydantic validation error — e.g. topics must be a list
        msg = rawDetail.map(e => e.msg || JSON.stringify(e)).join("; ");
      } else if (err?.message) {
        msg = err.message;
      }
      setErrorMsg(msg);
      setStep("error");
    }
  };

  // ── Import ──────────────────────────────────────────────────────────────────
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
    setConfig({ num_questions: 90, difficulty: "medium", question_types: "mixed", time_limit: 30, exam_title: "", focus_topics: "" });
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
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
          <button
            onClick={() => navigate("/admin")}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors border border-gray-200"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* IMPORTED */}
        {step === "imported" && (
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-600 px-8 py-10 text-white text-center">
              <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4"><CheckIcon /></div>
              <h2 className="text-2xl font-bold mb-1">Exam Saved to Database!</h2>
              <p className="text-emerald-100 text-sm">Live and visible to candidates immediately</p>
            </div>
            <div className="p-8 flex flex-col sm:flex-row gap-3">
              <button onClick={() => navigate(`/admin/exams/${importedExamId}/edit`)} className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-xl transition-colors">
                Edit Exam <ArrowRightIcon />
              </button>
              <button onClick={() => navigate("/admin/exams")} className="flex-1 flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 px-6 rounded-xl transition-colors">
                All Exams
              </button>
              <button onClick={reset} className="flex-1 flex items-center justify-center gap-2 border border-gray-200 hover:bg-gray-50 text-gray-600 font-semibold py-3 px-6 rounded-xl transition-colors">
                Generate Another
              </button>
            </div>
	< truncated lines 6441-6720 >
                </div>
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-gray-200 p-6">
              <h2 className="font-semibold text-gray-900 mb-4">3. Review & Generate</h2>
              <div className="flex flex-wrap gap-2 mb-6">
                <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm">{config.num_questions} questions</span>
                <span className={`px-3 py-1 rounded-full text-sm capitalize ${difficultyColor[config.difficulty]}`}>{config.difficulty}</span>
                <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm">{config.time_limit} min</span>
                {inputMode === "file" && file && <span className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm">📄 {file.name}</span>}
                {inputMode === "search" && searchTopics.trim() && <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">🔍 Web search</span>}
                {inputMode === "text" && syllabusText.trim() && <span className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm">📝 Pasted text</span>}
              </div>
              <button onClick={handleGenerate} className="w-full flex items-center justify-center gap-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold py-4 rounded-xl text-base transition-all">
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
