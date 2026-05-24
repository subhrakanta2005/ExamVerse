"""
AI Exam Generator Service
Uses Google Gemini API (free tier) to generate exam questions from syllabus content.
Model: gemini-2.0-flash  —  free, fast, 1500 req/day, no card needed.
"""
import os
import json
import httpx
from typing import Optional

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


# ── Text extraction ────────────────────────────────────────────────────────────

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract plain text from uploaded file bytes (PDF / DOCX / TXT)."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except ImportError:
            return f"[PDF: {filename} — add 'pypdf' to requirements.txt]"
        except Exception as e:
            return f"[PDF parse error: {e}]"

    if ext in ("docx", "doc"):
        try:
            import docx, io
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except ImportError:
            return f"[DOCX: {filename} — add 'python-docx' to requirements.txt]"
        except Exception as e:
            return f"[DOCX parse error: {e}]"

    # Fallback
    return file_bytes.decode("utf-8", errors="ignore")


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _build_prompt(
    syllabus_text: str,
    num_questions: int,
    difficulty: str,
    question_types: str,
    time_limit: int,
    exam_title: Optional[str],
    focus_topics: Optional[str],
) -> str:
    type_guide = {
        "mcq":        "ALL questions must be multiple-choice (type='mcq') with exactly 4 options, exactly 1 correct.",
        "mixed":      "Mix: ~60% mcq (4 options, 1 correct), ~25% true_false (2 options: True/False), ~15% short_answer (no options, just correct_answer string).",
        "true_false": "ALL questions must be true_false with exactly 2 options: 'True' and 'False'.",
        "short":      "ALL questions must be short_answer type with no options — just a correct_answer string.",
    }.get(question_types, "Mix of mcq, true_false, and short_answer.")

    focus_line = f"\n- Focus on these topics only: {focus_topics}" if focus_topics else ""
    title_line = f"\n- Exam title to use: {exam_title}" if exam_title else ""

    return f"""You are an expert academic exam creator. Read the syllabus below and generate a complete exam as valid JSON only.

SYLLABUS:
{syllabus_text[:8000]}

REQUIREMENTS:
- Total questions: {num_questions}
- Difficulty: {difficulty}
- Time limit: {time_limit} minutes
- Question style: {type_guide}{focus_line}{title_line}

RULES:
1. Return ONLY valid JSON — no markdown, no explanation, no code fences.
2. Every question must directly relate to the syllabus content.
3. MCQ options must be plausible — wrong options should not be obviously wrong.
4. short_answer questions: set "options": [] and include "correct_answer": "<word or phrase>".
5. total_marks = sum of all question marks. pass_percentage = 40.

OUTPUT FORMAT (return exactly this structure):
{{
  "title": "string",
  "description": "string (1 sentence about what this exam covers)",
  "duration_minutes": {time_limit},
  "total_marks": <number>,
  "pass_percentage": 40,
  "negative_marking": false,
  "sections": [
    {{
      "title": "Section name",
      "description": "Brief section description",
      "questions": [
        {{
          "text": "Question text here?",
          "question_type": "mcq | true_false | short_answer",
          "marks": 1,
          "difficulty": "easy | medium | hard",
          "explanation": "Why the correct answer is correct (1-2 sentences)",
          "correct_answer": "Only for short_answer type — the expected answer string",
          "options": [
            {{"text": "Option A", "is_correct": false}},
            {{"text": "Option B", "is_correct": true}},
            {{"text": "Option C", "is_correct": false}},
            {{"text": "Option D", "is_correct": false}}
          ]
        }}
      ]
    }}
  ]
}}"""


# ── Gemini API call ────────────────────────────────────────────────────────────

async def generate_exam_from_syllabus(
    syllabus_text: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    question_types: str = "mixed",
    time_limit: int = 30,
    exam_title: Optional[str] = None,
    focus_topics: Optional[str] = None,
) -> dict:
    """
    Call Gemini API and return a parsed exam dict.
    Raises ValueError on API errors or bad JSON.
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    prompt = _build_prompt(
        syllabus_text, num_questions, difficulty,
        question_types, time_limit, exam_title, focus_topics,
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",   # forces JSON output
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code != 200:
        raise ValueError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()

    # Extract text from Gemini response structure
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response structure: {e}\n{data}")

    # Strip markdown fences if present (safety net)
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```", 2)[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        exam_dict = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}\nRaw: {raw_text[:500]}")

    return exam_dict
