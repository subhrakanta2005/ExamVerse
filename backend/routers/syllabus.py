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
    # ── Validate file type ─────────────────────────────────────────────────────
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

    # ── Validate params ────────────────────────────────────────────────────────
    if not 1 <= num_questions <= 100:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 100.")
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        raise HTTPException(status_code=400, detail="difficulty must be easy | medium | hard | mixed.")
    if question_types not in ("mcq", "true_false", "short", "mixed"):
        raise HTTPException(status_code=400, detail="question_types must be mcq | true_false | short | mixed.")

    # ── Read file ──────────────────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) > 10 * 1024 * 1024:  # 10 MB guard
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    # ── Extract text ───────────────────────────────────────────────────────────
    try:
        syllabus_text = await extract_text_from_file(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {e}")

    if not syllabus_text or len(syllabus_text.strip()) < 30:
        raise HTTPException(
            status_code=422,
            detail="Could not extract meaningful text from the file. "
                   "Please upload a readable TXT, PDF, or DOCX file.",
        )

    # ── Generate exam ──────────────────────────────────────────────────────────
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

    # ── Separate coverage report from exam body ────────────────────────────────
    coverage_report = result.pop("coverage_report", {})

    return JSONResponse({
        "success":          True,
        "exam":             result,
        "coverage_report":  coverage_report,
        "syllabus_preview": syllabus_text[:500],
    })


@router.get("/health")
async def syllabus_health():
    """Quick health check for the syllabus service."""
    return {"status": "ok", "generator": "rule-based (no API required)"}
