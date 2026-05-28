"""
ExamVerse / ExamForge — Syllabus Upload & Exam Generation Router
================================================================
File:  backend/routers/syllabus.py

Endpoints:
  POST /api/syllabus/upload-and-generate
    • Accepts a syllabus file (TXT / PDF / DOCX) + generation params
    • Returns the generated exam JSON + a syllabus coverage report
    • Uses the local rule-based generator — no external API needed

Registration (already done in your main.py):
  app.include_router(syllabus_router, prefix="/api/syllabus", tags=["syllabus"])
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from services.ai_generator import extract_text_from_file, generate_exam_from_syllabus

router = APIRouter()


@router.post("/upload-and-generate")
async def upload_syllabus_and_generate_exam(
    file:           UploadFile  = File(...),
    num_questions:  int         = Form(default=10),
    difficulty:     str         = Form(default="mixed"),    # easy | medium | hard | mixed
    question_types: str         = Form(default="mixed"),    # mcq | true_false | short | mixed
    time_limit:     int         = Form(default=30),         # minutes
    exam_title:     Optional[str] = Form(default=None),
    focus_topics:   Optional[str] = Form(default=None),     # comma-separated, optional
):
    """
    Upload a syllabus file and immediately generate an exam from it.

    Returns:
        {
          "success": true,
          "exam": { title, description, duration_minutes, total_marks,
                    sections: [{ title, description, questions: [...] }] },
          "coverage_report": {
              total_topics_in_syllabus, topics_covered, topics_missing,
              coverage_percentage, covered_topic_list, missing_topic_list,
              questions_per_topic, weak_areas,
              question_distribution: { by_type, by_difficulty },
              sections_detected, total_questions
          },
          "syllabus_preview": "first 500 chars of extracted text"
        }
    """
    # ── Validate file type ──────────────────────────────────────────────────
    allowed_types = {
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }
    allowed_exts = {"txt", "pdf", "docx", "doc"}

    filename = file.filename or "upload.txt"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
        )

    # ── Validate params ─────────────────────────────────────────────────────
    if not 1 <= num_questions <= 300:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 300.")
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        raise HTTPException(status_code=400, detail="difficulty must be easy | medium | hard | mixed.")
    if question_types not in ("mcq", "true_false", "short", "mixed"):
        raise HTTPException(status_code=400, detail="question_types must be mcq | true_false | short | mixed.")

    # ── Read file ──────────────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB guard
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20 MB.")

    if len(file_bytes) < 20:
        raise HTTPException(status_code=400, detail="Uploaded file appears to be empty.")

    # ── Extract text ────────────────────────────────────────────────────────
    try:
        syllabus_text = await extract_text_from_file(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from file: {e}")

    if not syllabus_text or len(syllabus_text.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="Could not extract readable text from the file. "
                   "Please ensure it contains selectable/searchable text.",
        )

    # ── Generate exam ───────────────────────────────────────────────────────
    try:
        result = await generate_exam_from_syllabus(
            syllabus_text  = syllabus_text,
            num_questions  = num_questions,
            difficulty     = difficulty,
            question_types = question_types,
            time_limit     = time_limit,
            exam_title     = exam_title,
            focus_topics   = focus_topics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exam generation failed: {e}")

    return JSONResponse(content={
        "success":         True,
        "exam":            {
            "title":            result["title"],
            "description":      result["description"],
            "duration_minutes": result["duration_minutes"],
            "total_marks":      result["total_marks"],
            "pass_percentage":  result["pass_percentage"],
            "negative_marking": result["negative_marking"],
            "sections":         result["sections"],
        },
        "coverage_report": result.get("coverage_report", {}),
        "syllabus_preview": syllabus_text[:500],
    })


# ══════════════════════════════════════════════════════════════════════════════
#  NEW: Search-based exam generation (no file upload needed)
# ══════════════════════════════════════════════════════════════════════════════

from services.ai_generator import generate_exam_from_search, TAVILY_API_KEY
from pydantic import BaseModel


class SearchGenerateRequest(BaseModel):
    topics:         list[str]
    num_questions:  int           = 10
    difficulty:     str           = "mixed"
    question_types: str           = "mixed"
    time_limit:     int           = 30
    exam_title:     Optional[str] = None
    focus_topics:   Optional[str] = None
    extra_context:  str           = ""      # e.g. "UPSC exam India"


@router.post("/search-and-generate")
async def search_and_generate_exam(body: SearchGenerateRequest):
    """
    Generate an exam from topic keywords instead of an uploaded file.
    Fetches real web content via Tavily (if TAVILY_API_KEY is set),
    then runs the rule-based generator on the fetched text.

    Request body (JSON):
        {
          "topics": ["Odisha Geography", "Indian Constitution"],
          "num_questions": 20,
          "difficulty": "mixed",
          "question_types": "mixed",
          "time_limit": 30,
          "extra_context": "OSSSC exam",
          "exam_title": "Odisha GK Test"
        }
    """
    if not body.topics:
        raise HTTPException(status_code=400, detail="Provide at least one topic.")
    if not 1 <= body.num_questions <= 300:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 300.")
    if body.difficulty not in ("easy", "medium", "hard", "mixed"):
        raise HTTPException(status_code=400, detail="difficulty must be easy | medium | hard | mixed.")
    if body.question_types not in ("mcq", "true_false", "short", "mixed"):
        raise HTTPException(status_code=400, detail="question_types must be mcq | true_false | short | mixed.")

    try:
        result = await generate_exam_from_search(
            topics         = body.topics,
            num_questions  = body.num_questions,
            difficulty     = body.difficulty,
            question_types = body.question_types,
            time_limit     = body.time_limit,
            exam_title     = body.exam_title,
            focus_topics   = body.focus_topics,
            extra_context  = body.extra_context,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search-based generation failed: {e}")

    return JSONResponse(content={
        "success":          True,
        "search_enabled":   bool(TAVILY_API_KEY),
        "exam":             {
            "title":            result["title"],
            "description":      result["description"],
            "duration_minutes": result["duration_minutes"],
            "total_marks":      result["total_marks"],
            "pass_percentage":  result["pass_percentage"],
            "negative_marking": result["negative_marking"],
            "sections":         result["sections"],
        },
        "coverage_report":  result.get("coverage_report", {}),
        "queries_used":     result.get("coverage_report", {}).get("queries_used", []),
        "source":           result.get("coverage_report", {}).get("source", "fallback"),
    })
