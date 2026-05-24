"""
ExamVerse / ExamForge — Syllabus Upload & Exam Generation Router
================================================================
File:  backend/routers/syllabus.py

Endpoints:
  POST /api/syllabus/upload-and-generate
    • Accepts a syllabus file (TXT / PDF / DOCX) + generation params
    • Returns the generated exam JSON + a syllabus coverage report
    • Uses the local rule-based generator — no external API needed

  POST /api/syllabus/search-and-generate          ← NEW
    • No file needed — just a topic name
    • Searches Tavily for rich content about the topic
    • Feeds that content into the same rule-based generator
    • Requires TAVILY_API_KEY env var

Registration (already done in your main.py):
  app.include_router(syllabus_router, prefix="/api/syllabus", tags=["syllabus"])
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional

from services.ai_generator import (
    extract_text_from_file,
    generate_exam_from_syllabus,
    build_syllabus_text_from_search,   # ← new Tavily helper
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Upload file and generate (existing, unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/upload-and-generate")
async def upload_syllabus_and_generate_exam(
    file:           UploadFile      = File(...),
    num_questions:  int             = Form(default=10),
    difficulty:     str             = Form(default="mixed"),    # easy|medium|hard|mixed
    question_types: str             = Form(default="mixed"),    # mcq|true_false|short|mixed
    time_limit:     int             = Form(default=30),         # minutes
    exam_title:     Optional[str]   = Form(default=None),
    focus_topics:   Optional[str]   = Form(default=None),       # comma-separated
):
    """
    Upload a syllabus file and immediately generate an exam from it.

    Returns:
        {
          "success": true,
          "source": "file",
          "exam": { title, description, duration_minutes, total_marks,
                    sections: [{ title, description, questions: [...] }] },
          "coverage_report": { ... },
          "syllabus_preview": "first 500 chars of extracted text"
        }
    """
    # ── Validate file type ────────────────────────────────────────────────────
    allowed_exts = {"txt", "pdf", "docx", "doc"}
    filename = file.filename or "upload.txt"
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
        )

    # ── Validate params ───────────────────────────────────────────────────────
    if not 1 <= num_questions <= 300:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 300.")
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        raise HTTPException(status_code=400, detail="difficulty must be easy|medium|hard|mixed.")
    if question_types not in ("mcq", "true_false", "short", "mixed"):
        raise HTTPException(status_code=400, detail="question_types must be mcq|true_false|short|mixed.")

    # ── Read file ─────────────────────────────────────────────────────────────
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    # ── Extract text ──────────────────────────────────────────────────────────
    try:
        syllabus_text = await extract_text_from_file(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {e}")

    if not syllabus_text.strip():
        raise HTTPException(status_code=422, detail="Could not extract any text from the uploaded file.")

    # ── Generate exam ─────────────────────────────────────────────────────────
    try:
        result = await generate_exam_from_syllabus(
            syllabus_text   = syllabus_text,
            num_questions   = num_questions,
            difficulty      = difficulty,
            question_types  = question_types,
            time_limit      = time_limit,
            exam_title      = exam_title,
            focus_topics    = focus_topics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exam generation failed: {e}")

    return JSONResponse({
        "success":          True,
        "source":           "file",
        "exam":             result,
        "coverage_report":  result.pop("coverage_report", {}),
        "syllabus_preview": syllabus_text[:500],
    })


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Search topic on web and generate  ← NEW
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/search-and-generate")
async def search_topic_and_generate_exam(
    topic:          str             = Form(...),                # required: main subject
    exam_title:     Optional[str]   = Form(default=None),       # e.g. "OSSSC RI Exam"
    sub_topics:     Optional[str]   = Form(default=None),       # comma-separated extras
    num_questions:  int             = Form(default=10),
    difficulty:     str             = Form(default="mixed"),
    question_types: str             = Form(default="mixed"),
    time_limit:     int             = Form(default=30),
):
    """
    Search the web for content about `topic` using Tavily, then generate an exam.
    No file upload required.

    Form fields:
        topic           — main subject, e.g. "History of Odisha"
        exam_title      — optional label, e.g. "OSSSC General Awareness"
        sub_topics      — optional comma-separated sub-topics to also search,
                          e.g. "Kalinga War, Jagannath Temple, Tribal Culture"
        num_questions   — 1–300
        difficulty      — easy|medium|hard|mixed
        question_types  — mcq|true_false|short|mixed
        time_limit      — minutes

    Returns:
        {
          "success": true,
          "source": "web_search",
          "queries_used": ["History of Odisha", "Kalinga War", ...],
          "exam": { ... },
          "coverage_report": { ... },
          "content_preview": "first 500 chars fetched from web"
        }

    Errors:
        400  — missing/invalid params
        422  — Tavily returned no usable content
        503  — TAVILY_API_KEY not configured or Tavily unreachable
    """
    # ── Validate params ───────────────────────────────────────────────────────
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="'topic' field is required and cannot be blank.")
    if len(topic) > 300:
        raise HTTPException(status_code=400, detail="'topic' must be under 300 characters.")
    if not 1 <= num_questions <= 300:
        raise HTTPException(status_code=400, detail="num_questions must be between 1 and 300.")
    if difficulty not in ("easy", "medium", "hard", "mixed"):
        raise HTTPException(status_code=400, detail="difficulty must be easy|medium|hard|mixed.")
    if question_types not in ("mcq", "true_false", "short", "mixed"):
        raise HTTPException(status_code=400, detail="question_types must be mcq|true_false|short|mixed.")

    # ── Fetch content from web via Tavily ─────────────────────────────────────
    try:
        syllabus_text, queries_used = await build_syllabus_text_from_search(
            topic       = topic,
            exam_title  = exam_title or "",
            sub_topics  = sub_topics,
        )
    except RuntimeError as e:
        # RuntimeError = known Tavily problem (no key, bad key, no results)
        err = str(e)
        if "TAVILY_API_KEY" in err:
            raise HTTPException(status_code=503, detail=err)
        if "no usable content" in err.lower():
            raise HTTPException(status_code=422, detail=err)
        raise HTTPException(status_code=503, detail=err)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Web search failed unexpectedly: {e}")

    if not syllabus_text.strip():
        raise HTTPException(
            status_code=422,
            detail=f"No usable content found for topic '{topic}'. Try rephrasing."
        )

    # ── Generate exam from fetched content ────────────────────────────────────
    try:
        result = await generate_exam_from_syllabus(
            syllabus_text   = syllabus_text,
            num_questions   = num_questions,
            difficulty      = difficulty,
            question_types  = question_types,
            time_limit      = time_limit,
            exam_title      = exam_title or f"{topic} — Exam",
            focus_topics    = sub_topics,   # re-use as focus filter inside generator
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exam generation failed: {e}")

    return JSONResponse({
        "success":          True,
        "source":           "web_search",
        "queries_used":     queries_used,
        "exam":             result,
        "coverage_report":  result.pop("coverage_report", {}),
        "content_preview":  syllabus_text[:500],
    })
