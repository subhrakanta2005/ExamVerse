import { useState, useEffect, useRef, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import api from "../../services/api";

// ── Icons ─────────────────────────────────────────────────────────────────────
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
  </svg>
);
const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);
const ArrowRightIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
  </svg>
);
const ClockIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);
const FlagIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18m0-16.5l6-1.5 6 1.5 6-1.5V18l-6 1.5-6-1.5-6 1.5" />
  </svg>
);

// ── Helpers ───────────────────────────────────────────────────────────────────
const difficultyColor = {
  easy:   "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100  text-amber-700",
  hard:   "bg-red-100    text-red-700",
};

const typeLabel = {
  mcq:          "Multiple Choice",
  true_false:   "True / False",
  short_answer: "Short Answer",
};

function formatTime(secs) {
  const m = Math.floor(secs / 60).toString().padStart(2, "0");
  const s = (secs % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

// Flatten exam sections → flat question list with section name
function flattenQuestions(exam) {
  const flat = [];
  for (const sec of exam.sections || []) {
    for (const q of sec.questions || []) {
      flat.push({ ...q, _section: sec.title });
    }
  }
  return flat;
}

// ══════════════════════════════════════════════════════════════════════════════
export default function ExamPage() {
  const location = useLocation();
  const navigate  = useNavigate();

  // Exam + session passed via router state from SyllabusUpload or exam list
  const { exam, sessionId: existingSessionId, candidateName } =
    location.state || {};

  const [sessionId,    setSessionId]    = useState(existingSessionId || null);
  const [questions,    setQuestions]    = useState([]);
  const [currentIdx,  setCurrentIdx]   = useState(0);
  const [answer,      setAnswer]       = useState("");
  const [feedback,    setFeedback]     = useState(null);   // result of /answer
  const [progress,    setProgress]     = useState(null);
  const [answered,    setAnswered]     = useState({});     // idx → feedback
  const [timeLeft,    setTimeLeft]     = useState(null);
  const [loading,     setLoading]      = useState(false);
  const [finishing,   setFinishing]    = useState(false);
  const [error,       setError]        = useState("");
  const timerRef = useRef(null);

  // ── Start session on mount ─────────────────────────────────────────────────
  useEffect(() => {
    if (!exam) { navigate("/"); return; }

    const qs = flattenQuestions(exam);
    setQuestions(qs);

    async function startSession() {
      if (existingSessionId) {
        setTimeLeft((exam.duration_minutes || 30) * 60);
        return;
      }
      try {
        const res = await api.post("/evaluation/start", {
          exam,
          candidate_name: candidateName || "Candidate",
        });
        setSessionId(res.data.session_id);
        setTimeLeft((res.data.duration_minutes || 30) * 60);
      } catch (e) {
        setError("Failed to start session. Please try again.");
      }
    }
    startSession();
  }, []);  // eslint-disable-line

  // ── Countdown timer ────────────────────────────────────────────────────────
  useEffect(() => {
    if (timeLeft === null) return;
    if (timeLeft <= 0) { handleFinish(); return; }
    timerRef.current = setTimeout(() => setTimeLeft(t => t - 1), 1000);
    return () => clearTimeout(timerRef.current);
  }, [timeLeft]);  // eslint-disable-line

  const currentQ = questions[currentIdx];

  // ── Submit answer ──────────────────────────────────────────────────────────
  const handleSubmitAnswer = useCallback(async (selectedAnswer) => {
    if (!sessionId || !currentQ) return;
    const ans = selectedAnswer ?? answer;
    if (!ans.trim()) return;

    setLoading(true);
    setError("");
    try {
      const res = await api.post("/evaluation/answer", {
        session_id:   sessionId,
        question_idx: currentIdx,
        answer:       ans,
      });
      const fb = res.data;
      setFeedback(fb);
      setProgress(fb.progress);
      setAnswered(prev => ({ ...prev, [currentIdx]: fb }));
    } catch (e) {
      setError("Failed to submit answer. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [sessionId, currentQ, currentIdx, answer]);

  // ── Next question ──────────────────────────────────────────────────────────
  const handleNext = () => {
    setFeedback(null);
    setAnswer("");
    if (currentIdx + 1 >= questions.length) {
      handleFinish();
    } else {
      setCurrentIdx(i => i + 1);
    }
  };

  // ── Finish exam ────────────────────────────────────────────────────────────
  const handleFinish = useCallback(async () => {
    if (!sessionId || finishing) return;
    clearTimeout(timerRef.current);
    setFinishing(true);
    try {
      const res = await api.post(`/evaluation/finish/${sessionId}`);
      navigate("/exam/result", { state: { result: res.data } });
    } catch (e) {
      setError("Failed to submit exam. Please try again.");
      setFinishing(false);
    }
  }, [sessionId, finishing, navigate]);

  // ── MCQ option click ───────────────────────────────────────────────────────
  const handleOptionClick = (optText) => {
    if (feedback) return;   // already answered
    setAnswer(optText);
    handleSubmitAnswer(optText);
  };

  if (!exam || !currentQ) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500">{error || "Loading exam…"}</p>
      </div>
    );
  }

  const isAnswered    = !!feedback;
  const isLastQ       = currentIdx + 1 >= questions.length;
  const answeredCount = Object.keys(answered).length;
  const pctDone       = Math.round((answeredCount / questions.length) * 100);
  const timerWarning  = timeLeft !== null && timeLeft < 120;

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">

      {/* ── Top bar ──────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between gap-4">

          {/* Progress bar */}
          <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-slate-500 font-medium">
                Question {currentIdx + 1} of {questions.length}
              </span>
              <span className="text-xs text-slate-500">{pctDone}% done</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                style={{ width: `${pctDone}%` }}
              />
            </div>
          </div>

          {/* Score so far */}
          {progress && (
            <div className="text-center hidden sm:block">
              <p className="text-xs text-slate-400">Score</p>
              <p className="text-sm font-semibold text-slate-700">
                {progress.score_so_far}/{progress.max_so_far}
              </p>
            </div>
          )}

          {/* Timer */}
          {timeLeft !== null && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-mono font-semibold
              ${timerWarning
                ? "bg-red-50 text-red-600 animate-pulse"
                : "bg-slate-100 text-slate-600"
              }`}>
              <ClockIcon />
              {formatTime(timeLeft)}
            </div>
          )}

          {/* Finish early */}
          <button
            onClick={handleFinish}
            disabled={finishing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium
              text-slate-500 hover:text-red-600 hover:bg-red-50 transition-colors"
          >
            <FlagIcon />
            <span className="hidden sm:inline">Finish</span>
          </button>
        </div>
      </header>

      {/* ── Question card ─────────────────────────────────────────────────── */}
      <main className="flex-1 flex items-start justify-center px-4 py-8">
        <div className="w-full max-w-3xl">

          {/* Section + badges */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-full">
              {currentQ._section}
            </span>
            <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${difficultyColor[currentQ.difficulty] || "bg-slate-100 text-slate-600"}`}>
              {currentQ.difficulty}
            </span>
            <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full">
              {typeLabel[currentQ.question_type] || currentQ.question_type}
            </span>
            <span className="text-xs font-medium text-slate-500 ml-auto">
              {currentQ.marks} {currentQ.marks === 1 ? "mark" : "marks"}
            </span>
          </div>

          {/* Question text */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-4">
            <p className="text-lg font-medium text-slate-800 leading-relaxed">
              {currentQ.text}
            </p>
          </div>

          {/* ── MCQ options ────────────────────────────────────────────── */}
          {currentQ.question_type === "mcq" && (
            <div className="space-y-3">
              {currentQ.options?.map((opt, i) => {
                let style = "bg-white border-slate-200 text-slate-700 hover:border-indigo-300 hover:bg-indigo-50";
                if (isAnswered) {
                  if (opt.is_correct)
                    style = "bg-emerald-50 border-emerald-400 text-emerald-800";
                  else if (opt.text === answer && !opt.is_correct)
                    style = "bg-red-50 border-red-400 text-red-800";
                  else
                    style = "bg-white border-slate-100 text-slate-400 opacity-60";
                }
                return (
                  <button
                    key={i}
                    onClick={() => handleOptionClick(opt.text)}
                    disabled={isAnswered || loading}
                    className={`w-full flex items-center gap-4 px-5 py-4 rounded-xl border-2
                      text-left transition-all duration-150 font-medium ${style}
                      disabled:cursor-default`}
                  >
                    <span className={`w-7 h-7 rounded-full border-2 flex items-center justify-center
                      text-xs font-bold flex-shrink-0
                      ${isAnswered && opt.is_correct ? "border-emerald-500 bg-emerald-500 text-white" : "border-current"}`}>
                      {isAnswered && opt.is_correct ? <CheckIcon /> :
                       isAnswered && opt.text === answer && !opt.is_correct ? <XIcon /> :
                       String.fromCharCode(65 + i)}
                    </span>
                    {opt.text}
                  </button>
                );
              })}
            </div>
          )}

          {/* ── True / False ─────────────────────────────────────────── */}
          {currentQ.question_type === "true_false" && (
            <div className="grid grid-cols-2 gap-3">
              {["True", "False"].map((val) => {
                const isCorrectOpt = feedback?.correct_answer?.toLowerCase() === val.toLowerCase();
                const isChosen     = answer === val;
                let style = "bg-white border-slate-200 text-slate-700 hover:border-indigo-300 hover:bg-indigo-50";
                if (isAnswered) {
                  if (isCorrectOpt)      style = "bg-emerald-50 border-emerald-400 text-emerald-800";
                  else if (isChosen)     style = "bg-red-50 border-red-400 text-red-800";
                  else                   style = "bg-white border-slate-100 text-slate-400 opacity-60";
                }
                return (
                  <button
                    key={val}
                    onClick={() => { setAnswer(val); handleSubmitAnswer(val); }}
                    disabled={isAnswered || loading}
                    className={`flex items-center justify-center gap-2 py-5 rounded-xl border-2
                      font-semibold text-lg transition-all duration-150 ${style}
                      disabled:cursor-default`}
                  >
                    {isAnswered && isCorrectOpt && <CheckIcon />}
                    {isAnswered && isChosen && !isCorrectOpt && <XIcon />}
                    {val}
                  </button>
                );
              })}
            </div>
          )}

          {/* ── Short answer ──────────────────────────────────────────── */}
          {currentQ.question_type === "short_answer" && !isAnswered && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <input
                type="text"
                value={answer}
                onChange={e => setAnswer(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSubmitAnswer()}
                placeholder="Type your answer and press Enter…"
                className="w-full text-slate-800 placeholder-slate-300 text-base
                  outline-none border-none focus:ring-0 bg-transparent"
                autoFocus
              />
              <div className="flex justify-end mt-3">
                <button
                  onClick={() => handleSubmitAnswer()}
                  disabled={!answer.trim() || loading}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-indigo-600
                    text-white font-medium text-sm hover:bg-indigo-700 transition-colors
                    disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {loading ? "Checking…" : "Submit"} <ArrowRightIcon />
                </button>
              </div>
            </div>
          )}

          {/* ── Feedback banner ───────────────────────────────────────── */}
          {feedback && (
            <div className={`mt-4 rounded-xl p-4 border
              ${feedback.is_correct
                ? "bg-emerald-50 border-emerald-200"
                : "bg-red-50 border-red-200"}`}>
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center
                  ${feedback.is_correct ? "bg-emerald-500" : "bg-red-500"} text-white`}>
                  {feedback.is_correct ? <CheckIcon /> : <XIcon />}
                </span>
                <div className="flex-1 min-w-0">
                  <p className={`font-semibold mb-1
                    ${feedback.is_correct ? "text-emerald-800" : "text-red-800"}`}>
                    {feedback.is_correct
                      ? `Correct! +${feedback.marks_awarded} mark${feedback.marks_awarded !== 1 ? "s" : ""}`
                      : `Incorrect — 0 / ${feedback.marks_possible} marks`}
                  </p>
                  {!feedback.is_correct && (
                    <p className="text-sm text-red-700 mb-1">
                      Correct answer: <span className="font-medium">{feedback.correct_answer}</span>
                    </p>
                  )}
                  {feedback.explanation && (
                    <p className="text-sm text-slate-600">{feedback.explanation}</p>
                  )}
                </div>
              </div>

              {/* Next / Finish button */}
              <div className="flex justify-end mt-4">
                <button
                  onClick={isLastQ ? handleFinish : handleNext}
                  disabled={finishing}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-lg bg-indigo-600
                    text-white font-medium hover:bg-indigo-700 transition-colors
                    disabled:opacity-50"
                >
                  {finishing ? "Submitting…" :
                   isLastQ   ? "Finish Exam 🎉" : "Next Question"}
                  {!isLastQ && !finishing && <ArrowRightIcon />}
                </button>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="mt-3 text-sm text-red-600 text-center">{error}</p>
          )}

          {/* ── Question navigator dots ───────────────────────────────── */}
          <div className="mt-8 flex flex-wrap gap-2 justify-center">
            {questions.map((_, i) => {
              const isDone    = answered[i] !== undefined;
              const isCurrent = i === currentIdx;
              return (
                <div
                  key={i}
                  title={`Q${i + 1}`}
                  className={`w-7 h-7 rounded-full text-xs font-semibold flex items-center justify-center
                    transition-all
                    ${isCurrent  ? "bg-indigo-600 text-white ring-2 ring-indigo-300 ring-offset-1" :
                      isDone && answered[i]?.is_correct ? "bg-emerald-500 text-white" :
                      isDone     ? "bg-red-400 text-white" :
                                   "bg-slate-200 text-slate-500"}`}
                >
                  {i + 1}
                </div>
              );
            })}
          </div>

        </div>
      </main>
    </div>
  );
}
