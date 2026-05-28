"""
backend/services/ai_generator.py

AI-powered exam generation service.
Uses OpenRouter (free tier) → mistral-7b-instruct to generate exams from syllabus text.
Falls back to a rule-based generator if the LLM call fails or times out.

Environment variables (set in Render dashboard):
  OPENROUTER_API_KEY   — from https://openrouter.ai  (free, no credit card)
  TAVILY_API_KEY       — optional, for web-search mode (https://tavily.com)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import textwrap
from typing import Any, Optional

import httpx

# ── Optional: pypdf for server-side PDF fallback ─────────────────────────────
try:
    from pypdf import PdfReader
    import io as _io
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

# ── Optional: python-docx ──────────────────────────────────────────────────
try:
    import docx as _docx
    import io as _io2
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── API keys ──────────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
TAVILY_API_KEY: str     = os.getenv("TAVILY_API_KEY", "")

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Fast, free model on OpenRouter — swap for any model you prefer
_LLM_MODEL      = "mistralai/mistral-7b-instruct"

# Hard timeout for the LLM HTTP call (seconds)
_LLM_TIMEOUT = 90


# ══════════════════════════════════════════════════════════════════════════════
# Text extraction
# ══════════════════════════════════════════════════════════════════════════════

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from PDF, DOCX, or TXT bytes.
    PDF extraction is handled browser-side in SyllabusUpload.jsx (pdfjs),
    so by the time we receive a PDF it arrives as extracted text in a .txt blob.
    This function is a safety net for direct API calls.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"

    if ext == "txt":
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return file_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="replace")

    if ext == "pdf":
        if _PYPDF_AVAILABLE:
            try:
                reader = PdfReader(_io.BytesIO(file_bytes))
                pages = [page.extract_text() or "" for page in reader.pages[:60]]
                return "\n".join(pages)
            except Exception as exc:
                logger.warning("pypdf extraction failed: %s", exc)
        return file_bytes.decode("utf-8", errors="replace")

    if ext in ("docx", "doc"):
        if _DOCX_AVAILABLE:
            try:
                doc = _docx.Document(_io2.BytesIO(file_bytes))
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception as exc:
                logger.warning("python-docx extraction failed: %s", exc)
        return file_bytes.decode("utf-8", errors="replace")

    return file_bytes.decode("utf-8", errors="replace")


# ══════════════════════════════════════════════════════════════════════════════
# LLM call helper
# ══════════════════════════════════════════════════════════════════════════════

async def _call_llm(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """
    Call OpenRouter chat completions endpoint.
    Returns the assistant message text, or raises on error/timeout.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Add it in Render → Environment → OPENROUTER_API_KEY. "
            "Get a free key at https://openrouter.ai"
        )

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model":      _LLM_MODEL,
        "messages":   messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    headers = {
        "Authorization":  f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type":   "application/json",
        "HTTP-Referer":   "https://exam-verse-nine.vercel.app",
        "X-Title":        "ExamVerse",
    }

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        resp = await client.post(_OPENROUTER_URL, json=payload, headers=headers)

    if resp.status_code != 200:
        body = resp.text[:400]
        raise RuntimeError(
            f"OpenRouter returned HTTP {resp.status_code}: {body}"
        )

    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ══════════════════════════════════════════════════════════════════════════════
# JSON extraction from LLM response
# ══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Any:
    """
    Extract the first valid JSON object/array from an LLM response.
    LLMs often wrap JSON in markdown code fences — strip them first.
    """
    # Strip ```json ... ``` or ``` ... ```
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first { ... } or [ ... ] block
    for pattern in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in LLM response. Preview: {text[:300]}")


# ══════════════════════════════════════════════════════════════════════════════
# Prompt builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_prompt(
    content: str,
    num_questions: int,
    difficulty: str,
    question_types: str,
    time_limit: int,
    exam_title: Optional[str],
    focus_topics: Optional[str],
) -> str:
    title_hint    = f'Use "{exam_title}" as the exam title.' if exam_title else "Infer a suitable exam title."
    focus_hint    = f"Focus especially on: {focus_topics}." if focus_topics else ""
    type_hint_map = {
        "mcq":        "all MCQ (single correct answer, 4 options each)",
        "true_false": "all True/False questions (2 options: True and False)",
        "short":      "all short-answer questions (no options needed)",
        "mixed":      "a mix of MCQ, True/False, and short-answer",
    }
    type_hint = type_hint_map.get(question_types, type_hint_map["mixed"])

    return textwrap.dedent(f"""
        You are an expert exam setter. Generate exactly {num_questions} questions from the content below.

        Rules:
        - Difficulty: {difficulty}
        - Question type: {type_hint}
        - {title_hint}
        - {focus_hint}
        - For MCQ: 4 options labelled (a)-(d), mark exactly one correct. Each option must be on its own line.
        - For True/False: options are exactly "True" and "False".
        - Short-answer: provide a model answer in the explanation field.
        - Each question must have a non-empty explanation (1-2 sentences).
        - Return ONLY a JSON object — no markdown, no preamble, no extra text.

        JSON schema:
        {{
          "title": "string",
          "description": "string",
          "duration_minutes": {time_limit},
          "total_marks": <sum of all marks>,
          "pass_percentage": 40,
          "negative_marking": false,
          "sections": [
            {{
              "title": "Section 1",
              "description": "",
              "questions": [
                {{
                  "text": "Question text here?",
                  "question_type": "mcq_single",
                  "marks": 1,
                  "explanation": "Because ...",
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
        }}

        For true_false questions use question_type "true_false".
        For short-answer questions use question_type "short_answer" with an empty options array.

        CONTENT TO USE:
        ---
        {content[:6000]}
        ---

        Return ONLY valid JSON. No markdown. No explanation outside the JSON.
    """).strip()


# ══════════════════════════════════════════════════════════════════════════════
# Result normaliser
# ══════════════════════════════════════════════════════════════════════════════

def _normalise_result(raw: dict, num_questions: int, time_limit: int) -> dict:
    """
    Ensure the parsed JSON has all required keys with correct types.
    Fixes common LLM quirks (missing keys, wrong is_correct placement, etc.)
    """
    sections = raw.get("sections") or []

    # Flatten then re-section if the LLM returned a flat questions list
    if not sections and raw.get("questions"):
        sections = [{"title": "General", "description": "", "questions": raw["questions"]}]

    clean_sections = []
    total_marks = 0

    for sec in sections:
        qs = sec.get("questions") or []
        clean_qs = []

        for q in qs:
            q_type   = q.get("question_type", "mcq_single")
            raw_opts = q.get("options") or []
            options  = []

            # Some LLMs put correct answer as a separate field instead of is_correct flag
            correct_answer_text = (q.get("correct_answer") or "").strip().lower()

            for opt in raw_opts:
                opt_text   = str(opt.get("text", "")).strip()
                is_correct = bool(opt.get("is_correct", False))

                # Fallback: match correct_answer field
                if not is_correct and correct_answer_text:
                    is_correct = opt_text.lower() == correct_answer_text or \
                                 opt_text.lower().startswith(correct_answer_text)

                options.append({
                    "text":       opt_text,
                    "is_correct": is_correct,
                })

            # If STILL no correct option flagged, mark the first one
            if options and not any(o["is_correct"] for o in options):
                options[0]["is_correct"] = True

            marks = float(q.get("marks", 1) or 1)
            total_marks += marks

            clean_qs.append({
                "text":          str(q.get("text", "Question")).strip(),
                "question_type": q_type,
                "marks":         marks,
                "explanation":   str(q.get("explanation", "") or ""),
                "options":       options,
            })

        clean_sections.append({
            "title":       str(sec.get("title", "Section")).strip() or "Section",
            "description": str(sec.get("description", "") or ""),
            "questions":   clean_qs,
        })

    # Build coverage report
    all_qs = [q for s in clean_sections for q in s["questions"]]
    coverage = {
        "total_topics_in_syllabus":  1,
        "topics_covered":            1,
        "topics_missing":            0,
        "coverage_percentage":       100,
        "total_questions":           len(all_qs),
        "question_distribution": {
            "by_type": {},
            "by_difficulty": {},
        },
        "weak_areas":   [],
        "queries_used": [],
        "source":       "llm",
    }

    return {
        "title":            str(raw.get("title", "Generated Exam") or "Generated Exam").strip(),
        "description":      str(raw.get("description", "") or ""),
        "duration_minutes": int(raw.get("duration_minutes", time_limit) or time_limit),
        "total_marks":      int(total_marks) or len(all_qs),
        "pass_percentage":  int(raw.get("pass_percentage", 40) or 40),
        "negative_marking": bool(raw.get("negative_marking", False)),
        "sections":         clean_sections,
        "coverage_report":  coverage,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Fallback rule-based generator (used when LLM is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

def _fallback_generate(
    content: str,
    num_questions: int,
    difficulty: str,
    time_limit: int,
    exam_title: Optional[str],
) -> dict:
    """
    Simple rule-based True/False question generator.
    Splits content into sentences and turns each into a T/F question.
    Not great quality, but never hangs and always returns.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]+', content) if len(s.strip()) > 30]
    questions = []

    for i, sent in enumerate(sentences[:num_questions]):
        questions.append({
            "text":          f"True or False: {sent}?",
            "question_type": "true_false",
            "marks":         1,
            "explanation":   "Based on the provided syllabus content.",
            "options": [
                {"text": "True",  "is_correct": True},
                {"text": "False", "is_correct": False},
            ],
        })

    # Pad if needed
    while len(questions) < num_questions:
        questions.append({
            "text":          f"Question {len(questions) + 1}: Review the syllabus content carefully.",
            "question_type": "true_false",
            "marks":         1,
            "explanation":   "Please review your syllabus notes.",
            "options": [
                {"text": "True",  "is_correct": True},
                {"text": "False", "is_correct": False},
            ],
        })

    return {
        "title":            exam_title or "Generated Exam",
        "description":      "Auto-generated exam",
        "duration_minutes": time_limit,
        "total_marks":      len(questions),
        "pass_percentage":  40,
        "negative_marking": False,
        "sections": [{"title": "General", "description": "", "questions": questions}],
        "coverage_report": {
            "total_topics_in_syllabus": 1,
            "topics_covered":           1,
            "topics_missing":           0,
            "coverage_percentage":      100,
            "total_questions":          len(questions),
            "question_distribution":    {"by_type": {}, "by_difficulty": {}},
            "weak_areas":               [],
            "source":                   "fallback",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

async def generate_exam_from_syllabus(
    syllabus_text:  str,
    num_questions:  int            = 10,
    difficulty:     str            = "mixed",
    question_types: str            = "mixed",
    time_limit:     int            = 30,
    exam_title:     Optional[str]  = None,
    focus_topics:   Optional[str]  = None,
) -> dict:
    """
    Generate a structured exam dict from syllabus text using an LLM.
    Falls back to rule-based generation if LLM is unavailable.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("No OPENROUTER_API_KEY — using fallback generator")
        return _fallback_generate(syllabus_text, num_questions, difficulty, time_limit, exam_title)

    prompt = _build_prompt(
        content        = syllabus_text,
        num_questions  = num_questions,
        difficulty     = difficulty,
        question_types = question_types,
        time_limit     = time_limit,
        exam_title     = exam_title,
        focus_topics   = focus_topics,
    )

    try:
        raw_text = await _call_llm(
            prompt    = prompt,
            system    = "You are an expert exam setter. You ONLY output valid JSON. Never output anything except a JSON object.",
            max_tokens= 4096,
        )
        raw_json = _extract_json(raw_text)
        return _normalise_result(raw_json, num_questions, time_limit)

    except Exception as exc:
        logger.error("LLM generation failed, using fallback: %s", exc)
        return _fallback_generate(syllabus_text, num_questions, difficulty, time_limit, exam_title)


async def generate_exam_from_search(
    topics:         list[str],
    num_questions:  int            = 10,
    difficulty:     str            = "mixed",
    question_types: str            = "mixed",
    time_limit:     int            = 30,
    exam_title:     Optional[str]  = None,
    focus_topics:   Optional[str]  = None,
    extra_context:  str            = "",
) -> dict:
    """
    Generate an exam by optionally fetching web content for the topics,
    then running the LLM generator on the combined text.
    """
    combined_text = ""

    # ── Try Tavily web search ──────────────────────────────────────────────
    if TAVILY_API_KEY and topics:
        try:
            query = ", ".join(topics[:5])
            if extra_context:
                query += f" {extra_context}"

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 5},
                    headers={"Content-Type": "application/json"},
                )

            if resp.status_code == 200:
                results = resp.json().get("results", [])
                combined_text = "\n\n".join(
                    f"{r.get('title', '')}\n{r.get('content', '')}"
                    for r in results
                )
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)

    # ── Fall back to topic list as content ─────────────────────────────────
    if not combined_text:
        combined_text = (
            f"Topics: {', '.join(topics)}\n"
            f"Extra context: {extra_context}\n\n"
            "Generate questions based on your knowledge of these topics. "
            "Ensure questions are factually accurate and educationally relevant."
        )

    title = exam_title or f"{', '.join(topics[:2])} Exam"

    return await generate_exam_from_syllabus(
        syllabus_text  = combined_text,
        num_questions  = num_questions,
        difficulty     = difficulty,
        question_types = question_types,
        time_limit     = time_limit,
        exam_title     = title,
        focus_topics   = focus_topics,
    )
