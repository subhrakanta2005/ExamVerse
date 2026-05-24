"""
AI Exam Generator Service
Provider: OpenRouter (openrouter.ai) — one key for 300+ models
Model:    anthropic/claude-3-haiku          (~$0.00025/call — very cheap, best JSON quality)
Fallback: google/gemini-2.0-flash-exp:free   (free, no credits)
Fallback: meta-llama/llama-3.3-70b-instruct  (cheap, if above busy)

Get your key at: https://openrouter.ai/keys
Set in .env:     OPENROUTER_API_KEY=sk-or-...
"""
import os
import json
import httpx
from typing import Optional

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL     = "https://openrouter.ai/api/v1/chat/completions"

# Free model first — uses $0 credits
# Falls back to cheap paid model (~$0.001/call) if free is rate-limited
MODELS = [
    "anthropic/claude-3-haiku",           # fastest + cheapest Claude — great for structured JSON
    "google/gemini-2.0-flash-exp:free",   # free fallback
    "meta-llama/llama-3.3-70b-instruct",  # cheap fallback
]


# ── Text extraction ────────────────────────────────────────────────────────────

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
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
        "mixed":      "Mix: ~60% mcq (4 options, 1 correct), ~25% true_false (2 options: True/False), ~15% short_answer.",
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
4. short_answer: set "options": [] and include "correct_answer": "<word or phrase>".
5. total_marks = sum of all question marks. pass_percentage = 40.

OUTPUT FORMAT (return exactly this structure):
{{
  "title": "string",
  "description": "string (1 sentence about what this exam covers)",
  "duration_minutes": {time_limit},
  "total_marks": 0,
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
          "explanation": "Why the correct answer is correct",
          "correct_answer": "Only for short_answer — the expected answer",
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


# ── JSON cleaner ───────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from AI: {e}\nRaw output: {raw[:500]}")


# ── OpenRouter call (tries models in order) ────────────────────────────────────

async def _call_openrouter(prompt: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Get your key at https://openrouter.ai/keys and add it to your env vars."
        )

    last_error = None

    for model in MODELS:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert exam creator. "
                        "Always respond with valid JSON only. "
                        "No markdown fences, no explanation, no text outside JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://examverse.app",
                    "X-Title":       "ExamVerse",
                },
            )

        if resp.status_code == 429 or resp.status_code == 503:
            # This model is busy/rate-limited — try next
            last_error = f"Model {model} returned {resp.status_code}"
            continue

        if resp.status_code != 200:
            raise ValueError(
                f"OpenRouter error {resp.status_code} with model {model}: {resp.text[:400]}"
            )

        data = resp.json()

        # Check for OpenRouter-level error inside 200 response (it does this sometimes)
        if "error" in data:
            last_error = f"Model {model} error: {data['error'].get('message', data['error'])}"
            continue

        try:
            raw = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            last_error = f"Unexpected response structure from {model}: {e}"
            continue

        return _parse_json(raw)

    raise ValueError(
        f"All models failed. Last error: {last_error}. "
        "Check your OpenRouter balance at https://openrouter.ai/credits"
    )


# ── Main entry point ───────────────────────────────────────────────────────────

async def generate_exam_from_syllabus(
    syllabus_text: str,
    num_questions: int = 10,
    difficulty: str = "medium",
    question_types: str = "mixed",
    time_limit: int = 30,
    exam_title: Optional[str] = None,
    focus_topics: Optional[str] = None,
) -> dict:
    prompt = _build_prompt(
        syllabus_text, num_questions, difficulty,
        question_types, time_limit, exam_title, focus_topics,
    )
    return await _call_openrouter(prompt)
