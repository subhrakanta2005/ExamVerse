import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "../../services/api";
import clsx from "clsx";

// ── Timer ─────────────────────────────────────────────────────────────────────
function Timer({ totalSeconds, onExpire }) {
  const [remaining, setRemaining] = useState(totalSeconds);
  useEffect(() => {
    if (remaining <= 0) { onExpire(); return; }
    const t = setTimeout(() => setRemaining(r => r - 1), 1000);
    return () => clearTimeout(t);
  }, [remaining, onExpire]);
  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const critical = remaining < 300;
  return (
    <div className={clsx(
      "flex items-center gap-2 px-4 py-2 rounded-xl font-mono font-bold text-lg",
      critical
        ? "bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse"
        : "bg-slate-800 text-white"
    )}>
      <span>⏱</span>
      {String(mins).padStart(2, "0")}:{String(secs).padStart(2, "0")}
    </div>
  );
}

// ── QuestionView ──────────────────────────────────────────────────────────────
function QuestionView({ question, selectedId, onSelect }) {
  if (!question) return null;
  const { question_type, text, options, marks } = question;
  const isMcq = ["mcq_single", "mcq", "mcq_multiple", "mcq_multi", "true_false"].includes(question_type);

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 mb-3">
        <span className="badge-blue">{marks} mark{marks !== 1 ? "s" : ""}</span>
        <span className="badge-gray text-xs">{question_type.replace(/_/g, " ").toUpperCase()}</span>
      </div>
      <p className="text-white text-lg leading-relaxed">{text}</p>

      {isMcq && (
        <div className="space-y-3 mt-4">
          {options?.map((opt) => (
            <button
              key={opt.id ?? opt.text}
              onClick={() => onSelect(opt)}
              className={clsx(
                "w-full text-left px-5 py-4 rounded-xl border text-sm transition-all duration-150",
                selectedId === (opt.id ?? opt.text)
                  ? "bg-brand-600/20 border-brand-500 text-white"
                  : "bg-slate-800/40 border-slate-700 text-slate-300 hover:border-slate-600 hover:bg-slate-800/60"
              )}
            >
              <span className={clsx(
                "inline-flex w-5 h-5 rounded-full border mr-3 items-center justify-center text-xs flex-shrink-0",
                selectedId === (opt.id ?? opt.text) ? "border-brand-400 bg-brand-500" : "border-slate-600"
              )}>
                {selectedId === (opt.id ?? opt.text) && "✓"}
              </span>
              {opt.text}
            </button>
          ))}
        </div>
      )}

      {(question_type === "short_answer" || question_type === "fill_blank") && (
        <input
          type="text"
          className="input-field mt-4"
          placeholder="Type your answer…"
          value={selectedId || ""}
          onChange={e => onSelect({ text: e.target.value, id: e.target.value })}
        />
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function SyllabusExamPage() {
  const location = useLocation();
  const navigate = useNavigate();

  // Load exam from sessionStorage (written by SyllabusUpload) or location.state
  const _stored = (() => {
    try { return JSON.parse(sessionStorage.getItem("generatedExam") || "null"); } catch { return null; }
  })();
  const exam = location.state?.exam ?? _stored;

  const [sessionId,    setSessionId]    = useState(null);
  const [questions,    setQuestions]    = useState([]);
  const [currentIdx,   setCurrentIdx]   = useState(0);
  const [selections,   setSelections]   = useState({}); // idx -> { optId, optText }
  const [markedReview, setMarkedReview] = useState(new Set());
  const [submitted,    setSubmitted]    = useState({}); // idx -> feedback
  const [loading,      setLoading]      = useState(true);
  const [submitting,   setSubmitting]   = useState(false);
  const [showConfirm,  setShowConfirm]  = useState(false);
  const [tabWarning,   setTabWarning]   = useState(false);
  const [score,        setScore]        = useState({ correct: 0, total: 0 });

  // Redirect if no exam data
  useEffect(() => {
    if (!exam) { navigate("/dashboard"); return; }

    // Start evaluation session
    api.post("/api/evaluation/start", { exam })
      .then(r => {
        setSessionId(r.data.session_id);
        const flat = (exam.sections || []).flatMap(s => s.questions || []);
        setQuestions(flat);
        setScore({ correct: 0, total: flat.length });
      })
      .catch(() => {
        // Fallback: run without server session (local only)
        const flat = (exam.sections || []).flatMap(s => s.questions || []);
        setQuestions(flat);
        setScore({ correct: 0, total: flat.length });
        setSessionId("local");
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  // Tab switch detection
  useEffect(() => {
    const handler = () => { if (document.hidden) setTabWarning(true); };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, []);

  const currentQ = questions[currentIdx];

  const handleSelect = useCallback((opt) => {
    setSelections(prev => ({ ...prev, [currentIdx]: { optId: opt.id ?? opt.text, optText: opt.text } }));
  }, [currentIdx]);

  const toggleReview = () => {
    setMarkedReview(prev => {
      const next = new Set(prev);
      next.has(currentIdx) ? next.delete(currentIdx) : next.add(currentIdx);
      return next;
    });
  };

  const getStatus = (i) => {
    const hasAnswer = selections[i] !== undefined;
    const isReview  = markedReview.has(i);
    if (isReview && hasAnswer) return "answered-review";
    if (isReview)   return "review";
    if (hasAnswer)  return "answered";
    return "unanswered";
  };

  const answeredCount = Object.keys(selections).length;

  const handleFinish = async (auto = false) => {
    setSubmitting(true);
    try {
      if (sessionId && sessionId !== "local") {
        // Submit all answers at once
        const answers = questions.map((q, i) => ({
          question_idx: i,
          answer: selections[i]?.optText ?? "",
        }));
        const res = await api.post("/api/evaluation/finish", {
          session_id: sessionId,
          answers,
        });
        sessionStorage.removeItem("generatedExam");
        navigate("/exam/result", { state: { result: res.data, exam } });
      } else {
        // Local scoring fallback
        let correct = 0;
        questions.forEach((q, i) => {
          const sel = selections[i]?.optText;
          const correctOpt = q.options?.find(o => o.is_correct);
          if (sel && correctOpt && sel === correctOpt.text) correct++;
        });
        sessionStorage.removeItem("generatedExam");
        navigate("/exam/result", {
          state: {
            result: {
              score: correct,
              total: questions.length,
              percentage: Math.round((correct / questions.length) * 100),
            },
            exam,
          }
        });
      }
    } catch (err) {
      console.error(err);
      // Navigate anyway with local score
      let correct = 0;
      questions.forEach((q, i) => {
        const sel = selections[i]?.optText;
        const correctOpt = q.options?.find(o => o.is_correct);
        if (sel && correctOpt && sel === correctOpt.text) correct++;
      });
      sessionStorage.removeItem("generatedExam");
      navigate("/exam/result", {
        state: {
          result: {
            score: correct,
            total: questions.length,
            percentage: Math.round((correct / questions.length) * 100),
          },
          exam,
        }
      });
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-slate-400">Loading exam…</p>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">

      {/* Tab warning */}
      {tabWarning && (
        <div className="bg-red-500/90 text-white px-6 py-3 flex items-center justify-between text-sm font-medium">
          <span>⚠️ Tab switch detected! This may be recorded.</span>
          <button onClick={() => setTabWarning(false)} className="hover:text-red-200">✕</button>
        </div>
      )}

      {/* Header */}
      <header className="sticky top-0 z-30 bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center gap-4">
        <div className="flex-1">
          <p className="font-display font-bold text-white">{exam?.title || "Practice Exam"}</p>
          <p className="text-xs text-slate-500">{answeredCount}/{questions.length} answered</p>
        </div>
        {exam?.duration_minutes && (
          <Timer
            totalSeconds={exam.duration_minutes * 60}
            onExpire={() => handleFinish(true)}
          />
        )}
        <button
          onClick={() => setShowConfirm(true)}
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
                Question {currentIdx + 1} of {questions.length}
              </span>
              <button
                onClick={toggleReview}
                className={clsx(
                  "text-sm px-4 py-1.5 rounded-lg border transition-all",
                  markedReview.has(currentIdx)
                    ? "bg-amber-500/20 border-amber-500/50 text-amber-400"
                    : "border-slate-700 text-slate-500 hover:text-slate-300"
                )}
              >
                {markedReview.has(currentIdx) ? "★ Marked" : "☆ Mark for review"}
              </button>
            </div>

            <QuestionView
              question={currentQ}
              selectedId={selections[currentIdx]?.optId}
              onSelect={handleSelect}
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
                disabled={currentIdx === questions.length - 1}
                onClick={() => setCurrentIdx(i => i + 1)}
              >
                Next →
              </button>
            </div>
          </div>
        </main>

        {/* Question palette sidebar */}
        <aside className="hidden lg:flex w-72 border-l border-slate-800 p-5 flex-col gap-4">
          <p className="text-sm font-semibold text-slate-400">Question Palette</p>

          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              { color: "bg-emerald-500", label: "Answered" },
              { color: "bg-slate-700",   label: "Unanswered" },
              { color: "bg-amber-500",   label: "Marked" },
              { color: "bg-brand-500",   label: "Current" },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5 text-slate-500">
                <div className={`w-3 h-3 rounded ${color}`} />
                {label}
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2 overflow-y-auto max-h-[60vh]">
            {questions.map((_, i) => {
              const status = getStatus(i);
              return (
                <button
                  key={i}
                  onClick={() => setCurrentIdx(i)}
                  className={clsx(
                    "w-9 h-9 rounded-lg text-xs font-mono font-bold transition-all border",
                    i === currentIdx && "ring-2 ring-brand-400",
                    status === "answered"        && "bg-emerald-600/30 border-emerald-500/50 text-emerald-400",
                    status === "review"          && "bg-amber-600/30 border-amber-500/50 text-amber-400",
                    status === "answered-review" && "bg-brand-600/30 border-brand-500/50 text-brand-400",
                    status === "unanswered"      && "bg-slate-800 border-slate-700 text-slate-400 hover:border-slate-600",
                  )}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>

          <div className="mt-auto space-y-2 text-xs text-slate-500 border-t border-slate-800 pt-4">
            <div className="flex justify-between">
              <span>Answered</span>
              <span className="text-emerald-400 font-semibold">{answeredCount}</span>
            </div>
            <div className="flex justify-between">
              <span>Unanswered</span>
              <span className="text-slate-400 font-semibold">{questions.length - answeredCount}</span>
            </div>
            <div className="flex justify-between">
              <span>Marked</span>
              <span className="text-amber-400 font-semibold">{markedReview.size}</span>
            </div>
          </div>
        </aside>
      </div>

      {/* Submit confirmation modal */}
      {showConfirm && (
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
                <p className="font-bold text-slate-400">{questions.length - answeredCount}</p>
                <p className="text-slate-500 text-xs">Unanswered</p>
              </div>
              <div className="bg-slate-800/60 rounded-xl p-3">
                <p className="font-bold text-amber-400">{markedReview.size}</p>
                <p className="text-slate-500 text-xs">Marked</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setShowConfirm(false)}>
                Continue Exam
              </button>
              <button
                className="btn-primary flex-1"
                onClick={() => { setShowConfirm(false); handleFinish(false); }}
                disabled={submitting}
              >
                {submitting ? "Submitting…" : "Submit Now"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
