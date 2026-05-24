"""
ExamVerse / ExamForge — Per-Question Evaluation Engine
=======================================================
File:  backend/routers/evaluation.py

Endpoints:
  POST /api/evaluation/answer        — evaluate one answer, update session
  GET  /api/evaluation/session/{id}  — get current session state
  POST /api/evaluation/finish/{id}   — close session, get final report
  POST /api/evaluation/start         — create a new attempt session

Registration — add to backend/main.py:
  from routers.evaluation import router as evaluation_router
  app.include_router(evaluation_router, prefix="/api/evaluation", tags=["evaluation"])
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid, time

router = APIRouter()

# ── In-memory session store ────────────────────────────────────────────────────
# Each session holds the full exam structure + candidate's answers so far.
# For production: replace with Redis or a DB table.
_SESSIONS: dict[str, dict] = {}
SESSION_TTL = 60 * 60 * 3   # 3 hours

def _prune_expired():
    now = time.time()
    expired = [k for k, v in _SESSIONS.items() if now - v["started_at"] > SESSION_TTL]
    for k in expired:
        del _SESSIONS[k]


# ══════════════════════════════════════════════════════════════════════════════
# MODELS
# ══════════════════════════════════════════════════════════════════════════════

class StartSessionRequest(BaseModel):
    exam: dict                        # the full exam object from /api/syllabus/upload-and-generate
    candidate_name: Optional[str] = "Anonymous"
    candidate_id:   Optional[str] = None


class AnswerRequest(BaseModel):
    session_id:   str
    question_idx: int                 # 0-based global index across all sections
    answer:       str                 # candidate's answer text or option text


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _flatten_questions(exam: dict) -> list[dict]:
    """Return all questions as a flat list with section info attached."""
    flat = []
    for sec in exam.get("sections", []):
        for q in sec.get("questions", []):
            flat.append({**q, "_section": sec["title"]})
    return flat


def _evaluate_answer(question: dict, candidate_answer: str) -> dict:
    """
    Compare candidate_answer to the question's correct answer.
    Returns: { is_correct, marks_awarded, correct_answer, explanation, feedback }
    """
    q_type  = question.get("question_type", "mcq")
    marks   = question.get("marks", 1)
    correct = str(question.get("correct_answer", "")).strip()
    given   = candidate_answer.strip()

    # ── MCQ: match option text or option label (A/B/C/D) ──────────────────────
    if q_type == "mcq":
        # Find the correct option text from the options list
        correct_option_text = correct
        for opt in question.get("options", []):
            if opt.get("is_correct"):
                correct_option_text = opt["text"]
                break

        is_correct = given.lower() == correct_option_text.lower()

    # ── True/False ─────────────────────────────────────────────────────────────
    elif q_type == "true_false":
        # Accept "true"/"false", "yes"/"no", "t"/"f"
        true_aliases  = {"true", "t", "yes", "y", "1"}
        false_aliases = {"false", "f", "no", "n", "0"}
        given_norm   = given.lower()
        correct_norm = correct.lower()

        if correct_norm in true_aliases:
            is_correct = given_norm in true_aliases
        elif correct_norm in false_aliases:
            is_correct = given_norm in false_aliases
        else:
            is_correct = given_norm == correct_norm

    # ── Short answer / fill-in-the-blank ──────────────────────────────────────
    else:
        # Case-insensitive, strip punctuation, partial match allowed
        import re
        def normalise(s):
            return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()

        gn = normalise(given)
        cn = normalise(correct)
        is_correct = (gn == cn) or (cn and cn in gn) or (gn and gn in cn)

    marks_awarded = marks if is_correct else 0

    # Feedback message
    if is_correct:
        feedback = "✅ Correct!"
    else:
        feedback = f"❌ Incorrect. The correct answer is: {_correct_display(question)}"

    return {
        "is_correct":     is_correct,
        "marks_awarded":  marks_awarded,
        "marks_possible": marks,
        "correct_answer": _correct_display(question),
        "explanation":    question.get("explanation", ""),
        "feedback":       feedback,
    }


def _correct_display(question: dict) -> str:
    """Return a human-readable correct answer string."""
    for opt in question.get("options", []):
        if opt.get("is_correct"):
            return opt["text"]
    return str(question.get("correct_answer", ""))


def _build_topic_breakdown(answers: list[dict], questions: list[dict]) -> list[dict]:
    """Group scores by section/topic."""
    topic_data: dict[str, dict] = {}
    for i, ans in enumerate(answers):
        if ans is None:
            continue
        q   = questions[i]
        sec = q.get("_section", "General")
        if sec not in topic_data:
            topic_data[sec] = {"correct": 0, "total": 0, "marks_earned": 0, "marks_possible": 0}
        topic_data[sec]["total"]          += 1
        topic_data[sec]["marks_possible"] += q.get("marks", 1)
        if ans.get("is_correct"):
            topic_data[sec]["correct"]     += 1
            topic_data[sec]["marks_earned"] += ans.get("marks_awarded", 0)

    return [
        {
            "topic":           sec,
            "questions_seen":  d["total"],
            "correct":         d["correct"],
            "marks_earned":    d["marks_earned"],
            "marks_possible":  d["marks_possible"],
            "accuracy_pct":    round(d["correct"] / d["total"] * 100, 1) if d["total"] else 0,
        }
        for sec, d in topic_data.items()
    ]


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/start")
async def start_session(req: StartSessionRequest):
    """
    Create a new exam attempt session.
    Call this when a candidate clicks 'Start Exam'.

    Returns: { session_id, total_questions, exam_title }
    """
    _prune_expired()

    questions = _flatten_questions(req.exam)
    if not questions:
        raise HTTPException(status_code=400, detail="Exam has no questions.")

    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "session_id":     session_id,
        "candidate_name": req.candidate_name,
        "candidate_id":   req.candidate_id,
        "exam":           req.exam,
        "questions":      questions,          # flat list with _section attached
        "answers":        [None] * len(questions),  # filled as candidate answers
        "started_at":     time.time(),
        "finished_at":    None,
        "finished":       False,
    }

    return {
        "session_id":      session_id,
        "total_questions": len(questions),
        "exam_title":      req.exam.get("title", "Exam"),
        "duration_minutes": req.exam.get("duration_minutes", 30),
        "total_marks":     req.exam.get("total_marks", len(questions)),
    }


@router.post("/answer")
async def submit_answer(req: AnswerRequest):
    """
    Evaluate one answer as the candidate submits it.

    Returns immediate feedback:
    {
      "is_correct": bool,
      "marks_awarded": int,
      "marks_possible": int,
      "correct_answer": str,
      "explanation": str,
      "feedback": str,
      "progress": {
          "answered": int, "total": int,
          "score_so_far": int, "max_so_far": int,
          "percentage_so_far": float
      }
    }
    """
    session = _SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    if session["finished"]:
        raise HTTPException(status_code=400, detail="This session is already finished.")

    questions = session["questions"]
    if req.question_idx < 0 or req.question_idx >= len(questions):
        raise HTTPException(
            status_code=400,
            detail=f"question_idx must be 0–{len(questions) - 1}.",
        )

    question = questions[req.question_idx]
    result   = _evaluate_answer(question, req.answer)

    # Store result
    session["answers"][req.question_idx] = {
        **result,
        "given_answer": req.answer,
        "question_idx": req.question_idx,
    }

    # Live progress
    answered = [a for a in session["answers"] if a is not None]
    score_so_far = sum(a["marks_awarded"] for a in answered)
    max_so_far   = sum(questions[i]["marks"] for i, a in enumerate(session["answers"]) if a is not None)

    return JSONResponse({
        **result,
        "progress": {
            "answered":          len(answered),
            "total":             len(questions),
            "score_so_far":      score_so_far,
            "max_so_far":        max_so_far,
            "percentage_so_far": round(score_so_far / max_so_far * 100, 1) if max_so_far else 0,
        },
    })


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    Get the current state of an exam session.
    Useful to restore state if the page refreshes.
    """
    session = _SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    questions = session["questions"]
    answered  = [a for a in session["answers"] if a is not None]

    return {
        "session_id":      session_id,
        "candidate_name":  session["candidate_name"],
        "exam_title":      session["exam"].get("title"),
        "total_questions": len(questions),
        "answered":        len(answered),
        "finished":        session["finished"],
        "answers":         session["answers"],   # list with None for unanswered
    }


@router.post("/finish/{session_id}")
async def finish_session(session_id: str):
    """
    Close the session and return the full result report.
    Call when the candidate submits the exam or time runs out.

    Returns:
    {
      "score": int,
      "total_marks": int,
      "percentage": float,
      "passed": bool,
      "pass_mark": int,
      "time_taken_seconds": int,
      "questions_answered": int,
      "questions_correct": int,
      "topic_breakdown": [...],
      "question_results": [...],    ← full per-question detail
      "performance_summary": str
    }
    """
    session = _SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    session["finished"]    = True
    session["finished_at"] = time.time()

    questions  = session["questions"]
    answers    = session["answers"]
    exam       = session["exam"]

    total_marks    = exam.get("total_marks", len(questions))
    pass_pct       = exam.get("pass_percentage", 40)
    pass_mark      = round(total_marks * pass_pct / 100)

    # Score unanswered questions as 0
    score = sum(
        (a["marks_awarded"] if a else 0)
        for a in answers
    )
    correct_count = sum(1 for a in answers if a and a["is_correct"])
    answered_count = sum(1 for a in answers if a is not None)

    percentage  = round(score / total_marks * 100, 1) if total_marks else 0
    passed      = score >= pass_mark
    time_taken  = int(session["finished_at"] - session["started_at"])

    # Per-question results (including unanswered)
    question_results = []
    for i, q in enumerate(questions):
        a = answers[i]
        question_results.append({
            "question_idx":   i,
            "section":        q.get("_section", "General"),
            "question":       q["text"],
            "question_type":  q["question_type"],
            "difficulty":     q["difficulty"],
            "marks_possible": q["marks"],
            "given_answer":   a["given_answer"] if a else None,
            "correct_answer": _correct_display(q),
            "is_correct":     a["is_correct"] if a else False,
            "marks_awarded":  a["marks_awarded"] if a else 0,
            "explanation":    q.get("explanation", ""),
            "skipped":        a is None,
        })

    topic_breakdown = _build_topic_breakdown(answers, questions)

    # Simple performance summary
    if percentage >= 80:
        perf = "Excellent! Outstanding performance."
    elif percentage >= 60:
        perf = "Good performance. A few areas to review."
    elif percentage >= pass_pct:
        perf = "Passed. Focus on weak areas to improve further."
    else:
        perf = "Did not pass. Review the topics marked as weak areas."

    weak_topics = [t["topic"] for t in topic_breakdown if t["accuracy_pct"] < 50]

    return JSONResponse({
        "score":               score,
        "total_marks":         total_marks,
        "percentage":          percentage,
        "passed":              passed,
        "pass_mark":           pass_mark,
        "pass_percentage":     pass_pct,
        "time_taken_seconds":  time_taken,
        "questions_total":     len(questions),
        "questions_answered":  answered_count,
        "questions_correct":   correct_count,
        "questions_skipped":   len(questions) - answered_count,
        "topic_breakdown":     topic_breakdown,
        "weak_topics":         weak_topics,
        "question_results":    question_results,
        "performance_summary": perf,
        "candidate_name":      session["candidate_name"],
        "exam_title":          exam.get("title"),
    })
