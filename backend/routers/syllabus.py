"""
Router: /api/syllabus
POST /api/syllabus/generate  — Admin uploads syllabus → AI generates exam → saves to DB
GET  /api/syllabus/preview   — Generate preview JSON without saving (for testing)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
import json

from database import get_db
from utils.auth import get_current_admin
import models
from services.ai_generator import extract_text_from_file, generate_exam_from_syllabus

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ── Helper: save AI exam dict → DB ────────────────────────────────────────────

def _save_exam_to_db(
    exam_dict: dict, admin_user: models.User, db: Session
) -> models.Exam:
    """
    Persist the AI-generated exam JSON into the DB as:
    Exam → Section(s) → Question(s) → Option(s)
    """
    q_type_map = {
        "mcq":          models.QuestionType.MCQ_SINGLE,
        "mcq_single":   models.QuestionType.MCQ_SINGLE,
        "true_false":   models.QuestionType.TRUE_FALSE,
        "short_answer": models.QuestionType.FILL_BLANK,
        "fill_blank":   models.QuestionType.FILL_BLANK,
        "long_answer":  models.QuestionType.LONG_ANSWER,
        "numeric":      models.QuestionType.NUMERIC,
    }

    # 1. Create Exam
    exam = models.Exam(
        title=exam_dict.get("title", "AI Generated Exam"),
        description=exam_dict.get("description", ""),
        instructions=(
            "This exam was automatically generated from a syllabus using AI.\n"
            "Read each question carefully and select the best answer.\n"
            "The exam will auto-submit when the timer runs out."
        ),
        duration_minutes=int(exam_dict.get("duration_minutes", 30)),
        total_marks=0.0,          # recalculated below
        pass_percentage=float(exam_dict.get("pass_percentage", 40)),
        negative_marking=bool(exam_dict.get("negative_marking", False)),
        negative_marks_per_question=float(exam_dict.get("negative_marks_per_question", 0.25)),
        shuffle_questions=False,
        shuffle_options=True,
        max_attempts=3,
        is_public=True,
        is_active=True,
        show_result_immediately=True,
        allow_review=True,
        created_by=admin_user.id,
    )
    db.add(exam)
    db.flush()  # get exam.id

    total_marks = 0.0

    # 2. Create Sections
    for sec_order, sec_dict in enumerate(exam_dict.get("sections", [])):
        section = models.Section(
            exam_id=exam.id,
            title=sec_dict.get("title", f"Section {sec_order + 1}"),
            description=sec_dict.get("description", ""),
            order=sec_order,
        )
        db.add(section)
        db.flush()  # get section.id

        # 3. Create Questions
        for q_order, q_dict in enumerate(sec_dict.get("questions", [])):
            raw_type = q_dict.get("question_type", "mcq").lower().replace(" ", "_")
            q_type = q_type_map.get(raw_type, models.QuestionType.MCQ_SINGLE)
            marks = float(q_dict.get("marks", 1))
            total_marks += marks

            question = models.Question(
                section_id=section.id,
                text=q_dict.get("text", ""),
                question_type=q_type,
                marks=marks,
                negative_marks=float(exam_dict.get("negative_marks_per_question", 0.25)),
                difficulty=q_dict.get("difficulty", "medium"),
                explanation=q_dict.get("explanation", ""),
                order=q_order,
                is_active=True,
            )
            db.add(question)
            db.flush()  # get question.id

            # 4. Create Options
            options = q_dict.get("options", [])

            # short_answer / fill_blank: store correct_answer as a single "correct" option
            if q_type == models.QuestionType.FILL_BLANK and not options:
                correct_ans = q_dict.get("correct_answer", "")
                if correct_ans:
                    db.add(models.Option(
                        question_id=question.id,
                        text=correct_ans,
                        is_correct=True,
                        order=0,
                    ))
            else:
                for opt_order, opt_dict in enumerate(options):
                    db.add(models.Option(
                        question_id=question.id,
                        text=opt_dict.get("text", ""),
                        is_correct=bool(opt_dict.get("is_correct", False)),
                        order=opt_order,
                    ))

    # Update total_marks with actual calculated value
    exam.total_marks = total_marks
    db.commit()
    db.refresh(exam)
    return exam


# ── POST /api/syllabus/generate ───────────────────────────────────────────────

@router.post("/generate")
async def generate_exam(
    # File OR raw text — at least one required
    file: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),

    # Exam config
    num_questions: int      = Form(10),
    difficulty: str         = Form("medium"),     # easy | medium | hard | mixed
    question_types: str     = Form("mixed"),      # mcq | mixed | true_false | short
    time_limit: int         = Form(30),
    exam_title: Optional[str] = Form(None),
    focus_topics: Optional[str] = Form(None),

    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_admin),
):
    """
    Upload a syllabus PDF/DOCX/TXT (or paste raw text) →
    Gemini AI generates a full exam →
    Saved to DB and returned as JSON.
    """
    # 1. Get syllabus content
    text = ""

    if file and file.filename:
        raw = await file.read()
        if len(raw) > MAX_FILE_SIZE:
            raise HTTPException(400, "File too large. Maximum size is 10 MB.")
        text = await extract_text_from_file(raw, file.filename)

    elif syllabus_text:
        text = syllabus_text.strip()

    if not text:
        raise HTTPException(400, "Provide a syllabus file or paste syllabus text.")

    if len(text) < 50:
        raise HTTPException(400, "Syllabus content is too short to generate an exam from.")

    # 2. Clamp inputs
    num_questions = max(3, min(num_questions, 50))
    time_limit    = max(5, min(time_limit, 180))

    # 3. Call Gemini
    try:
        exam_dict = await generate_exam_from_syllabus(
            syllabus_text=text,
            num_questions=num_questions,
            difficulty=difficulty,
            question_types=question_types,
            time_limit=time_limit,
            exam_title=exam_title,
            focus_topics=focus_topics,
        )
    except ValueError as e:
        raise HTTPException(502, f"AI generation failed: {e}")

    # 4. Save to DB
    try:
        exam = _save_exam_to_db(exam_dict, current_admin, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to save exam to database: {e}")

    return {
        "message": "Exam generated and saved successfully.",
        "exam_id": exam.id,
        "title": exam.title,
        "total_marks": exam.total_marks,
        "duration_minutes": exam.duration_minutes,
        "is_public": exam.is_public,
        "is_active": exam.is_active,
        "preview_url": f"/admin/exams/{exam.id}",
    }


# ── POST /api/syllabus/preview ────────────────────────────────────────────────

@router.post("/preview")
async def preview_exam(
    file: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),
    num_questions: int      = Form(5),
    difficulty: str         = Form("medium"),
    question_types: str     = Form("mixed"),
    time_limit: int         = Form(30),
    exam_title: Optional[str] = Form(None),
    focus_topics: Optional[str] = Form(None),
    _: models.User = Depends(get_current_admin),
):
    """
    Same as /generate but does NOT save to the database.
    Returns raw AI output for frontend preview / confirmation.
    """
    text = ""
    if file and file.filename:
        raw = await file.read()
        text = await extract_text_from_file(raw, file.filename)
    elif syllabus_text:
        text = syllabus_text.strip()

    if not text or len(text) < 50:
        raise HTTPException(400, "Provide valid syllabus content.")

    try:
        exam_dict = await generate_exam_from_syllabus(
            syllabus_text=text,
            num_questions=max(3, min(num_questions, 50)),
            difficulty=difficulty,
            question_types=question_types,
            time_limit=max(5, min(time_limit, 180)),
            exam_title=exam_title,
            focus_topics=focus_topics,
        )
    except ValueError as e:
        raise HTTPException(502, f"AI generation failed: {e}")

    return exam_dict
