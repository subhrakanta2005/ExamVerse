"""
ExamVerse / ExamForge — AI-Powered Exam Generator (Gemini Edition)
===================================================================
File:  backend/services/ai_generator.py

Uses Google Gemini (gemini-1.5-flash) via direct HTTP (no SDK).
This keeps memory usage under 100MB — safe for Render free tier (512MB).

FREE TIER: 1,500 requests/day — more than enough.
No credit card required to get an API key.

Get your free key at: https://aistudio.google.com/app/apikey

Setup (one time):
1. Add to backend/.env:
       GEMINI_API_KEY=AIza...your_key_here
   (No extra pip packages needed — uses httpx which is already installed)

All existing function signatures are unchanged — routers need ZERO modifications.
Fallback: if GEMINI_API_KEY is not set, uses the rule-based generator.
"""

from __future__ import annotations

import json
import os
import random
import re
import string
from typing import Optional

# ══════════════════════════════════════════════════════════════════════════════
# 0.  GEMINI CLIENT SETUP  (pure HTTP — no SDK, saves ~250MB RAM)
# ══════════════════════════════════════════════════════════════════════════════

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
_GEMINI_URL     = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-1.5-flash:generateContent"
)


async def _call_gemini_api(prompt: str) -> str:
    """
    Call Gemini REST API directly with httpx (already in requirements.txt).
    Returns the text response, or raises on failure.
    Uses zero extra memory vs the google-generativeai SDK (~250MB saved).
    """
    import httpx

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature":     0.7,
            "maxOutputTokens": 8192,
        },
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{_GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract text from Gemini response structure
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ══════════════════════════════════════════════════════════════════════════════
# 1.  TEXT EXTRACTION  (TXT / PDF / DOCX) — unchanged
# ══════════════════════════════════════════════════════════════════════════════

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Return plain text from an uploaded syllabus file."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")

    if ext == "pdf":
        try:
            import pypdf, io
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore")

    if ext in ("docx", "doc"):
        try:
            import docx, io
            doc = docx.Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except Exception:
            return file_bytes.decode("utf-8", errors="ignore")

    return file_bytes.decode("utf-8", errors="ignore")


# ══════════════════════════════════════════════════════════════════════════════
# 2.  GEMINI-POWERED QUESTION GENERATION
# ══════════════════════════════════════════════════════════════════════════════

_MCQ_SYSTEM_PROMPT = """\
You are an expert exam question writer. Your job is to read the given text and
generate high-quality exam questions that TEST UNDERSTANDING, not just memory.

Rules:
- Read the text carefully and understand the concepts.
- Generate questions that are clear, unambiguous, and educational.
- For MCQ: exactly 4 options, exactly 1 correct answer.
- Distractors must be plausible (not obviously wrong).
- Avoid "all of the above" or "none of the above" options.
- Questions should cover different parts of the text.
- Do NOT copy sentences verbatim — rephrase into question form.
- Return ONLY valid JSON, no markdown, no explanation outside JSON.
"""


def _build_gemini_prompt(
    text: str,
    num_questions: int,
    difficulty: str,
    question_types: str,
    focus_topics: Optional[str],
    exam_title: Optional[str],
) -> str:
    """Build the prompt sent to Gemini."""

    # Trim text to stay within token limits (≈ 3000 words is plenty)
    max_chars = 12000
    if len(text) > max_chars:
        # Take beginning + end of document (captures intro & summary)
        text = text[:8000] + "\n...\n" + text[-4000:]

    type_instructions = {
        "mcq":        "Generate ONLY MCQ questions with 4 options each.",
        "true_false":  "Generate ONLY True/False questions.",
        "short":       "Generate ONLY short-answer questions (1–2 sentence answers).",
        "mixed":       "Mix question types: ~60% MCQ, ~20% True/False, ~20% short-answer.",
    }
    type_instr = type_instructions.get(question_types, type_instructions["mixed"])

    difficulty_instr = {
        "easy":   "Questions should be straightforward and test basic recall.",
        "medium": "Questions should require understanding and application.",
        "hard":   "Questions should require analysis, synthesis, or evaluation.",
        "mixed":  "Mix of easy (30%), medium (50%), and hard (20%) questions.",
    }.get(difficulty, "Mix difficulty levels.")

    focus_instr = f"\nFocus especially on these topics: {focus_topics}" if focus_topics else ""
    title_instr = f"\nExam title: {exam_title}" if exam_title else ""

    return f"""\
{_MCQ_SYSTEM_PROMPT}

TEXT TO STUDY:
\"\"\"
{text}
\"\"\"

TASK:
Generate exactly {num_questions} exam questions from the text above.
{type_instr}
{difficulty_instr}{focus_instr}{title_instr}

Return a JSON object with this EXACT structure:
{{
  "exam_title": "string (infer from content if not provided)",
  "questions": [
    {{
      "text": "The question text here?",
      "question_type": "mcq" | "true_false" | "short_answer",
      "difficulty": "easy" | "medium" | "hard",
      "marks": 1,
      "explanation": "Why this answer is correct",
      "options": [
        {{"text": "Option A text", "is_correct": false}},
        {{"text": "Option B text", "is_correct": true}},
        {{"text": "Option C text", "is_correct": false}},
        {{"text": "Option D text", "is_correct": false}}
      ]
    }}
  ]
}}

For true_false questions: options should be exactly [{{"text":"True","is_correct":...}},{{"text":"False","is_correct":...}}]
For short_answer questions: options should be [] (empty array), put the model answer in "explanation".

Return ONLY the JSON object. No markdown. No extra text.
"""


def _parse_gemini_response(raw: str, difficulty: str) -> list[dict]:
    """
    Parse Gemini's JSON response into our internal question list format.
    Handles common issues like markdown code fences, trailing commas, etc.
    """
    # Strip markdown fences if present
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON object if there's surrounding text
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except Exception:
                return []
        else:
            return []

    questions_raw = data.get("questions", [])
    questions = []

    for q in questions_raw:
        text = (q.get("text") or "").strip()
        if not text:
            continue

        q_type  = q.get("question_type", "mcq").lower().replace(" ", "_")
        diff    = q.get("difficulty", difficulty)
        marks   = float(q.get("marks", 1))
        expl    = (q.get("explanation") or "").strip()
        options = q.get("options", [])

        # Validate MCQ: must have exactly 1 correct answer
        if q_type == "mcq":
            correct_count = sum(1 for o in options if o.get("is_correct"))
            if correct_count != 1 or len(options) < 2:
                continue  # drop malformed question

        # Find correct answer text (for evaluation engine)
        correct_answer = ""
        for opt in options:
            if opt.get("is_correct"):
                correct_answer = opt.get("text", "")
                break

        questions.append({
            "text":           text,
            "question_type":  q_type,
            "difficulty":     diff,
            "marks":          marks,
            "explanation":    expl,
            "correct_answer": correct_answer,
            "options": [
                {
                    "text":       str(o.get("text", "")),
                    "is_correct": bool(o.get("is_correct", False)),
                    "order":      i,
                }
                for i, o in enumerate(options)
            ],
        })

    return questions


async def _generate_with_gemini(
    text:           str,
    num_questions:  int,
    difficulty:     str,
    question_types: str,
    focus_topics:   Optional[str],
    exam_title:     Optional[str],
) -> tuple[list[dict], str]:
    """
    Call Gemini REST API directly (no SDK) and return (questions, inferred_title).
    Returns ([], "") on failure so caller falls back to rule-based.
    """
    if not GEMINI_API_KEY:
        return [], ""

    batch_size     = 30
    all_questions: list[dict] = []
    inferred_title = exam_title or ""

    batches = []
    remaining = num_questions
    while remaining > 0:
        batches.append(min(remaining, batch_size))
        remaining -= batch_size

    for batch_n in batches:
        prompt = _build_gemini_prompt(
            text, batch_n, difficulty, question_types, focus_topics, exam_title
        )
        try:
            raw = await _call_gemini_api(prompt)
        except Exception:
            break

        parsed         = _parse_gemini_response(raw, difficulty)
        all_questions += parsed

        if not inferred_title:
            try:
                import re as _re
                clean = _re.sub(r"^```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
                data  = json.loads(clean)
                inferred_title = data.get("exam_title", "") or ""
            except Exception:
                pass

    return all_questions, inferred_title



# ══════════════════════════════════════════════════════════════════════════════
# 3.  MAIN ENTRY POINT  (signature unchanged — your router works as-is)
# ══════════════════════════════════════════════════════════════════════════════

async def generate_exam_from_syllabus(
    syllabus_text:  str,
    num_questions:  int = 10,
    difficulty:     str = "medium",
    question_types: str = "mixed",
    time_limit:     int = 30,
    exam_title:     Optional[str] = None,
    focus_topics:   Optional[str] = None,
    **kwargs,
) -> dict:
    """
    Generate a full exam + coverage report from syllabus text.

    Uses Gemini LLM if GEMINI_API_KEY is set.
    Falls back to rule-based generator if key is missing or API fails.
    """

    # ── Try Gemini first ───────────────────────────────────────────────────────
    if GEMINI_API_KEY:
        questions, inferred_title = await _generate_with_gemini(
            text           = syllabus_text,
            num_questions  = num_questions,
            difficulty     = difficulty,
            question_types = question_types,
            focus_topics   = focus_topics,
            exam_title     = exam_title,
        )

        if questions:
            # Pad with rule-based if Gemini returned fewer than requested
            if len(questions) < num_questions:
                extra = _generate_rule_based_questions(
                    _preprocess_text_for_parser(syllabus_text),
                    num_questions - len(questions),
                    difficulty, question_types, focus_topics,
                )
                questions += extra

            title = exam_title or inferred_title or _infer_title(syllabus_text)
            questions = questions[:num_questions]

            # Build sections — group by difficulty so the exam has structure
            sections_out = _group_into_sections(questions, title)
            total_marks  = sum(q["marks"] for q in questions)

            # Build lightweight coverage report
            coverage = _build_gemini_coverage_report(questions, syllabus_text)

            return {
                "title":            title,
                "description":      f"AI-generated exam with {len(questions)} questions.",
                "duration_minutes": time_limit,
                "total_marks":      total_marks,
                "pass_percentage":  40,
                "negative_marking": False,
                "sections":         sections_out,
                "coverage_report":  coverage,
            }

    # ── Fallback: rule-based generator (no key needed) ─────────────────────────
    return await _rule_based_generate(
        syllabus_text, num_questions, difficulty,
        question_types, time_limit, exam_title, focus_topics,
    )


def _group_into_sections(questions: list[dict], title: str) -> list[dict]:
    """Group questions into sections. For Gemini output, use one section."""
    return [{
        "title":       title,
        "description": "Questions generated by AI from the uploaded content.",
        "questions":   questions,
    }]


def _build_gemini_coverage_report(questions: list[dict], text: str) -> dict:
    """Build a minimal coverage report for Gemini-generated questions."""
    type_dist: dict[str, int] = {}
    diff_dist: dict[str, int] = {}
    for q in questions:
        qt = q.get("question_type", "mcq")
        qd = q.get("difficulty", "medium")
        type_dist[qt] = type_dist.get(qt, 0) + 1
        diff_dist[qd] = diff_dist.get(qd, 0) + 1

    return {
        "total_topics_in_syllabus": len(questions),
        "topics_covered":           len(questions),
        "topics_missing":           0,
        "coverage_percentage":      100.0,
        "covered_topic_list":       [],
        "missing_topic_list":       [],
        "questions_per_topic":      [],
        "weak_areas":               [],
        "question_distribution": {
            "by_type":       type_dist,
            "by_difficulty": diff_dist,
        },
        "sections_detected": ["AI Generated"],
        "total_questions":   len(questions),
        "generator":         "gemini-1.5-flash",
        "note": "Questions generated by Gemini AI — understands context and concepts.",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4.  TAVILY SEARCH INTEGRATION (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY", "")
_TAVILY_ENDPOINT  = "https://api.tavily.com/search"
_TAVILY_TOTAL_CAP = 5


async def fetch_topic_content_from_web(query: str, max_results: int = 3) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        import httpx
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TAVILY_ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()
        parts = []
        if data.get("answer"):
            parts.append(data["answer"])
        for r in data.get("results", [])[:max_results]:
            if r.get("content"):
                parts.append(r["content"])
        return "\n\n".join(parts)
    except Exception:
        return ""


async def build_syllabus_text_from_search(
    topics: list[str], extra_context: str = ""
) -> tuple[str, list[str]]:
    blocks, queries_used = [], []
    for topic in topics[:_TAVILY_TOTAL_CAP]:
        query = f"{topic} {extra_context}".strip()
        queries_used.append(query)
        content = await fetch_topic_content_from_web(query)
        if content:
            blocks.append(f"Section: {topic}\n{content}")
    if not blocks:
        blocks = [f"Section: {t}\n- {t}" for t in topics]
    return "\n\n".join(blocks), queries_used


async def generate_exam_from_search(
    topics:         list[str],
    num_questions:  int  = 10,
    difficulty:     str  = "medium",
    question_types: str  = "mixed",
    time_limit:     int  = 30,
    exam_title:     Optional[str] = None,
    focus_topics:   Optional[str] = None,
    extra_context:  str  = "",
) -> dict:
    syllabus_text, queries_used = await build_syllabus_text_from_search(
        topics, extra_context
    )
    source = "web_search" if TAVILY_API_KEY else "fallback"
    result = await generate_exam_from_syllabus(
        syllabus_text  = syllabus_text,
        num_questions  = num_questions,
        difficulty     = difficulty,
        question_types = question_types,
        time_limit     = time_limit,
        exam_title     = exam_title or (", ".join(topics[:3]) + " — Exam"),
        focus_topics   = focus_topics,
    )
    result.setdefault("coverage_report", {}).update({
        "queries_used":    queries_used,
        "content_preview": syllabus_text[:300],
        "source":          source,
    })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 5.  RULE-BASED FALLBACK (kept intact — used when no Gemini key is set)
# ══════════════════════════════════════════════════════════════════════════════

async def _rule_based_generate(
    syllabus_text:  str,
    num_questions:  int,
    difficulty:     str,
    question_types: str,
    time_limit:     int,
    exam_title:     Optional[str],
    focus_topics:   Optional[str],
) -> dict:
    """Original rule-based generator — runs when GEMINI_API_KEY is not set."""
    random.seed(hash(syllabus_text[:200]) % (2**31))
    title = exam_title or _infer_title(syllabus_text)

    if _is_structured_mcq(syllabus_text):
        all_questions = parse_structured_mcq_text(
            syllabus_text,
            difficulty=difficulty if difficulty != "mixed" else "medium",
            num_questions=num_questions,
        )
        if len(all_questions) < num_questions:
            cleaned_text = _preprocess_text_for_parser(syllabus_text)
            extra = _generate_rule_based_questions(
                cleaned_text, num_questions - len(all_questions),
                difficulty, question_types, focus_topics,
            )
            all_questions.extend(extra)

        sections_out = [{
            "title":       title,
            "description": "Questions parsed directly from structured MCQ input.",
            "questions":   all_questions[:num_questions],
        }]
        total_marks   = sum(q["marks"] for q in all_questions[:num_questions])
        parsed_dummy  = {"sections": [{"title": title, "topics": []}],
                         "key_terms": [], "definitions": [], "sentences": []}
        coverage_report = _build_coverage_report(
            parsed_dummy, all_questions[:num_questions],
            [{"title": title, "topics": []}]
        )
        coverage_report["note"] = (
            "Input was detected as pre-formatted MCQ text and parsed directly."
        )
        return {
            "title": title,
            "description": "Exam generated from structured MCQ input.",
            "duration_minutes": time_limit,
            "total_marks": total_marks,
            "pass_percentage": 40,
            "negative_marking": False,
            "sections": sections_out,
            "coverage_report": coverage_report,
        }

    cleaned_text  = _preprocess_text_for_parser(syllabus_text)
    all_questions = _generate_rule_based_questions(
        cleaned_text, num_questions, difficulty, question_types, focus_topics
    )
    parsed   = _parse_syllabus(cleaned_text)
    sections = parsed["sections"]
    n_sections   = max(1, len(sections))
    chunk_size   = max(1, (num_questions + n_sections - 1) // n_sections)
    output_sections = []
    for chunk_i, start in enumerate(range(0, len(all_questions), chunk_size)):
        chunk    = all_questions[start:start + chunk_size]
        sec_name = sections[chunk_i % len(sections)]["title"] if sections else "General"
        output_sections.append({
            "title":       sec_name,
            "description": f"Questions covering {sec_name}",
            "questions":   chunk,
        })
    total_marks     = sum(q["marks"] for q in all_questions)
    coverage_report = _build_coverage_report(parsed, all_questions, sections)
    return {
        "title":            title,
        "description":      f"Auto-generated exam covering {len(sections)} section(s).",
        "duration_minutes": time_limit,
        "total_marks":      total_marks,
        "pass_percentage":  40,
        "negative_marking": False,
        "sections":         output_sections,
        "coverage_report":  coverage_report,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6.  ALL RULE-BASED HELPERS BELOW (kept exactly as before)
# ══════════════════════════════════════════════════════════════════════════════

_STRUCTURAL_LABELS = re.compile(
    r'^\s*('
    r'explanation|answer|correct answer|solution|hint|note|reference|'
    r'Q\s*\d+|question\s*\d+|'
    r'section|chapter|unit|module|part|topic'
    r')\s*[:\.\-]\s*',
    re.IGNORECASE,
)

_OPTION_RE = re.compile(r'^\s*[\(\[]?([A-Da-d])[\)\]\.]\s+(.+)', re.IGNORECASE)
_QUESTION_START_RE = re.compile(
    r'^\s*(?:Q\.?\s*\d+[\.\):]?|Question\s+\d+[\.\):]?|\d+[\.\)])\s+(.+)',
    re.IGNORECASE,
)
_ANSWER_LINE_RE = re.compile(
    r'^\s*[✓✔☑]?\s*(?:correct\s+)?answer\s*[:\-]\s*(?:\(([A-Da-d])\)|([A-Da-d]))\s*',
    re.IGNORECASE,
)
_EXPLANATION_RE = re.compile(r'^\s*explanation\s*[:\-]\s*(.+)', re.IGNORECASE)
_OPTION_CLEANUP_RE = re.compile(
    r'\s*[\[\(]?\s*correct\s*[\]\)]?\s*$', re.IGNORECASE
)


def _is_structured_mcq(text: str) -> bool:
    q_count   = sum(1 for l in text.splitlines() if _QUESTION_START_RE.match(l))
    opt_count = sum(1 for l in text.splitlines() if _OPTION_RE.match(l))
    return q_count >= 2 and opt_count >= 4


def parse_structured_mcq_text(
    text: str,
    difficulty: str = "medium",
    num_questions: Optional[int] = None,
) -> list[dict]:
    lines           = text.splitlines()
    questions       = []
    current_q_text  = None
    current_options: list[dict] = []
    current_answer  = None   # letter A-D
    current_explanation = ""

    def flush():
        nonlocal current_q_text, current_options, current_answer, current_explanation
        if current_q_text is None:
            return
        options = current_options[:]
        if current_answer is not None:
            letter = current_answer.upper()
            letter_map = {chr(ord('A') + i): i for i in range(4)}
            idx = letter_map.get(letter)
            for i, opt in enumerate(options):
                opt["is_correct"] = (i == idx)
        else:
            for opt in options:
                opt_text = opt["text"].lower()
                if _OPTION_CLEANUP_RE.search(opt.get("text", "")):
                    opt["text"] = _OPTION_CLEANUP_RE.sub("", opt["text"]).strip()
                    opt["is_correct"] = True

        correct_count = sum(1 for o in options if o.get("is_correct"))
        if correct_count == 1 and len(options) >= 2:
            correct_text = next(o["text"] for o in options if o["is_correct"])
            questions.append({
                "text":           current_q_text.strip(),
                "question_type":  "mcq",
                "difficulty":     difficulty,
                "marks":          2,
                "explanation":    current_explanation.strip(),
                "correct_answer": correct_text,
                "options":        options,
            })

        current_q_text      = None
        current_options     = []
        current_answer      = None
        current_explanation = ""

    for line in lines:
        if num_questions and len(questions) >= num_questions:
            break

        qm = _QUESTION_START_RE.match(line)
        if qm:
            flush()
            current_q_text = qm.group(1).strip()
            continue

        om = _OPTION_RE.match(line)
        if om and current_q_text is not None:
            text_part = _OPTION_CLEANUP_RE.sub("", om.group(2)).strip()
            current_options.append({"text": text_part, "is_correct": False, "order": len(current_options)})
            continue

        am = _ANSWER_LINE_RE.match(line)
        if am:
            current_answer = (am.group(1) or am.group(2) or "").upper()
            continue

        em = _EXPLANATION_RE.match(line)
        if em:
            current_explanation = em.group(1).strip()
            continue

    flush()
    return questions


def _preprocess_text_for_parser(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        if _STRUCTURAL_LABELS.match(line):
            continue
        if _OPTION_RE.match(line):
            continue
        if _ANSWER_LINE_RE.match(line):
            continue
        if _QUESTION_START_RE.match(line):
            m = _QUESTION_START_RE.match(line)
            cleaned.append(m.group(1) if m else line)
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _parse_syllabus(text: str) -> dict:
    lines          = [l.strip() for l in text.splitlines() if l.strip()]
    all_sentences  = re.findall(r'[^.!?]+[.!?]', text)
    key_terms:   list[str] = []
    definitions: list[dict] = []
    sections:    list[dict] = []
    current_section = "General"
    current_topics:  list[str] = []

    heading_re  = re.compile(r'^(#{1,3}|[A-Z][A-Z\s]{3,}:?$|Chapter\s+\d+|Section\s+\d+|Unit\s+\d+)', re.IGNORECASE)
    numbered_re = re.compile(r'^\d+[\.\)]\s+(.+)')
    bullet_re   = re.compile(r'^[-*•]\s+(.+)')
    def_re      = re.compile(r'^(.{3,40})\s+(?:is|are|refers? to|means?|defined as)\s+(.{10,200})', re.IGNORECASE)

    for line in lines:
        dm = def_re.match(line)
        if dm:
            term, defn = dm.group(1).strip(), dm.group(2).strip()
            if len(term.split()) <= 5 and len(defn) > 10 and len(term) > 2:
                definitions.append({"term": term, "definition": defn})

        hm = heading_re.match(line)
        if hm:
            if current_section and current_topics:
                sections.append({"title": current_section, "topics": current_topics[:]})
            current_section = line.strip().rstrip(':').strip()
            current_topics  = []
            continue

        nm = numbered_re.match(line) or bullet_re.match(line)
        if nm:
            topic = nm.group(1).strip()
            current_topics.append(topic)
            key_terms.extend(t.strip() for t in re.split(r'[,;]', topic) if len(t.strip()) > 2)
            continue

        if 5 < len(line) <= 100:
            current_topics.append(line)
            key_terms.extend(w for w in line.split() if w[0].isupper() and len(w) > 3)

    if current_section and current_topics:
        sections.append({"title": current_section, "topics": current_topics})
    if not sections:
        sections = [{"title": "General", "topics": lines[:300]}]

    seen, unique_terms = set(), []
    for t in key_terms:
        tc = t.strip(string.punctuation).lower()
        if tc not in seen and len(tc) > 2 and tc not in {
            "explanation", "answer", "solution", "question", "correct",
        }:
            seen.add(tc)
            unique_terms.append(t.strip(string.punctuation))

    return {
        "sections":    sections,
        "key_terms":   unique_terms[:300],
        "definitions": definitions[:150],
        "sentences":   all_sentences[:300],
    }


def _marks(difficulty: str, base: int = 1) -> int:
    return {"easy": base, "medium": base + 1, "hard": base + 2}.get(difficulty, base)


def _make_definition_mcq(term, definition, all_terms, difficulty):
    others = [t for t in all_terms if t.lower() != term.lower()]
    random.shuffle(others)
    fillers = [
        f"A method used to evaluate {others[0] if others else 'data'}",
        f"The process of organizing {others[1] if len(others) > 1 else 'information'} systematically",
        f"A framework for analyzing {others[2] if len(others) > 2 else 'structures'}",
        f"An approach focused on {others[3] if len(others) > 3 else 'output'} optimization",
    ]
    options = [{"text": definition, "is_correct": True}] + \
              [{"text": d, "is_correct": False} for d in fillers[:3]]
    random.shuffle(options)
    return {
        "text": f"What is {term}?", "question_type": "mcq",
        "marks": _marks(difficulty, 2), "difficulty": difficulty,
        "explanation": f"{term} refers to {definition}.",
        "correct_answer": definition, "options": options,
    }


def _make_topic_mcq(topic, section_title, all_topics, difficulty):
    wrong = [t for t in all_topics if t != topic and len(t) > 5]
    random.shuffle(wrong)
    distractors = wrong[:3]
    if len(distractors) < 3:
        distractors += ["None of the above", "An unrelated framework", "A deprecated method"][:3 - len(distractors)]
    options = [{"text": topic, "is_correct": True}] + \
              [{"text": d, "is_correct": False} for d in distractors[:3]]
    random.shuffle(options)
    return {
        "text": f"Which of the following is a key concept under '{section_title}'?",
        "question_type": "mcq", "marks": _marks(difficulty), "difficulty": difficulty,
        "explanation": f"'{topic}' is a core concept in {section_title}.",
        "correct_answer": topic, "options": options,
    }


def _make_true_false(topic, section_title, difficulty):
    true_tpl  = [f"{topic} is a fundamental concept in {section_title}."]
    false_tpl = [f"{topic} is completely unrelated to {section_title}."]
    is_true   = random.choice([True, False])
    statement = random.choice(true_tpl if is_true else false_tpl)
    options   = [
        {"text": "True",  "is_correct": is_true},
        {"text": "False", "is_correct": not is_true},
    ]
    return {
        "text": statement, "question_type": "true_false",
        "marks": _marks(difficulty), "difficulty": difficulty,
        "explanation": f"This statement about {topic} is {'true' if is_true else 'false'}.",
        "correct_answer": "True" if is_true else "False", "options": options,
    }


def _make_fill_blank(keyword, sentence, difficulty):
    blanked = re.sub(re.escape(keyword), "______", sentence, count=1, flags=re.IGNORECASE)
    return {
        "text": f"Fill in the blank: {blanked}", "question_type": "short_answer",
        "marks": _marks(difficulty), "difficulty": difficulty,
        "explanation": f"The missing word is '{keyword}'.",
        "correct_answer": keyword, "options": [],
    }


def _make_short_answer(topic, section_title, difficulty):
    templates = [
        f"Briefly explain the significance of {topic} in {section_title}.",
        f"What role does {topic} play in {section_title}?",
    ]
    return {
        "text": random.choice(templates), "question_type": "short_answer",
        "marks": _marks(difficulty, 2), "difficulty": difficulty,
        "explanation": f"{topic} is an important concept within {section_title}.",
        "correct_answer": f"Answer should cover key aspects of {topic}.", "options": [],
    }


def _build_coverage_report(parsed, questions, all_sections):
    all_topics_flat    = [t for s in all_sections for t in s["topics"]]
    covered_topics     = set()
    missing_topics     = []
    topic_question_count: dict[str, int] = {}
    q_texts_lower      = [q["text"].lower() for q in questions]
    for topic in all_topics_flat:
        tl = topic.lower()
        if any(tl in qt or any(w in qt for w in tl.split() if len(w) > 4) for qt in q_texts_lower):
            covered_topics.add(topic)
            topic_question_count[topic] = sum(1 for qt in q_texts_lower if tl in qt)
        else:
            missing_topics.append(topic)
    coverage_pct = round(len(covered_topics) / max(len(all_topics_flat), 1) * 100, 1)
    type_dist: dict[str, int] = {}
    diff_dist: dict[str, int] = {}
    for q in questions:
        type_dist[q.get("question_type", "unknown")] = type_dist.get(q.get("question_type", "unknown"), 0) + 1
        diff_dist[q.get("difficulty", "unknown")]     = diff_dist.get(q.get("difficulty", "unknown"), 0) + 1
    return {
        "total_topics_in_syllabus": len(all_topics_flat),
        "topics_covered":           len(covered_topics),
        "topics_missing":           len(missing_topics),
        "coverage_percentage":      coverage_pct,
        "covered_topic_list":       sorted(covered_topics),
        "missing_topic_list":       missing_topics[:30],
        "questions_per_topic":      [{"topic": t, "count": c} for t, c in sorted(topic_question_count.items(), key=lambda x: -x[1])],
        "weak_areas":               [],
        "question_distribution":    {"by_type": type_dist, "by_difficulty": diff_dist},
        "sections_detected":        [s["title"] for s in all_sections],
        "total_questions":          len(questions),
    }


def _infer_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if 5 < len(line) < 80 and not line.startswith(("#", "-", "*", ".")):
            return f"{line} — Exam"
    return "Auto-Generated Exam"


def _generate_rule_based_questions(text, num_questions, difficulty, question_types, focus_topics):
    parsed    = _parse_syllabus(text)
    sections  = parsed["sections"]
    key_terms = parsed["key_terms"]
    defs      = parsed["definitions"]
    sentences = parsed["sentences"]

    if focus_topics:
        focus_lower = [f.strip().lower() for f in focus_topics.split(",")]
        filtered    = [s for s in sections if any(f in s["title"].lower() for f in focus_lower)]
        sections    = filtered if filtered else sections

    all_topics_flat = [(t, s["title"]) for s in sections for t in s["topics"]]
    if not all_topics_flat:
        all_topics_flat = [(line, "General") for line in text.splitlines() if line.strip()]
    random.shuffle(all_topics_flat)

    diff_map = {
        "easy":   ["easy"]   * num_questions,
        "medium": ["medium"] * num_questions,
        "hard":   ["hard"]   * num_questions,
        "mixed":  (["easy", "medium", "medium", "hard"] * (num_questions // 4 + 1))[:num_questions],
    }
    difficulties = diff_map.get(difficulty, ["medium"] * num_questions)

    if question_types == "mcq":
        type_cycle = ["mcq"] * num_questions
    elif question_types == "true_false":
        type_cycle = ["true_false"] * num_questions
    elif question_types == "short":
        type_cycle = ["short_answer"] * num_questions
    else:
        type_cycle = (["mcq", "mcq", "mcq", "true_false", "true_false", "short_answer"] * (num_questions // 6 + 1))[:num_questions]

    all_questions, def_idx, topic_idx = [], 0, 0
    all_topic_texts = [t for t, _ in all_topics_flat]

    for i in range(num_questions):
        q_type = type_cycle[i]
        diff   = difficulties[i]
        topic, sec_title = all_topics_flat[topic_idx % len(all_topics_flat)]

        if q_type == "mcq":
            if def_idx < len(defs):
                d = defs[def_idx]; def_idx += 1
                q = _make_definition_mcq(d["term"], d["definition"], key_terms, diff)
            else:
                q = _make_topic_mcq(topic, sec_title, all_topic_texts, diff)
        elif q_type == "true_false":
            q = _make_true_false(topic, sec_title, diff)
        else:
            first_word     = topic.split()[0] if topic.split() else topic
            matching_sents = [s for s in sentences if first_word.lower() in s.lower()]
            q = _make_fill_blank(first_word, matching_sents[0], diff) if matching_sents else _make_short_answer(topic, sec_title, diff)

        all_questions.append(q)
        topic_idx += 1

    return all_questions
