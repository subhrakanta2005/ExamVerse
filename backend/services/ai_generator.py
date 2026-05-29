"""
backend/services/ai_generator.py

Generates exams using Google Gemini (free tier).
Falls back to a smart rule-based generator when Gemini is unavailable.

Env vars (set in Render → Environment):
  GEMINI_API_KEY   — https://aistudio.google.com/apikey  (free, 1500 req/day)
  TAVILY_API_KEY   — optional, for web-search mode
"""
from __future__ import annotations

import asyncio, json, logging, os, random, re, textwrap
from typing import Any, Optional
import httpx

try:
    from pypdf import PdfReader
    import io as _io; _PYPDF = True
except ImportError:
    _PYPDF = False

try:
    import docx as _docx
    import io as _io2; _DOCX = True
except ImportError:
    _DOCX = False

logger = logging.getLogger(__name__)

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

# Models tried in order — stops at first success
_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
]
_GEMINI_BASE    = "https://generativelanguage.googleapis.com/v1beta/models"
_GEMINI_TIMEOUT = 90


# ══════════════════════════════════════════════════════════════════════════════
# File text extraction
# ══════════════════════════════════════════════════════════════════════════════

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    if ext == "txt":
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try: return file_bytes.decode(enc)
            except UnicodeDecodeError: pass
        return file_bytes.decode("utf-8", errors="replace")
    if ext == "pdf" and _PYPDF:
        try:
            reader = PdfReader(_io.BytesIO(file_bytes))
            return "\n".join(p.extract_text() or "" for p in reader.pages[:60])
        except Exception as e: logger.warning("pypdf: %s", e)
    if ext in ("docx", "doc") and _DOCX:
        try:
            doc = _docx.Document(_io2.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e: logger.warning("docx: %s", e)
    return file_bytes.decode("utf-8", errors="replace")


# ══════════════════════════════════════════════════════════════════════════════
# Gemini API — tries multiple models, surfaces real errors
# ══════════════════════════════════════════════════════════════════════════════

async def _call_gemini(prompt: str, max_tokens: int = 8192) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set.")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    last_error = "No models attempted"
    async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
        for model in _GEMINI_MODELS:
            url = f"{_GEMINI_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                resp = await client.post(
                    url, json=payload,
                    headers={"Content-Type": "application/json"}
                )
                if resp.status_code == 404:
                    last_error = f"model {model} not found (404)"
                    logger.warning("Gemini: %s", last_error)
                    continue
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code} from {model}: {resp.text[:300]}"
                    logger.error("Gemini: %s", last_error)
                    # 400 = bad key / quota — no point retrying other models
                    if resp.status_code in (400, 401, 403):
                        break
                    continue
                data = resp.json()
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info("Gemini OK using model=%s", model)
                    return text
                except (KeyError, IndexError):
                    last_error = f"Unexpected response from {model}: {str(data)[:200]}"
                    logger.error("Gemini: %s", last_error)
                    continue
            except httpx.TimeoutException:
                last_error = f"Timeout ({_GEMINI_TIMEOUT}s) on {model}"
                logger.warning("Gemini: %s", last_error)
                continue
    raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


def _extract_json(text: str) -> Any:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text).strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    for pat in (r'\{[\s\S]*\}', r'\[[\s\S]*\]'):
        m = re.search(pat, text)
        if m:
            try: return json.loads(m.group())
            except json.JSONDecodeError: pass
    raise ValueError(f"No JSON in LLM output: {text[:300]}")


# ══════════════════════════════════════════════════════════════════════════════
# Prompt
# ══════════════════════════════════════════════════════════════════════════════

def _build_prompt(content, num_questions, difficulty, question_types,
                  time_limit, exam_title, focus_topics) -> str:
    title_hint = f'Use "{exam_title}" as the exam title.' if exam_title \
                 else "Infer a suitable exam title from the content."
    focus_hint = f"Focus especially on: {focus_topics}." if focus_topics else ""

    type_map = {
        "mcq":        f"ALL {num_questions} questions must be MCQ (4 options, exactly 1 correct).",
        "true_false": f"ALL {num_questions} questions must be True/False (2 options: True and False).",
        "short":      f"ALL {num_questions} questions must be short_answer (empty options array, model answer in explanation).",
        "mixed":      f"Mix: ~60% mcq_single, ~20% true_false, ~20% short_answer across {num_questions} questions.",
    }
    return textwrap.dedent(f"""
You are an expert exam setter. Generate exactly {num_questions} questions from the content below.

RULES:
1. Difficulty: {difficulty}
2. {type_map.get(question_types, type_map['mixed'])}
3. {title_hint}
4. {focus_hint}
5. Every question MUST have a non-empty explanation (why the answer is correct).
6. MCQ: exactly 4 meaningful options, mark exactly 1 with "is_correct": true.
7. True/False: options must be [{{"text":"True","is_correct":true/false}},{{"text":"False","is_correct":false/true}}].
8. short_answer: options array must be [].
9. question_type values: "mcq_single", "true_false", "short_answer".
10. Return ONLY valid JSON — no markdown, no text outside the JSON object.

JSON FORMAT:
{{
  "title": "...",
  "description": "...",
  "duration_minutes": {time_limit},
  "total_marks": {num_questions},
  "pass_percentage": 40,
  "negative_marking": false,
  "sections": [{{
    "title": "Section 1",
    "description": "",
    "questions": [
      {{
        "text": "What is the powerhouse of the cell?",
        "question_type": "mcq_single",
        "marks": 1,
        "explanation": "The mitochondria produces ATP energy for the cell.",
        "options": [
          {{"text": "Nucleus",      "is_correct": false}},
          {{"text": "Mitochondria", "is_correct": true}},
          {{"text": "Ribosome",     "is_correct": false}},
          {{"text": "Lysosome",     "is_correct": false}}
        ]
      }}
    ]
  }}]
}}

CONTENT:
---
{content[:7000]}
---

Return ONLY the JSON object. No markdown. No explanation outside JSON.
""").strip()


# ══════════════════════════════════════════════════════════════════════════════
# Normaliser
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
            raw_opts = q.get("options") or []
            correct_hint = (q.get("correct_answer") or "").strip().lower()
            options = []
            for opt in raw_opts:
                t = str(opt.get("text", "")).strip()
                ic = bool(opt.get("is_correct", False))
                if not ic and correct_hint:
                    ic = t.lower() == correct_hint or t.lower().startswith(correct_hint)
                options.append({"text": t, "is_correct": ic})
            if options and not any(o["is_correct"] for o in options):
                options[0]["is_correct"] = True
            marks = float(q.get("marks") or 1)
            total_marks += marks
            clean_qs.append({
                "text":          str(q.get("text", "Question")).strip(),
                "question_type": q.get("question_type", "mcq_single"),
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
            "total_topics_in_syllabus": 1, "topics_covered": 1,
            "topics_missing": 0, "coverage_percentage": 100,
            "total_questions": len(all_qs),
            "question_distribution": {"by_type": {}, "by_difficulty": {}},
            "weak_areas": [], "source": "gemini",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Smart rule-based fallback
# ══════════════════════════════════════════════════════════════════════════════

_STOPWORDS = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","being","have","has",
    "had","do","does","did","will","would","could","should","may","might",
    "shall","can","its","it","this","that","these","those","their","they",
    "them","there","here","each","every","some","any","all","both","few",
    "more","most","other","such","no","not","only","own","same","so","than",
    "too","very","just","also","well","even","still","back","way","our","your",
    "my","we","he","she","his","her","you","i","me","us","who","what","which",
    "when","where","how","why","figure","table","section","chapter","page",
    "given","shown","following","above","below","however","therefore","thus",
    "life","lives","living","organism","organisms","period","time","span",
    "example","examples","few","several","many","number","numbers",
}

# Single-word concepts that are too generic to be a meaningful answer
_GENERIC_WORDS = {"life", "time", "period", "growth", "form", "type", "kind",
                  "part", "role", "process", "stage", "state", "mode", "means"}


def _clean_sentence(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip().rstrip('.!?,;:')


def _is_good_answer(word: str) -> bool:
    """Return True if word is a meaningful, specific answer (not a stopword or generic)."""
    w = word.lower().strip()
    if w in _STOPWORDS: return False
    if w in _GENERIC_WORDS: return False
    if len(w) < 3: return False
    if not re.search(r'[a-zA-Z]', w): return False
    return True


def _extract_facts(content: str) -> list[dict]:
    """
    Extract (sentence, subject, answer) triples where answer is a specific,
    meaningful term — proper noun, numeric, or named concept.
    """
    raw_sents = re.split(r'(?<=[.!?])\s+|\n', content)
    sents = [_clean_sentence(s) for s in raw_sents if len(s.strip()) > 25]

    facts = []
    seen_answers: set = set()

    for sent in sents:
        # ── Pattern 1: "X is/are/was [the] Y" — named entity answer ──────────
        m = re.match(
            r'^(.{5,60}?)\s+(?:is|are|was|were|has been|have been)\s+(?:the\s+)?(.{3,60})$',
            sent, re.IGNORECASE
        )
        if m:
            subject   = m.group(1).strip()
            predicate = m.group(2).strip()
            # Prefer the LAST proper noun or number in the predicate
            candidates = re.findall(r'\b([A-Z][a-zA-Z]{2,}|[0-9]+(?:\.[0-9]+)?)\b', predicate)
            candidates = [c for c in candidates if _is_good_answer(c)]
            if not candidates:
                # fall back to last meaningful word
                candidates = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', predicate)
                              if _is_good_answer(w)]
            if candidates:
                answer = candidates[-1]
                if answer.lower() not in seen_answers:
                    seen_answers.add(answer.lower())
                    facts.append({
                        "sentence":  sent,
                        "subject":   subject,
                        "predicate": predicate,
                        "answer":    answer,
                        "style":     "is_predicate",
                    })
                continue

        # ── Pattern 2: multi-word proper noun in sentence ────────────────────
        proper = re.findall(r'\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+)\b', sent)
        for phrase in proper:
            if _is_good_answer(phrase.replace(" ", "")) and phrase.lower() not in seen_answers:
                seen_answers.add(phrase.lower())
                facts.append({
                    "sentence":  sent,
                    "subject":   phrase,
                    "predicate": sent.replace(phrase, "______", 1),
                    "answer":    phrase,
                    "style":     "proper_blank",
                })
                break

        # ── Pattern 3: sentence contains a number (years, counts, etc.) ──────
        nums = re.findall(r'\b(\d+(?:\.\d+)?)\s*(years?|months?|days?|km|mg|cm|%|kg)?\b', sent)
        for num, unit in nums:
            answer = f"{num} {unit}".strip() if unit else num
            if answer not in seen_answers and int(float(num)) > 0:
                seen_answers.add(answer)
                # Build a fill-in-the-blank
                blank_sent = re.sub(re.escape(answer), "______", sent, count=1)
                facts.append({
                    "sentence":  sent,
                    "subject":   blank_sent,
                    "predicate": f"approximately {answer}",
                    "answer":    answer,
                    "style":     "numeric",
                })
                break

    return facts


def _get_distractors(correct: str, content: str, n: int = 3) -> list[str]:
    """Pick n plausible distractors — not stopwords, not the correct answer."""
    # Prefer words of similar length and type
    pool = []
    # Proper nouns first
    pool += re.findall(r'\b[A-Z][a-z]{2,}\b', content)
    # Then longer words
    pool += re.findall(r'\b[A-Za-z]{4,}\b', content)

    filtered = []
    seen = set()
    for w in pool:
        wl = w.lower()
        if wl not in seen and _is_good_answer(w) and w.lower() != correct.lower():
            seen.add(wl)
            filtered.append(w)

    random.shuffle(filtered)
    result = filtered[:n]

    # Pad with generic plausible distractors if pool is thin
    generics = ["None of the above", "All of the above", "Cannot be determined",
                "Data insufficient", "Not mentioned in the text"]
    i = 0
    while len(result) < n:
        result.append(generics[i % len(generics)]); i += 1

    return result[:n]


def _fallback_generate(
    content: str, num_questions: int, difficulty: str, question_types: str,
    time_limit: int, exam_title: Optional[str],
) -> dict:
    """
    Rule-based generator. Only runs when Gemini is unavailable.
    Produces meaningful MCQ/T-F/SA questions from real facts in the text.
    """
    facts    = _extract_facts(content)
    all_sents = [_clean_sentence(s) for s in re.split(r'(?<=[.!?])\s+|\n', content)
                 if len(s.strip()) > 40]

    if question_types == "mcq":
        seq = ["mcq_single"] * num_questions
    elif question_types == "true_false":
        seq = ["true_false"] * num_questions
    elif question_types == "short":
        seq = ["short_answer"] * num_questions
    else:
        n_mcq = max(1, round(num_questions * 0.60))
        n_tf  = max(1, round(num_questions * 0.20))
        n_sa  = num_questions - n_mcq - n_tf
        seq   = (["mcq_single"] * n_mcq +
                 ["true_false"] * max(0, n_tf) +
                 ["short_answer"] * max(0, n_sa))
        random.shuffle(seq)

    questions  = []
    fact_idx   = 0
    sent_idx   = 0
    used_sents: set = set()

    for q_type in seq[:num_questions]:

        # ── MCQ ───────────────────────────────────────────────────────────────
        if q_type == "mcq_single":
            fact = None
            for fi in range(fact_idx, min(fact_idx + 30, len(facts))):
                if facts[fi]["sentence"] not in used_sents:
                    fact = facts[fi]; fact_idx = fi + 1
                    used_sents.add(fact["sentence"]); break

            if fact:
                answer = fact["answer"]
                if fact["style"] == "proper_blank":
                    q_text = f"Fill in the blank: {fact['predicate']}?"
                elif fact["style"] == "numeric":
                    q_text = f"Fill in the blank: {fact['subject']}?"
                else:
                    q_text = (f"According to the content, what is the "
                              f"{fact['subject'].lower().strip('.')}?")

                distractors = _get_distractors(answer, content, 3)
                opts = [answer] + distractors
                random.shuffle(opts)
                questions.append({
                    "text":          q_text,
                    "question_type": "mcq_single",
                    "marks":         1,
                    "explanation":   f"From the text: \"{fact['sentence']}\"",
                    "options":       [{"text": o, "is_correct": (o == answer)} for o in opts],
                })
            else:
                # Generic comprehension MCQ
                sent = all_sents[sent_idx % len(all_sents)] if all_sents else "Review the content."
                sent_idx += 1
                questions.append({
                    "text":    f"Which statement correctly reflects the content?",
                    "question_type": "mcq_single",
                    "marks":   1,
                    "explanation": f"This is directly stated in the text: \"{sent[:100]}\"",
                    "options": [
                        {"text": sent[:80] + ("..." if len(sent) > 80 else ""), "is_correct": True},
                        {"text": "The opposite of what is stated in the text.",   "is_correct": False},
                        {"text": "This concept is not mentioned in the content.", "is_correct": False},
                        {"text": "Only partially correct based on the content.",  "is_correct": False},
                    ],
                })

        # ── True / False ──────────────────────────────────────────────────────
        elif q_type == "true_false":
            sent = None
            for si in range(sent_idx, sent_idx + len(all_sents) + 1):
                candidate = all_sents[si % len(all_sents)] if all_sents else ""
                if candidate not in used_sents and len(candidate) > 30:
                    sent = candidate; sent_idx = si + 1
                    used_sents.add(sent); break
            if not sent:
                sent = all_sents[sent_idx % len(all_sents)] if all_sents else "Review the content."
                sent_idx += 1
            questions.append({
                "text":          f"True or False: {sent}.",
                "question_type": "true_false",
                "marks":         1,
                "explanation":   "This statement is directly supported by the content.",
                "options": [
                    {"text": "True",  "is_correct": True},
                    {"text": "False", "is_correct": False},
                ],
            })

        # ── Short Answer ──────────────────────────────────────────────────────
        else:
            fact = None
            for fi in range(fact_idx, min(fact_idx + 30, len(facts))):
                if facts[fi]["sentence"] not in used_sents:
                    fact = facts[fi]; fact_idx = fi + 1
                    used_sents.add(fact["sentence"]); break

            if fact:
                q_text  = f"Explain: {fact['subject'].strip('.')} — as described in the content."
                explain = fact["sentence"]
            else:
                sent     = all_sents[sent_idx % len(all_sents)] if all_sents else "Review the content."
                sent_idx += 1
                q_text   = f"In your own words, explain: \"{sent[:100]}\"."
                explain  = sent

            questions.append({
                "text":          q_text,
                "question_type": "short_answer",
                "marks":         2,
                "explanation":   explain,
                "options":       [],
            })

    while len(questions) < num_questions:
        questions.append({
            "text":          f"Summarise a key concept from the content (question {len(questions)+1}).",
            "question_type": "short_answer",
            "marks":         2,
            "explanation":   "Refer to the syllabus for key concepts.",
            "options":       [],
        })

    return {
        "title":            exam_title or "Generated Exam",
        "description":      "Auto-generated from syllabus content.",
        "duration_minutes": time_limit,
        "total_marks":      sum(q["marks"] for q in questions),
        "pass_percentage":  40,
        "negative_marking": False,
        "sections":         [{"title": "General", "description": "", "questions": questions}],
        "coverage_report": {
            "total_topics_in_syllabus": max(1, len(facts)),
            "topics_covered":           min(len(facts), num_questions),
            "topics_missing":           0,
            "coverage_percentage":      100,
            "total_questions":          len(questions),
            "question_distribution":    {"by_type": {}, "by_difficulty": {}},
            "weak_areas":               [],
            "source":                   "fallback",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Pre-formatted question bank parser
# Handles PDFs that already contain MCQs with [CORRECT] / Answer: (X) markers
# ══════════════════════════════════════════════════════════════════════════════

def _is_question_bank(text: str) -> bool:
    """Return True if the text looks like a pre-formatted MCQ question bank."""
    correct_markers = len(re.findall(r'\[CORRECT\]', text, re.IGNORECASE))
    answer_markers  = len(re.findall(r'Answer\s*:\s*\([A-Da-d]\)', text))
    q_markers       = len(re.findall(r'\bQ\s*\d+[\.\)]', text))
    abcd_options    = len(re.findall(r'^[A-D]\)', text, re.MULTILINE))
    score = (correct_markers * 3) + (answer_markers * 3) + (q_markers * 2) + abcd_options
    logger.info("Question bank score: %d (correct=%d answer=%d q=%d abcd=%d)",
                score, correct_markers, answer_markers, q_markers, abcd_options)
    return score >= 10


def _parse_question_bank(
    text: str,
    num_questions: int,
    time_limit: int,
    exam_title: Optional[str],
) -> dict:
    """
    Parse a pre-formatted MCQ question bank PDF into ExamVerse format.

    Handles multiple common formats:
      Format A:  Q1. Question text?
                 A) Option  B) Option  C) Option [CORRECT]  D) Option
                 Answer: (C)

      Format B:  1. Question text
                 A. Option
                 B. Option
                 C. Option
                 D. Option
                 Answer: B

      Format C:  mixed inline like "A) Mahanadi B) ... C) Baitarani [CORRECT] D) ..."
    """
    questions = []

    # ── Split into question blocks ────────────────────────────────────────────
    # Split on Q<n>. or standalone <n>. at start of line
    blocks = re.split(r'\n(?=(?:Q\s*)?\d+[\.\)]\s)', text)

    for block in blocks:
        block = block.strip()
        if len(block) < 10:
            continue

        # ── Extract question number + text ────────────────────────────────────
        m_head = re.match(r'^(?:Q\s*)?(\d+)[\.\)]\s*(.+?)(?=\n[A-Da-d][\.\)]|\Z)',
                          block, re.DOTALL | re.IGNORECASE)
        if not m_head:
            continue

        q_text_raw = m_head.group(2).strip()

        # Clean up question text — remove embedded option lines that got merged
        # e.g. "Which river? A) Mahanadi B) Rushikulya C) Baitarani [CORRECT] D) Brahmani"
        # Detect inline options: "A) opt1  B) opt2  C) opt3 [CORRECT]  D) opt4"
        inline_opts = re.findall(r'([A-D])\)\s*(.*?)(?=\s+[A-D]\)|\s*$)',
                                  q_text_raw, re.IGNORECASE)
        correct_inline = None
        if inline_opts:
            correct_m = re.search(r'([A-D])\)\s*[^\n]*\[CORRECT\]',
                                  q_text_raw, re.IGNORECASE)
            if correct_m:
                correct_inline = correct_m.group(1).upper()
            # Strip options from question text
            q_text_raw = re.split(r'\s{2,}[A-D]\)|(?<![A-Z])\s+A\)', q_text_raw)[0].strip()

        # Also strip "Answer: (X)" from question text
        q_text_raw = re.sub(r'\s*Answer\s*:\s*\([A-Da-d]\)\s*$', '', q_text_raw,
                            flags=re.IGNORECASE).strip()
        # Strip trailing format metadata lines
        q_text_raw = re.sub(
            r'(Format:.*|SECTION\s+\d+.*|ExamVerse.*)', '', q_text_raw,
            flags=re.IGNORECASE
        ).strip()

        if not q_text_raw or len(q_text_raw) < 5:
            continue

        # ── Extract options from next lines ───────────────────────────────────
        # Extract options — handles both multi-line and inline formats
        # First try multi-line (each option on its own line)
        option_lines = re.findall(
            r'^([A-D])[\.\)]\ *(.+?)$',
            block, re.MULTILINE | re.IGNORECASE
        )
        # If only 1 "option" found, the options are inline on one line — re-split
        if len(option_lines) <= 1:
            inline_line = re.search(r'^[A-D][\.\)].+', block, re.MULTILINE | re.IGNORECASE)
            if inline_line:
                option_lines = re.findall(
                    r'([A-D])\)\ *(.*?)(?=\ +[A-D]\)|\ *$)',
                    inline_line.group(), re.IGNORECASE
                )


        # Determine correct answer letter
        # Priority 1: Answer: (X)
        ans_m = re.search(r'Answer\s*:\s*\(?([A-Da-d])\)?', block, re.IGNORECASE)
        correct_letter = ans_m.group(1).upper() if ans_m else None

        # Priority 2: inline [CORRECT] tag
        if not correct_letter and correct_inline:
            correct_letter = correct_inline

        # Priority 3: [CORRECT] next to an option line
        if not correct_letter:
            correct_m2 = re.search(r'([A-D])[\.\)][^\n]*\[CORRECT\]', block, re.IGNORECASE)
            if correct_m2:
                correct_letter = correct_m2.group(1).upper()

        # Build options
        options = []
        if option_lines:
            for letter, opt_text in option_lines:
                opt_text = opt_text.strip()
                opt_text = re.sub(r'\[CORRECT\]', '', opt_text, flags=re.IGNORECASE).strip()
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                if not opt_text:
                    continue
                is_correct = (letter.upper() == correct_letter) if correct_letter \
                             else ("[CORRECT]" in opt_text)
                options.append({"text": opt_text, "is_correct": is_correct})
        elif inline_opts:
            # inline_opts is list of (letter, text) tuples
            for letter, opt_text in inline_opts:
                opt_text = re.sub(r'\[CORRECT\]', '', opt_text, flags=re.IGNORECASE).strip()
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                if not opt_text:
                    continue
                is_correct = (letter.upper() == correct_letter) if correct_letter                              else ("[CORRECT]" in opt_text)
                options.append({"text": opt_text, "is_correct": is_correct})

        # Skip if no usable options
        if not options:
            continue

        # Ensure exactly one correct answer
        if not any(o["is_correct"] for o in options):
            options[0]["is_correct"] = True

        questions.append({
            "text":          q_text_raw,
            "question_type": "mcq_single",
            "marks":         1,
            "explanation":   f"Answer: ({correct_letter})" if correct_letter else "",
            "options":       options,
        })

        if len(questions) >= num_questions:
            break

    if not questions:
        raise ValueError("Could not parse any questions from the question bank PDF.")

    logger.info("Question bank parser: extracted %d questions", len(questions))

    # Infer title from first meaningful line if not provided
    if not exam_title:
        first_line = text.strip().splitlines()[0][:80].strip()
        exam_title = first_line if len(first_line) > 5 else "Question Bank Exam"

    total = len(questions)
    return {
        "title":            exam_title,
        "description":      f"Imported from question bank — {total} MCQ questions.",
        "duration_minutes": time_limit,
        "total_marks":      total,
        "pass_percentage":  40,
        "negative_marking": False,
        "sections": [{"title": "Section 1", "description": "", "questions": questions}],
        "coverage_report": {
            "total_topics_in_syllabus": total,
            "topics_covered":           total,
            "topics_missing":           0,
            "coverage_percentage":      100,
            "total_questions":          total,
            "question_distribution":    {"by_type": {"mcq_single": total}, "by_difficulty": {}},
            "weak_areas":               [],
            "source":                   "question_bank_parser",
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
    # Step 1: detect pre-formatted question bank -- parse directly
    if _is_question_bank(syllabus_text):
        logger.info("Detected pre-formatted question bank -- parsing directly")
        try:
            return _parse_question_bank(syllabus_text, num_questions, time_limit, exam_title)
        except Exception as exc:
            logger.warning("Question bank parser failed (%s) -- continuing to AI", exc)

    # Step 2: AI / fallback generation
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set -- using fallback generator")
        return _fallback_generate(syllabus_text, num_questions, difficulty,
                                  question_types, time_limit, exam_title)
    prompt = _build_prompt(syllabus_text, num_questions, difficulty, question_types,
                           time_limit, exam_title, focus_topics)
    try:
        raw_text = await _call_gemini(prompt, max_tokens=8192)
        raw_json = _extract_json(raw_text)
        result   = _normalise(raw_json, num_questions, time_limit)
        logger.info("Gemini OK: %d questions generated",
                    sum(len(s["questions"]) for s in result["sections"]))
        return result
    except Exception as exc:
        logger.error("Gemini failed (%s) -- falling back to rule-based generator", exc)
        return _fallback_generate(syllabus_text, num_questions, difficulty,
                                  question_types, time_limit, exam_title)


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
    combined = ""
    if TAVILY_API_KEY and topics:
        try:
            query = ", ".join(topics[:5]) + (f" {extra_context}" if extra_context else "")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 5},
                    headers={"Content-Type": "application/json"},
                )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                combined = "\n\n".join(
                    f"{r.get('title','')}\n{r.get('content','')}" for r in results
                )
        except Exception as exc:
            logger.warning("Tavily search failed: %s", exc)

    if not combined:
        combined = (f"Topics: {', '.join(topics)}\nContext: {extra_context}\n\n"
                    "Generate educationally accurate questions on these topics.")

    return await generate_exam_from_syllabus(
        syllabus_text  = combined,
        num_questions  = num_questions,
        difficulty     = difficulty,
        question_types = question_types,
        time_limit     = time_limit,
        exam_title     = exam_title or f"{', '.join(topics[:2])} Exam",
        focus_topics   = focus_topics,
    )
