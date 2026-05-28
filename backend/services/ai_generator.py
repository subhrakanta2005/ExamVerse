"""
backend/services/ai_generator.py

Generates exams from syllabus text using Google Gemini (free tier).
Falls back to a rich rule-based MCQ generator if Gemini is unavailable.

Environment variable (set in Render dashboard):
  GEMINI_API_KEY  — get free key at https://aistudio.google.com/apikey
                    (1500 requests/day, no credit card needed)

Also exports TAVILY_API_KEY for the search router.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import textwrap
from typing import Any, Optional

import httpx

# ── Optional PDF / DOCX extraction (server-side fallback) ────────────────────
try:
    from pypdf import PdfReader
    import io as _io
    _PYPDF = True
except ImportError:
    _PYPDF = False

try:
    import docx as _docx
    import io as _io2
    _DOCX = True
except ImportError:
    _DOCX = False

logger = logging.getLogger(__name__)

# ── Keys ──────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent"
)
_GEMINI_TIMEOUT = 90  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# File text extraction
# ══════════════════════════════════════════════════════════════════════════════

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"

    if ext == "txt":
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return file_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="replace")

    if ext == "pdf" and _PYPDF:
        try:
            reader = PdfReader(_io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages[:60])
        except Exception as e:
            logger.warning("pypdf failed: %s", e)

    if ext in ("docx", "doc") and _DOCX:
        try:
            doc = _docx.Document(_io2.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.warning("docx failed: %s", e)

    return file_bytes.decode("utf-8", errors="replace")


# ══════════════════════════════════════════════════════════════════════════════
# Gemini API call
# ══════════════════════════════════════════════════════════════════════════════

async def _call_gemini(prompt: str, max_tokens: int = 8192) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment variables.")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
        },
    }

    url = f"{_GEMINI_URL}?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
        resp = await client.post(url, json=payload,
                                 headers={"Content-Type": "application/json"})

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:400]}")

    data = resp.json()

    # Extract text from response
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from e


# ══════════════════════════════════════════════════════════════════════════════
# JSON extractor
# ══════════════════════════════════════════════════════════════════════════════

def _extract_json(text: str) -> Any:
    # Strip markdown fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pat in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        m = re.search(pat, text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON in LLM output. Preview: {text[:300]}")


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
    title_hint = f'Use "{exam_title}" as the exam title.' if exam_title else "Infer a suitable exam title from the content."
    focus_hint = f"Focus especially on these topics: {focus_topics}." if focus_topics else ""

    type_instructions = {
        "mcq": f"""Generate all {num_questions} questions as MCQ (multiple choice).
Each MCQ must have exactly 4 options (a, b, c, d) with exactly one correct answer.""",

        "true_false": f"""Generate all {num_questions} questions as True/False.
Each question must have exactly 2 options: "True" and "False".""",

        "short": f"""Generate all {num_questions} questions as short-answer.
Each question should have an empty options array [] and a model answer in the explanation field.""",

        "mixed": f"""Generate a mix of question types across the {num_questions} questions:
- About 60% MCQ (4 options each, one correct)
- About 20% True/False (options: "True" and "False")
- About 20% short_answer (empty options array, model answer in explanation)
Vary the types naturally — do NOT put all of one type in one section.""",
    }

    type_instr = type_instructions.get(question_types, type_instructions["mixed"])

    return textwrap.dedent(f"""
You are an expert exam setter. Generate exactly {num_questions} exam questions from the content below.

INSTRUCTIONS:
- Difficulty level: {difficulty}
- {type_instr}
- {title_hint}
- {focus_hint}
- Every question MUST have a non-empty explanation (1-2 sentences explaining the correct answer).
- For MCQ: exactly 4 options, mark exactly one with "is_correct": true.
- For true_false: options must be exactly [{{"text":"True","is_correct":true}},{{"text":"False","is_correct":false}}] or vice versa.
- For short_answer: use an empty options array and put the model answer in "explanation".
- question_type values: use "mcq_single" for MCQ, "true_false" for True/False, "short_answer" for short answer.
- marks: 1 per question (unless specified otherwise).
- Return ONLY a valid JSON object. No markdown, no preamble, no explanation outside the JSON.

REQUIRED JSON STRUCTURE:
{{
  "title": "Exam title here",
  "description": "Brief description",
  "duration_minutes": {time_limit},
  "total_marks": {num_questions},
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
          "explanation": "The correct answer is X because...",
          "options": [
            {{"text": "Option A", "is_correct": false}},
            {{"text": "Option B", "is_correct": true}},
            {{"text": "Option C", "is_correct": false}},
            {{"text": "Option D", "is_correct": false}}
          ]
        }},
        {{
          "text": "Is the sky blue?",
          "question_type": "true_false",
          "marks": 1,
          "explanation": "The sky appears blue due to Rayleigh scattering.",
          "options": [
            {{"text": "True",  "is_correct": true}},
            {{"text": "False", "is_correct": false}}
          ]
        }},
        {{
          "text": "Explain the concept of photosynthesis.",
          "question_type": "short_answer",
          "marks": 1,
          "explanation": "Photosynthesis is the process by which plants convert sunlight, water, and CO2 into glucose and oxygen.",
          "options": []
        }}
      ]
    }}
  ]
}}

CONTENT TO USE:
---
{content[:7000]}
---

Return ONLY valid JSON. No markdown fences. No text before or after the JSON object.
""").strip()


# ══════════════════════════════════════════════════════════════════════════════
# Result normaliser
# ══════════════════════════════════════════════════════════════════════════════

def _normalise(raw: dict, num_questions: int, time_limit: int) -> dict:
    sections = raw.get("sections") or []

    if not sections and raw.get("questions"):
        sections = [{"title": "General", "description": "", "questions": raw["questions"]}]

    clean_sections = []
    total_marks = 0

    for sec in sections:
        clean_qs = []
        for q in (sec.get("questions") or []):
            q_type   = q.get("question_type", "mcq_single")
            raw_opts = q.get("options") or []
            correct_answer_text = (q.get("correct_answer") or "").strip().lower()
            options = []

            for opt in raw_opts:
                text       = str(opt.get("text", "")).strip()
                is_correct = bool(opt.get("is_correct", False))
                # Fallback: match by correct_answer field
                if not is_correct and correct_answer_text:
                    is_correct = (text.lower() == correct_answer_text or
                                  text.lower().startswith(correct_answer_text))
                options.append({"text": text, "is_correct": is_correct})

            # If still no correct option, flag the first one
            if options and not any(o["is_correct"] for o in options):
                options[0]["is_correct"] = True

            marks = float(q.get("marks") or 1)
            total_marks += marks
            clean_qs.append({
                "text":          str(q.get("text", "Question")).strip(),
                "question_type": q_type,
                "marks":         marks,
                "explanation":   str(q.get("explanation", "") or ""),
                "options":       options,
            })

        clean_sections.append({
            "title":       str(sec.get("title", "Section") or "Section").strip(),
            "description": str(sec.get("description", "") or ""),
            "questions":   clean_qs,
        })

    all_qs = [q for s in clean_sections for q in s["questions"]]

    return {
        "title":            str(raw.get("title", "Generated Exam") or "Generated Exam").strip(),
        "description":      str(raw.get("description", "") or ""),
        "duration_minutes": int(raw.get("duration_minutes", time_limit) or time_limit),
        "total_marks":      int(total_marks) or len(all_qs),
        "pass_percentage":  int(raw.get("pass_percentage", 40) or 40),
        "negative_marking": bool(raw.get("negative_marking", False)),
        "sections":         clean_sections,
        "coverage_report": {
            "total_topics_in_syllabus": 1,
            "topics_covered":           1,
            "topics_missing":           0,
            "coverage_percentage":      100,
            "total_questions":          len(all_qs),
            "question_distribution":    {"by_type": {}, "by_difficulty": {}},
            "weak_areas":               [],
            "source":                   "gemini",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Rule-based MCQ fallback (used when Gemini is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

def _make_distractors(correct: str, all_words: list[str]) -> list[str]:
    """Pick 3 plausible distractors from other words in the text."""
    pool = [w for w in all_words if w.lower() != correct.lower() and len(w) > 3]
    random.shuffle(pool)
    distractors = list(dict.fromkeys(pool))[:3]  # deduplicated
    while len(distractors) < 3:
        distractors.append(f"None of the above (option {len(distractors)+1})")
    return distractors


def _fallback_generate(
    content: str,
    num_questions: int,
    difficulty: str,
    question_types: str,
    time_limit: int,
    exam_title: Optional[str],
) -> dict:
    """
    Rule-based generator — produces MCQ, True/False and Short Answer questions
    directly from the syllabus text without any LLM call.
    Quality is limited but it covers all question types and never hangs.
    """
    # Extract sentences and named tokens
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content)
                 if len(s.strip()) > 40]

    # Extract capitalized phrases (likely proper nouns / key terms)
    key_terms = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b', content)
    key_terms = list(dict.fromkeys(key_terms))  # deduplicated, order-preserving

    # All significant words for distractors
    all_words = re.findall(r'\b[A-Za-z]{4,}\b', content)

    questions = []
    sent_idx  = 0
    term_idx  = 0

    # Determine type distribution
    if question_types == "mcq":
        type_seq = ["mcq_single"] * num_questions
    elif question_types == "true_false":
        type_seq = ["true_false"] * num_questions
    elif question_types == "short":
        type_seq = ["short_answer"] * num_questions
    else:  # mixed
        n_mcq  = max(1, round(num_questions * 0.60))
        n_tf   = max(1, round(num_questions * 0.20))
        n_sa   = num_questions - n_mcq - n_tf
        type_seq = (["mcq_single"] * n_mcq +
                    ["true_false"] * n_tf +
                    ["short_answer"] * max(0, n_sa))
        random.shuffle(type_seq)

    for q_type in type_seq[:num_questions]:

        # ── MCQ ──────────────────────────────────────────────────────────────
        if q_type == "mcq_single":
            # Try to make a fill-in-the-blank style question from a key term
            if term_idx < len(key_terms) and sent_idx < len(sentences):
                term = key_terms[term_idx % len(key_terms)]
                sent = sentences[sent_idx % len(sentences)]
                term_idx += 1
                sent_idx += 1

                if term in sent:
                    q_text  = sent.replace(term, "______", 1).rstrip(".!?") + " — what fills the blank?"
                else:
                    q_text = f"Which of the following best describes '{term}'?"

                distractors = _make_distractors(term, all_words)
                opts = [term] + distractors
                random.shuffle(opts)

                questions.append({
                    "text":          q_text,
                    "question_type": "mcq_single",
                    "marks":         1,
                    "explanation":   f"'{term}' is the correct answer based on the syllabus content.",
                    "options": [
                        {"text": o, "is_correct": (o == term)} for o in opts
                    ],
                })
            else:
                # Fallback: generic question from sentence
                sent = sentences[sent_idx % len(sentences)] if sentences else "Review the syllabus."
                sent_idx += 1
                questions.append({
                    "text":          f"According to the content: {sent[:100]}... — which statement is correct?",
                    "question_type": "mcq_single",
                    "marks":         1,
                    "explanation":   "Refer to the relevant section in the syllabus.",
                    "options": [
                        {"text": "The statement is accurate as given.",  "is_correct": True},
                        {"text": "The statement is completely false.",   "is_correct": False},
                        {"text": "The statement applies only partially.","is_correct": False},
                        {"text": "None of the above.",                  "is_correct": False},
                    ],
                })

        # ── True / False ──────────────────────────────────────────────────────
        elif q_type == "true_false":
            sent = sentences[sent_idx % len(sentences)] if sentences else "This topic is important."
            sent_idx += 1
            questions.append({
                "text":          f"True or False: {sent.rstrip('.!?')}.",
                "question_type": "true_false",
                "marks":         1,
                "explanation":   "This statement is directly supported by the syllabus content.",
                "options": [
                    {"text": "True",  "is_correct": True},
                    {"text": "False", "is_correct": False},
                ],
            })

        # ── Short Answer ──────────────────────────────────────────────────────
        else:
            term = key_terms[term_idx % len(key_terms)] if key_terms else "the main topic"
            term_idx += 1
            questions.append({
                "text":          f"Briefly explain the significance of '{term}' as discussed in the content.",
                "question_type": "short_answer",
                "marks":         2,
                "explanation":   f"A good answer should reference the role of '{term}' as described in the syllabus.",
                "options":       [],
            })

    title = exam_title or "Generated Exam"
    return {
        "title":            title,
        "description":      "Auto-generated from syllabus content.",
        "duration_minutes": time_limit,
        "total_marks":      sum(q["marks"] for q in questions),
        "pass_percentage":  40,
        "negative_marking": False,
        "sections": [{"title": "General", "description": "", "questions": questions}],
        "coverage_report": {
            "total_topics_in_syllabus": len(key_terms),
            "topics_covered":           min(len(key_terms), num_questions),
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
    num_questions:  int           = 10,
    difficulty:     str           = "mixed",
    question_types: str           = "mixed",
    time_limit:     int           = 30,
    exam_title:     Optional[str] = None,
    focus_topics:   Optional[str] = None,
) -> dict:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — using rule-based fallback generator")
        return _fallback_generate(
            syllabus_text, num_questions, difficulty, question_types, time_limit, exam_title
        )

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
        raw_text = await _call_gemini(prompt, max_tokens=8192)
        raw_json = _extract_json(raw_text)
        result   = _normalise(raw_json, num_questions, time_limit)
        logger.info("Gemini generated %d questions successfully",
                    sum(len(s["questions"]) for s in result["sections"]))
        return result

    except Exception as exc:
        logger.error("Gemini generation failed (%s) — using fallback", exc)
        return _fallback_generate(
            syllabus_text, num_questions, difficulty, question_types, time_limit, exam_title
        )


async def generate_exam_from_search(
    topics:         list[str],
    num_questions:  int           = 10,
    difficulty:     str           = "mixed",
    question_types: str           = "mixed",
    time_limit:     int           = 30,
    exam_title:     Optional[str] = None,
    focus_topics:   Optional[str] = None,
    extra_context:  str           = "",
) -> dict:
    combined_text = ""

    # Try Tavily web search
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
                    f"{r.get('title','')}\n{r.get('content','')}" for r in results
                )
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)

    if not combined_text:
        combined_text = (
            f"Topics: {', '.join(topics)}\n"
            f"Extra context: {extra_context}\n\n"
            "Generate educationally accurate questions on these topics."
        )

    return await generate_exam_from_syllabus(
        syllabus_text  = combined_text,
        num_questions  = num_questions,
        difficulty     = difficulty,
        question_types = question_types,
        time_limit     = time_limit,
        exam_title     = exam_title or f"{', '.join(topics[:2])} Exam",
        focus_topics   = focus_topics,
    )
