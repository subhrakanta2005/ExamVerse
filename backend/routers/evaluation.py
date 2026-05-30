"""
backend/routers/evaluation.py
==============================
In-memory evaluation engine for AI-generated (syllabus-based) exams.

Endpoints consumed by SyllabusExamPage.jsx and SyllabusResultPage.jsx:
  POST /api/evaluation/start
  POST /api/evaluation/answer
  POST /api/evaluation/finish/{session_id}

Session persistence note:
  Sessions live in _sessions (a plain dict). On Render free-tier dynos this
  dict is wiped on every restart/sleep cycle. The frontend must handle 404
  responses from /answer and /finish gracefully (the candidate's exam will
  be lost). A production fix is to back this with Redis — swap _sessions for
  a Redis client and serialise SessionState as JSON.

TTL cleanup:
  Sessions older than SESSION_TTL_SECONDS are evicted on each /start call
  to prevent unbounded memory growth during long-running dyno sessions.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import uuid
import time

router = APIRouter()

# Sessions older than 4 hours are considered expired and eligible for eviction
SESSION_TTL_SECONDS = 4 * 60 * 60  # 4 hours

# ── In-memory session store  {session_id: SessionState} ──────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}


def _evict_expired_sessions() -> None:
    """Remove sessions that have exceeded SESSION_TTL_SECONDS."""
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s.get("started_at", now) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)


# ── Request / response schemas ─────────────────────────────────────────────────

class StartRequest(BaseModel):
    exam: Dict[str, Any]
    candidate_name: Optional[str] = "Candidate"


class AnswerRequest(BaseModel):
    session_id: str
    question_idx: int
    answer: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _flatten_questions(exam: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten exam sections → ordered question list (mirrors frontend flattenQuestions)."""
    flat = []
    for sec in exam.get("sections", []):
        for q in sec.get("questions", []):
            flat.append({**q, "_section": sec.get("title", "General")})
    return flat


def _check_answer(question: Dict[str, Any], submitted: str) -> Dict[str, Any]:
    """
    Evaluate a submitted answer against a question dict.
    Returns dict with: is_correct, marks_awarded, marks_possible, correct_answer, explanation
    """
    q_type         = question.get("question_type", "mcq")
    marks_possible = float(question.get("marks", 1))
    explanation    = question.get("explanation", "")
    options        = question.get("options", [])

    correct_text = ""
    for opt in options:
        if opt.get("is_correct"):
            correct_text = opt.get("text", "")
            break

    if not correct_text:
        correct_text = question.get("correct_answer", "")

    submitted_norm = submitted.strip().lower()
    correct_norm   = correct_text.strip().lower()

    is_correct = submitted_norm == correct_norm

    if q_type == "true_false" and not is_correct:
        is_correct = submitted_norm in ("true", "false") and submitted_norm == correct_norm

    marks_awarded = marks_possible if is_correct else 0.0

    return {
        "is_correct":     is_correct,
        "marks_awarded":  marks_awarded,
        "marks_possible": marks_possible,
        "correct_answer": correct_text,
        "explanation":    explanation,
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/start")
async def start_session(body: StartRequest):
    """
    Create an evaluation session for a generated exam.
    Also evicts expired sessions to keep memory bounded.
    Returns session_id + duration_minutes.
    """
    _evict_expired_sessions()

    session_id = str(uuid.uuid4())
    questions  = _flatten_questions(body.exam)

    if not questions:
        raise HTTPException(status_code=400, detail="Exam has no questions.")

    _sessions[session_id] = {
        "exam":           body.exam,
        "candidate_name": body.candidate_name or "Candidate",
        "questions":      questions,
        "answers":        {},
        "started_at":     time.time(),
    }

    return {
        "session_id":       session_id,
        "duration_minutes": body.exam.get("duration_minutes", 30),
        "total_questions":  len(questions),
    }


@router.post("/answer")
async def submit_answer(body: AnswerRequest):
    """
    Evaluate a single answer and return immediate feedback.
    Idempotent — re-submitting the same question_idx overwrites the previous answer.

    Returns 404 if the session is not found. This can happen after a dyno
    restart — the frontend should show a user-friendly "session expired" message.
    """
    session = _sessions.get(body.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. The server may have restarted — please start a new exam."
        )

    questions = session["questions"]
    if body.question_idx < 0 or body.question_idx >= len(questions):
        raise HTTPException(status_code=400, detail="Invalid question index.")

    question = questions[body.question_idx]
    result   = _check_answer(question, body.answer)

    session["answers"][body.question_idx] = {
        "given_answer": body.answer,
        **result,
    }

    score_so_far = sum(
        r["marks_awarded"] for r in session["answers"].values()
    )
    max_so_far = sum(
        float(questions[i].get("marks", 1))
        for i in session["answers"]
    )

    return {
        **result,
        "progress": {
            "answered":     len(session["answers"]),
            "total":        len(questions),
            "score_so_far": round(score_so_far, 2),
            "max_so_far":   round(max_so_far, 2),
        },
    }


@router.post("/finish/{session_id}")
async def finish_session(session_id: str):
    """
    Finalise the session and return the full result payload.
    Shape matches what ResultPage.jsx and SyllabusResultPage.jsx expect.
    """
    session = _sessions.pop(session_id, None)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or already finished. The server may have restarted."
        )

    questions      = session["questions"]
    answers        = session["answers"]
    candidate_name = session["candidate_name"]
    exam           = session["exam"]
    elapsed        = int(time.time() - session["started_at"])

    total_marks     = sum(float(q.get("marks", 1)) for q in questions)
    obtained_marks  = sum(r["marks_awarded"] for r in answers.values())
    pass_percentage = float(exam.get("pass_percentage", 40))
    percentage      = round((obtained_marks / total_marks * 100), 1) if total_marks else 0
    passed          = percentage >= pass_percentage
    pass_mark       = round(total_marks * pass_percentage / 100, 1)

    questions_correct  = sum(1 for r in answers.values() if r["is_correct"])
    questions_answered = len(answers)
    questions_skipped  = len(questions) - questions_answered

    section_map: Dict[str, Dict[str, Any]] = {}
    for idx, q in enumerate(questions):
        sec = q.get("_section", "General")
        if sec not in section_map:
            section_map[sec] = {"correct": 0, "total": 0, "marks": 0, "max": 0}
        section_map[sec]["total"] += 1
        section_map[sec]["max"]   += float(q.get("marks", 1))
        if idx in answers:
            section_map[sec]["marks"]   += answers[idx]["marks_awarded"]
            if answers[idx]["is_correct"]:
                section_map[sec]["correct"] += 1

    topic_breakdown = [
        {
            "topic":          sec,
            "correct":        v["correct"],
            "questions_seen": v["total"],
            "accuracy_pct":   round(v["correct"] / v["total"] * 100) if v["total"] else 0,
        }
        for sec, v in section_map.items()
    ]

    weak_topics = [t["topic"] for t in topic_breakdown if t["accuracy_pct"] < 50]

    question_results = []
    for idx, q in enumerate(questions):
        ans = answers.get(idx)
        skipped = ans is None
        question_results.append({
            "question":       q.get("text", ""),
            "section":        q.get("_section", ""),
            "given_answer":   ans["given_answer"] if ans else "",
            "correct_answer": ans["correct_answer"] if ans else q.get("correct_answer", ""),
            "is_correct":     ans["is_correct"] if ans else False,
            "skipped":        skipped,
            "marks_awarded":  ans["marks_awarded"] if ans else 0,
            "marks_possible": float(q.get("marks", 1)),
            "explanation":    ans["explanation"] if ans else q.get("explanation", ""),
        })

    performance_summary = (
        f"You scored {percentage}% and {'passed' if passed else 'did not pass'} the exam. "
        f"You answered {questions_answered} of {len(questions)} questions, "
        f"getting {questions_correct} correct."
    )

    return {
        "score":               round(obtained_marks, 2),
        "total_marks":         round(total_marks, 2),
        "percentage":          round(percentage),
        "passed":              passed,
        "pass_mark":           pass_mark,
        "pass_percentage":     pass_percentage,
        "time_taken_seconds":  elapsed,
        "questions_total":     len(questions),
        "questions_answered":  questions_answered,
        "questions_correct":   questions_correct,
        "questions_skipped":   questions_skipped,
        "topic_breakdown":     topic_breakdown,
        "weak_topics":         weak_topics,
        "question_results":    question_results,
        "performance_summary": performance_summary,
        "candidate_name":      candidate_name,
        "exam_title":          exam.get("title", "Generated Exam"),
    }
