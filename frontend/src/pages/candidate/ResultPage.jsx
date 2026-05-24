import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { resultAPI } from "../../services/api";

// ── Icons ─────────────────────────────────────────────────────────────────────
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
  </svg>
);
const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className="w-4 h-4">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);
const TrophyIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10">
    <path fillRule="evenodd" d="M5.166 2.621v.858c-1.035.148-2.059.33-3.071.543a.75.75 0 00-.584.859 6.753 6.753 0 006.138 5.6 6.73 6.73 0 002.743 1.346A6.707 6.707 0 019.279 15H8.54c-1.036 0-1.875.84-1.875 1.875V19.5h-.75a2.25 2.25 0 00-2.25 2.25c0 .414.336.75.75.75h15a.75.75 0 00.75-.75 2.25 2.25 0 00-2.25-2.25h-.75v-2.625c0-1.036-.84-1.875-1.875-1.875h-.739a6.706 6.706 0 01-1.112-3.173 6.73 6.73 0 002.743-1.347 6.753 6.753 0 006.139-5.6.75.75 0 00-.585-.858 47.077 47.077 0 00-3.07-.543V2.62a.75.75 0 00-.658-.744 49.798 49.798 0 00-6.093-.377 49.798 49.798 0 00-6.093.377.75.75 0 00-.657.744zm0 2.629c0 1.196.312 2.32.857 3.294A5.266 5.266 0 013.16 5.337a45.6 45.6 0 012.006-.343v.256zm13.5 0v-.256c.674.1 1.343.214 2.006.343a5.265 5.265 0 01-2.863 3.207 6.72 6.72 0 00.857-3.294z" clipRule="evenodd" />
  </svg>
);
const HomeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-5 h-5">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
  </svg>
);

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatTime(secs) {
  if (!secs) return "—";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/**
 * Normalize backend result shape → UI shape.
 * Backend:  { obtained_marks, total_marks, percentage, is_passed, correct_count,
 *             incorrect_count, unattempted_count, section_scores, exam_title, ... }
 * UI needs: { score, total_marks, percentage, passed, questions_correct, ... }
 */
function normalizeResult(raw) {
  // Already normalized (came from old AI evaluation endpoint)
  if (raw.score !== undefined && raw.passed !== undefined) return raw;

  const total     = raw.total_marks    ?? 0;
  const obtained  = raw.obtained_marks ?? 0;
  const pct       = raw.percentage     ?? (total > 0 ? Math.round((obtained / total) * 100) : 0);
  const passed    = raw.is_passed      ?? (pct >= (raw.pass_percentage ?? 40));

  // Build topic_breakdown from section_scores if available
  const topic_breakdown = raw.section_scores
    ? Object.entries(raw.section_scores).map(([, sec]) => ({
        topic: sec.title || "Section",
        correct: "—",
        questions_seen: "—",
        accuracy_pct: sec.total > 0 ? Math.round((sec.obtained / sec.total) * 100) : 0,
      }))
    : [];

  return {
    score:               obtained,
    total_marks:         total,
    percentage:          Math.round(pct),
    passed,
    pass_mark:           raw.pass_mark ?? Math.round(total * ((raw.pass_percentage ?? 40) / 100)),
    pass_percentage:     raw.pass_percentage ?? 40,
    time_taken_seconds:  raw.time_taken_seconds ?? null,
    questions_total:     (raw.correct_count ?? 0) + (raw.incorrect_count ?? 0) + (raw.unattempted_count ?? 0),
    questions_answered:  (raw.correct_count ?? 0) + (raw.incorrect_count ?? 0),
    questions_correct:   raw.correct_count   ?? 0,
    questions_skipped:   raw.unattempted_count ?? 0,
    topic_breakdown,
    weak_topics:         [],
    question_results:    [],
    performance_summary: passed
      ? `You scored ${Math.round(pct)}% and passed the exam.`
      : `You scored ${Math.round(pct)}%. The pass mark was ${raw.pass_percentage ?? 40}%.`,
    candidate_name: raw.candidate_name ?? null,
    exam_title:     raw.exam_title     ?? (raw.exam_id ? `Exam #${raw.exam_id}` : null),
  };
}

// ── Sub-components ────────────────────────────────────────────────────────────
function ScoreDial({ percentage, passed }) {
  const r    = 54;
  const circ = 2 * Math.PI * r;
  const fill = (percentage / 100) * circ;
  const color = passed ? "#10b981" : percentage >= 35 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative w-40 h-40 mx-auto">
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#e2e8f0" strokeWidth="10" />
        <circle
          cx="60" cy="60" r={r} fill="none"
          stroke={color} strokeWidth="10"
          strokeDasharray={`${fill} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-slate-800">{percentage}%</span>
        <span className={`text-xs font-semibold mt-0.5 ${passed ? "text-emerald-600" : "text-red-500"}`}>
          {passed ? "PASSED" : "FAILED"}
        </span>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, color = "text-slate-800" }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      <p className="text-xs font-medium text-slate-500 mt-1">{label}</p>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
export default function ResultPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { attemptId } = useParams();   // present when route is /result/:attemptId

  const [rawResult, setRawResult] = useState(
    // Prefer state passed from submit flow; fall back to API fetch
    location.state?.result ?? null
  );
  const [loading, setLoading] = useState(!rawResult);
  const [fetchError, setFetchError] = useState("");

  // Fetch from API if we don't have state (e.g. direct URL or page refresh)
  useEffect(() => {
    if (rawResult) return;
    const resultId = attemptId;
    if (!resultId) {
      setFetchError("No result ID provided.");
      setLoading(false);
      return;
    }
    resultAPI.getByAttempt(resultId)
      .then(r => setRawResult(r.data))
      .catch(() => setFetchError("Result not found, or it hasn't been published yet."))
      .finally(() => setLoading(false));
  }, [attemptId]); // eslint-disable-line

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (!rawResult) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-center">
          <p className="text-slate-500 mb-2">{fetchError || "No result data found."}</p>
          <p className="text-slate-400 text-sm mb-4">
            The result may not be published yet. Check back after the admin publishes it.
          </p>
          <button
            onClick={() => navigate("/")}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  // Normalize backend shape → UI shape
  const result = normalizeResult(rawResult);

  const {
    score, total_marks, percentage, passed, pass_mark, pass_percentage,
    time_taken_seconds, questions_total, questions_answered,
    questions_correct, questions_skipped,
    topic_breakdown = [], weak_topics = [],
    question_results = [], performance_summary,
    candidate_name, exam_title,
  } = result;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-3xl mx-auto px-4 py-10 space-y-6">

        {/* ── Hero card ────────────────────────────────────────────────── */}
        <div className={`rounded-2xl p-8 text-center shadow-sm border
          ${passed ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`}>

          <div className={`inline-flex p-3 rounded-full mb-4
            ${passed ? "bg-emerald-100 text-emerald-600" : "bg-red-100 text-red-500"}`}>
            {passed ? <TrophyIcon /> : <XIcon />}
          </div>

          <h1 className="text-2xl font-bold text-slate-800 mb-1">
            {passed ? "Congratulations!" : "Better luck next time"}
          </h1>
          {candidate_name && candidate_name !== "Anonymous" && (
            <p className="text-slate-500 text-sm mb-1">{candidate_name}</p>
          )}
          {exam_title && (
            <p className="text-slate-500 text-sm mb-6">{exam_title}</p>
          )}

          <ScoreDial percentage={percentage} passed={passed} />

          {performance_summary && (
            <p className="mt-4 text-slate-600 text-sm max-w-md mx-auto">
              {performance_summary}
            </p>
          )}

          <p className="mt-2 text-xs text-slate-400">
            Pass mark: {pass_mark}/{total_marks} ({pass_percentage}%)
          </p>
        </div>

        {/* ── Stat cards ───────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Score"
            value={`${score}/${total_marks}`}
            color={passed ? "text-emerald-600" : "text-red-500"}
          />
          <StatCard
            label="Correct"
            value={questions_correct}
            sub={`of ${questions_answered} answered`}
            color="text-emerald-600"
          />
          <StatCard
            label="Skipped"
            value={questions_skipped}
            sub={`of ${questions_total} total`}
            color={questions_skipped > 0 ? "text-amber-500" : "text-slate-800"}
          />
          <StatCard
            label="Time Taken"
            value={formatTime(time_taken_seconds)}
          />
        </div>

        {/* ── Section breakdown ─────────────────────────────────────────── */}
        {topic_breakdown.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-base font-semibold text-slate-800 mb-4">Section Breakdown</h2>
            <div className="space-y-4">
              {topic_breakdown.map((t, i) => {
                const isWeak = weak_topics.includes(t.topic);
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-700">{t.topic}</span>
                        {isWeak && (
                          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
                            Needs review
                          </span>
                        )}
                      </div>
                      <span className="text-sm font-semibold text-slate-600">
                        {t.accuracy_pct}%
                      </span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700
                          ${t.accuracy_pct >= 70 ? "bg-emerald-500" :
                            t.accuracy_pct >= 40 ? "bg-amber-400" : "bg-red-400"}`}
                        style={{ width: `${t.accuracy_pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Question-by-question review ───────────────────────────────── */}
        {question_results.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-base font-semibold text-slate-800 mb-4">Question Review</h2>
            <div className="space-y-3">
              {question_results.map((qr, i) => (
                <div
                  key={i}
                  className={`rounded-xl p-4 border
                    ${qr.skipped         ? "bg-slate-50  border-slate-200" :
                      qr.is_correct      ? "bg-emerald-50 border-emerald-100" :
                                           "bg-red-50    border-red-100"}`}
                >
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center
                      text-white text-xs font-bold
                      ${qr.skipped    ? "bg-slate-300" :
                        qr.is_correct ? "bg-emerald-500" : "bg-red-400"}`}>
                      {qr.skipped ? "–" : qr.is_correct ? <CheckIcon /> : <XIcon />}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xs text-slate-500">Q{i + 1}</span>
                        {qr.section && (
                          <span className="text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                            {qr.section}
                          </span>
                        )}
                        <span className="text-xs text-slate-400 ml-auto">
                          {qr.marks_awarded}/{qr.marks_possible} marks
                        </span>
                      </div>
                      <p className="text-sm text-slate-700 font-medium mb-2">{qr.question}</p>
                      {qr.skipped ? (
                        <p className="text-xs text-slate-400 italic">Not answered</p>
                      ) : (
                        <div className="text-xs space-y-0.5">
                          <p>
                            <span className="text-slate-500">Your answer: </span>
                            <span className={qr.is_correct ? "text-emerald-700 font-medium" : "text-red-600 font-medium"}>
                              {qr.given_answer}
                            </span>
                          </p>
                          {!qr.is_correct && (
                            <p>
                              <span className="text-slate-500">Correct: </span>
                              <span className="text-emerald-700 font-medium">{qr.correct_answer}</span>
                            </p>
                          )}
                          {qr.explanation && (
                            <p className="text-slate-500 mt-1 italic">{qr.explanation}</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Actions ──────────────────────────────────────────────────── */}
        <div className="flex gap-3 justify-center pb-6">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-indigo-600
              text-white font-medium hover:bg-indigo-700 transition-colors shadow-sm"
          >
            <HomeIcon /> Go Home
          </button>
          <button
            onClick={() => navigate("/history")}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white
              border border-slate-200 text-slate-600 font-medium
              hover:bg-slate-50 transition-colors shadow-sm"
          >
            My Results
          </button>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white
              border border-slate-200 text-slate-600 font-medium
              hover:bg-slate-50 transition-colors shadow-sm"
          >
            Print
          </button>
        </div>

      </div>
    </div>
  );
}
