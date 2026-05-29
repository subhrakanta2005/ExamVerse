"""
backend/services/ai_generator.py

Rules:
  1. If uploaded file looks like a question bank  → parse it directly, NO AI at all
  2. If it's a syllabus/notes                     → use Gemini to generate questions
  3. If Gemini fails / key missing                → use smart rule-based fallback

Env vars (Render dashboard):
  GEMINI_API_KEY   — https://aistudio.google.com/apikey  (free, 1500 req/day)
  TAVILY_API_KEY   — optional, for search mode
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

_GEMINI_MODELS  = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
_GEMINI_BASE    = "https://generativelanguage.googleapis.com/v1beta/models"
_GEMINI_TIMEOUT = 90


# ══════════════════════════════════════════════════════════════════════════════
# File text extraction
# ══════════════════════════════════════════════════════════════════════════════

async def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"
    if ext == "pdf" and _PYPDF:
        try:
            reader = PdfReader(_io.BytesIO(file_bytes))
            # Extract all pages; keep newlines between pages
            pages = []
            for page in reader.pages[:80]:
                text = page.extract_text() or ""
                pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            logger.warning("pypdf error: %s", e)
    if ext in ("docx", "doc") and _DOCX:
        try:
            doc = _docx.Document(_io2.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.warning("docx error: %s", e)
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            pass
    return file_bytes.decode("utf-8", errors="replace")


# ══════════════════════════════════════════════════════════════════════════════
# QUESTION BANK DETECTOR & PARSER
# If the text is already a question bank → extract questions directly, zero AI
# ══════════════════════════════════════════════════════════════════════════════

def _is_question_bank(text: str) -> bool:
    """
    Return True if this text is a pre-made question bank.
    Looks for patterns that only appear in answer-key documents:
      (a)/(b)/(c)/(d) style options  +  Answer: markers
    """
    paren_options  = len(re.findall(r'\([a-d]\)\s*\S', text, re.IGNORECASE))
    tick_answers   = len(re.findall(r'[✓√]\s*Answer\s*:', text))
    plain_answers  = len(re.findall(r'\bAnswer\s*:\s*\([a-d]\)', text, re.IGNORECASE))
    correct_tags   = len(re.findall(r'\[CORRECT\]', text, re.IGNORECASE))
    numbered_qs    = len(re.findall(r'^\s*\d+[\.\)]\s+\S', text, re.MULTILINE))

    score = (paren_options * 2) + (tick_answers * 5) + (plain_answers * 4) + \
            (correct_tags * 4)  + (numbered_qs)

    logger.info(
        "QB detection: score=%d  paren_opts=%d  tick=%d  ans=%d  correct=%d  q#=%d",
        score, paren_options, tick_answers, plain_answers, correct_tags, numbered_qs
    )
    return score >= 15


def _clean_option_text(text: str) -> str:
    """Strip answer markers, ticks, explanation leaks from an option string."""
    # Remove answer markers like "✓ Answer: (b)" or "Answer: (b) Rice"
    text = re.sub(r'[✓√]\s*Answer\s*:.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\bAnswer\s*:.*$',      '', text, flags=re.IGNORECASE | re.DOTALL)
    # Remove [CORRECT] tags
    text = re.sub(r'\[CORRECT\]', '', text, flags=re.IGNORECASE)
    # Remove trailing explanation
    text = re.sub(r'\bExplanation\s*:.*$', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', text).strip()


def _extract_options(block: str) -> list[tuple[str, str]]:
    """
    Try multiple strategies to extract (letter, text) option pairs from a block.

    Strategy 1 — each option on its own line:
        (a) Andhra Pradesh
        (b) Jharkhand

    Strategy 2 — all options inline on one line (common after pypdf extraction):
        (a) Andhra Pradesh (b) Jharkhand (c) Chhattisgarh (d) West Bengal

    Strategy 3 — capital letter format on its own line:
        A) Andhra Pradesh
        B) Jharkhand

    Strategy 4 — capital letter inline:
        A) Andhra Pradesh B) Jharkhand C) Chhattisgarh D) West Bengal
    """

    # ── Strategy 1: lowercase paren options, one per line ────────────────────
    paren_opts = re.findall(r'^\s*\(([a-d])\)\s*(.+?)$', block,
                            re.MULTILINE | re.IGNORECASE)
    if len(paren_opts) >= 2:
        return [(l.lower(), _clean_option_text(t)) for l, t in paren_opts]

    # ── Strategy 2: ALL four options inline with (a)...(b)...(c)...(d) ──────
    # Captures everything between consecutive option markers
    inline_m = re.search(
        r'\(a\)\s*(.+?)\s*\(b\)\s*(.+?)\s*\(c\)\s*(.+?)\s*\(d\)\s*(.+?)(?=\s*[✓√]|\s*\bAnswer\b|\s*\bExplanation\b|\s*$)',
        block, re.IGNORECASE | re.DOTALL
    )
    if inline_m:
        return [
            ('a', _clean_option_text(inline_m.group(1))),
            ('b', _clean_option_text(inline_m.group(2))),
            ('c', _clean_option_text(inline_m.group(3))),
            ('d', _clean_option_text(inline_m.group(4))),
        ]

    # ── Strategy 3: capital letter options, one per line ─────────────────────
    cap_opts = re.findall(r'^\s*([A-D])[\.\)]\s*(.+?)$', block,
                          re.MULTILINE | re.IGNORECASE)
    if len(cap_opts) >= 2:
        return [(l.lower(), _clean_option_text(t)) for l, t in cap_opts]

    # ── Strategy 4: capital letter options inline ─────────────────────────────
    cap_inline = re.search(
        r'[A-D]\)\s*.+',
        block, re.IGNORECASE
    )
    if cap_inline:
        found = re.findall(
            r'([A-D])\)\s*(.*?)(?=\s+[A-D]\)|\s*[✓√]|\s*\bAnswer\b|\s*$)',
            cap_inline.group(), re.IGNORECASE
        )
        if len(found) >= 2:
            return [(l.lower(), _clean_option_text(t)) for l, t in found]

    return []


def _parse_question_bank(text: str, num_questions: int, time_limit: int,
                          exam_title: Optional[str]) -> dict:
    """
    Parse a pre-formatted question bank directly into ExamVerse format.

    Handles all common PDF-extracted layouts:
      • Options on separate lines: (a) Text\\n(b) Text\\n...
      • Options all on one line:   (a) Text (b) Text (c) Text (d) Text
      • Capital letter variants:   A) Text  B) Text  ...
      • Answer markers:            ✓ Answer: (b)  /  Answer: (b)  /  [CORRECT]
    """
    questions = []

    # ── Split into per-question blocks ────────────────────────────────────────
    # Matches "1." / "1)" / "Q1." / "Q.1" etc. at the start of a line
    blocks = re.split(r'(?m)(?=^\s*(?:Q[\s\.]*)?\d{1,3}[\.\)]\s)', text)

    for block in blocks:
        block = block.strip()
        if len(block) < 15:
            continue

        # ── Extract question number ───────────────────────────────────────────
        num_match = re.match(r'^(?:Q[\s\.]*)?\d{1,3}[\.\)]\s*', block)
        if not num_match:
            continue

        # ── Extract question text ─────────────────────────────────────────────
        # Everything after the question number, up to the first option marker
        # Option markers: "(a)", "A)", "A.", or a tick/answer line
        after_num = block[num_match.end():]

        # Try to find where the options begin
        option_start = re.search(
            r'\n\s*[\(\[]?[aAbBcCdD][\.\)\]]\s*\S'   # newline + option
            r'|\s*\(a\)\s*\S',                         # OR inline (a) right after question
            after_num
        )

        if option_start:
            q_text_raw = after_num[:option_start.start()]
        else:
            # No clear split — take first line as question text
            first_line_end = after_num.find('\n')
            q_text_raw = after_num[:first_line_end] if first_line_end > 0 else after_num[:200]

        q_text = re.sub(r'\s+', ' ', q_text_raw).strip()

        # Clean any answer/explanation that leaked into question text
        q_text = re.sub(r'\s*[✓√]\s*Answer\s*:.*$', '', q_text,
                        flags=re.IGNORECASE | re.DOTALL).strip()
        q_text = re.sub(r'\s*\bAnswer\s*:.*$', '', q_text,
                        flags=re.IGNORECASE | re.DOTALL).strip()
        q_text = re.sub(r'\s*\bExplanation\s*:.*$', '', q_text,
                        flags=re.IGNORECASE | re.DOTALL).strip()
        # Remove trailing option text that got swept in (e.g. "(a) Option1...")
        q_text = re.sub(r'\s*\(a\)\s*.*$', '', q_text,
                        flags=re.IGNORECASE | re.DOTALL).strip()

        if not q_text or len(q_text) < 4:
            continue

        # ── Extract options ───────────────────────────────────────────────────
        raw_opts = _extract_options(block)
        if not raw_opts:
            continue

        # ── Find correct answer letter ────────────────────────────────────────
        correct_letter = None

        # Pattern: ✓ Answer: (b) or Answer: (b) Rice  — capture the letter
        m_ans = re.search(r'[✓√]?\s*Answer\s*:\s*\(?([a-d])\)?', block, re.IGNORECASE)
        if m_ans:
            correct_letter = m_ans.group(1).lower()

        # Pattern: [CORRECT] next to an option
        if not correct_letter:
            m_corr = re.search(r'([A-Da-d])[\.\)][^\n]*\[CORRECT\]', block, re.IGNORECASE)
            if m_corr:
                correct_letter = m_corr.group(1).lower()

        # ── Extract explanation ───────────────────────────────────────────────
        explanation = ""
        m_expl = re.search(r'Explanation\s*:\s*(.+?)(?=\n\s*\n|\Z)', block,
                           re.DOTALL | re.IGNORECASE)
        if m_expl:
            explanation = re.sub(r'\s+', ' ', m_expl.group(1)).strip()[:500]

        # ── Build option list ─────────────────────────────────────────────────
        options = []
        for letter, opt_text in raw_opts:
            if not opt_text:
                continue
            is_correct = (letter == correct_letter) if correct_letter else False
            options.append({"text": opt_text, "is_correct": is_correct})

        if not options:
            continue

        # Ensure exactly one correct option
        correct_count = sum(1 for o in options if o["is_correct"])
        if correct_count == 0:
            # Last resort: nothing matched — mark first option correct and log
            logger.warning("No correct answer found for Q: %s... — defaulting to first option", q_text[:60])
            options[0]["is_correct"] = True
        elif correct_count > 1:
            # Multiple marked — keep only the first one
            first_seen = False
            for o in options:
                if o["is_correct"]:
                    if first_seen:
                        o["is_correct"] = False
                    else:
                        first_seen = True

        questions.append({
            "text":          q_text,
            "question_type": "mcq_single",
            "marks":         1,
            "explanation":   explanation,
            "options":       options,
        })

        

    if not questions:
        raise ValueError(
            "Could not parse any questions from the uploaded file. "
            "Please check the file format and try again."
        )

    logger.info("QB parser extracted %d / %d requested questions", len(questions), num_questions)

    # ── Auto-detect title from file if not provided ───────────────────────────
    if not exam_title:
        for line in text.splitlines():
            line = line.strip()
            # Skip lines that look like question numbers or short fragments
            if line and not re.match(r'^\d+[\.\)]', line) and 8 < len(line) < 120:
                exam_title = line
                break
        exam_title = exam_title or "Question Bank Exam"

    total = len(questions)
    duration = time_limit if time_limit else max(30, total * 1)

    # ── Group questions into subject-based sections (every 5 questions) ───────
    # For large banks, grouping into sections makes navigation easier
    SECTION_SIZE = 10
    sections = []
    for i in range(0, total, SECTION_SIZE):
        chunk = questions[i:i + SECTION_SIZE]
        sec_num = (i // SECTION_SIZE) + 1
        sections.append({
            "title":       f"Section {sec_num}",
            "description": "",
            "questions":   chunk,
        })

    return {
        "title":            exam_title,
        "description":      f"Imported from question bank — {total} questions.",
        "duration_minutes": duration,
        "total_marks":      float(total),
        "pass_percentage":  40,
        "negative_marking": False,
        "sections":         sections,
        "coverage_report": {
            "total_topics_in_syllabus": total,
            "topics_covered":           total,
            "topics_missing":           0,
            "coverage_percentage":      100,
            "total_questions":          total,
            "question_distribution":    {
                "by_type":       {"mcq_single": total},
                "by_difficulty": {},
            },
            "weak_areas": [],
            "source":     "question_bank_parser",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Gemini API
# ══════════════════════════════════════════════════════════════════════════════

async def _call_gemini(prompt: str, max_tokens: int = 8192) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    last_err = "no models tried"
    async with httpx.AsyncClient(timeout=_GEMINI_TIMEOUT) as client:
        for model in _GEMINI_MODELS:
            url = f"{_GEMINI_BASE}/{model}:generateContent?key={GEMINI_API_KEY}"
            try:
                r = await client.post(url, json=payload,
                                      headers={"Content-Type": "application/json"})
                if r.status_code == 404:
                    last_err = f"{model} not found"; continue
                if r.status_code in (400, 401, 403):
                    last_err = f"Auth/quota error {r.status_code}: {r.text[:200]}"; break
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code} from {model}: {r.text[:200]}"; continue
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.TimeoutException:
                last_err = f"timeout on {model}"; continue
    raise RuntimeError(f"Gemini failed: {last_err}")


def _extract_json(text: str) -> Any:
    text = re.sub(r'```(?:json)?\s*', '', text).replace('```', '').strip()
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
    raise ValueError(f"No JSON in response: {text[:300]}")


def _build_prompt(content, num_questions, difficulty, question_types,
                  time_limit, exam_title, focus_topics) -> str:
    title_hint = f'Title: "{exam_title}".' if exam_title else "Infer a good title."
    focus_hint = f"Focus on: {focus_topics}." if focus_topics else ""
    type_map = {
        "mcq":        f"All {num_questions} must be mcq_single (4 options, 1 correct).",
        "true_false": f"All {num_questions} must be true_false.",
        "short":      f"All {num_questions} must be short_answer (empty options array).",
        "mixed":      f"Mix: ~60% mcq_single, ~20% true_false, ~20% short_answer.",
    }
    # Limit content to 7000 chars to stay within Gemini context safely
    content_trimmed = content[:7000]
    return textwrap.dedent(f"""
You are an expert exam setter. Generate exactly {num_questions} questions from the content below.
Difficulty: {difficulty}. {type_map.get(question_types, type_map['mixed'])}
{title_hint} {focus_hint}

Every question MUST have a non-empty explanation.
MCQ: exactly 4 options, exactly 1 correct (is_correct: true).
Return ONLY valid JSON — no markdown, no text outside JSON.

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
        "text": "What is the capital of Odisha?",
        "question_type": "mcq_single",
        "marks": 1,
        "explanation": "Bhubaneswar is the capital of Odisha.",
        "options": [
          {{"text": "Cuttack",      "is_correct": false}},
          {{"text": "Bhubaneswar", "is_correct": true}},
          {{"text": "Puri",         "is_correct": false}},
          {{"text": "Rourkela",     "is_correct": false}}
        ]
      }}
    ]
  }}]
}}

CONTENT:
---
{content_trimmed}
---
Return ONLY the JSON object.
""").strip()


def _normalise(raw: dict, num_questions: int, time_limit: int) -> dict:
    sections = raw.get("sections") or []
    if not sections and raw.get("questions"):
        sections = [{"title": "Section 1", "description": "", "questions": raw["questions"]}]
    clean = []
    total = 0
    for sec in sections:
        qs = []
        for q in (sec.get("questions") or []):
            opts = q.get("options") or []
            ch   = (q.get("correct_answer") or "").strip().lower()
            options = []
            for o in opts:
                t  = str(o.get("text", "")).strip()
                ic = bool(o.get("is_correct", False))
                if not ic and ch:
                    ic = t.lower() == ch or t.lower().startswith(ch)
                options.append({"text": t, "is_correct": ic})
            if options and not any(o["is_correct"] for o in options):
                options[0]["is_correct"] = True
            marks = float(q.get("marks") or 1)
            total += marks
            qs.append({
                "text":          str(q.get("text", "")).strip(),
                "question_type": q.get("question_type", "mcq_single"),
                "marks":         marks,
                "explanation":   str(q.get("explanation", "") or ""),
                "options":       options,
            })
        clean.append({"title": str(sec.get("title") or "Section").strip(),
                      "description": str(sec.get("description") or ""),
                      "questions": qs})
    all_qs = [q for s in clean for q in s["questions"]]
    return {
        "title":            str(raw.get("title") or "Generated Exam").strip(),
        "description":      str(raw.get("description") or ""),
        "duration_minutes": int(raw.get("duration_minutes") or time_limit),
        "total_marks":      int(total) or len(all_qs),
        "pass_percentage":  int(raw.get("pass_percentage") or 40),
        "negative_marking": bool(raw.get("negative_marking", False)),
        "sections":         clean,
        "coverage_report": {
            "total_topics_in_syllabus": 1, "topics_covered": 1,
            "topics_missing": 0, "coverage_percentage": 100,
            "total_questions": len(all_qs),
            "question_distribution": {"by_type": {}, "by_difficulty": {}},
            "weak_areas": [], "source": "gemini",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# Smart fallback (runs only for real syllabi when Gemini is unavailable)
# ══════════════════════════════════════════════════════════════════════════════

_SW = {
    "the","a","an","and","or","but","in","on","at","to","for","of","with","by",
    "from","is","are","was","were","be","been","have","has","had","do","does",
    "did","will","would","could","should","this","that","these","those","it",
    "its","they","them","their","we","our","he","she","his","her","you","i",
    "also","so","than","too","very","just","each","every","some","any","all",
    "more","most","other","such","which","when","where","how","who","what",
    "figure","table","given","above","below","chapter","section","page",
}

def _good(w: str) -> bool:
    w = w.lower().strip()
    return w not in _SW and len(w) >= 3 and bool(re.search(r'[a-zA-Z]', w))

def _extract_facts(text: str) -> list[dict]:
    sents = [re.sub(r'\s+', ' ', s).strip().rstrip('.!?,;:')
             for s in re.split(r'(?<=[.!?])\s+|\n', text) if len(s.strip()) > 25]
    facts, seen = [], set()
    for sent in sents:
        m = re.match(
            r'^(.{5,60}?)\s+(?:is|are|was|were)\s+(?:the\s+)?(.{3,60})$',
            sent, re.IGNORECASE
        )
        if m:
            pred = m.group(2).strip()
            cands = [c for c in re.findall(r'\b([A-Z][a-zA-Z]{2,}|\d+[a-z]*)\b', pred)
                     if _good(c)]
            if not cands:
                cands = [w for w in re.findall(r'\b[A-Za-z]{4,}\b', pred) if _good(w)]
            if cands:
                ans = cands[-1]
                if ans.lower() not in seen:
                    seen.add(ans.lower())
                    facts.append({"sentence": sent, "subject": m.group(1).strip(),
                                  "answer": ans, "style": "is"})
                continue
        for num, unit in re.findall(r'\b(\d+(?:\.\d+)?)\s*(years?|km|m|BCE|CE|%|kg)?\b', sent):
            ans = f"{num} {unit}".strip() if unit else num
            if ans not in seen and int(float(num)) > 0:
                seen.add(ans)
                blank = re.sub(re.escape(ans), "______", sent, count=1)
                facts.append({"sentence": sent, "subject": blank,
                              "answer": ans, "style": "numeric"})
                break
    return facts

def _distractors(correct: str, text: str, n: int = 3) -> list[str]:
    pool = list(dict.fromkeys(
        w for w in re.findall(r'\b[A-Za-z]{3,}\b', text)
        if _good(w) and w.lower() != correct.lower()
    ))
    random.shuffle(pool)
    result = pool[:n]
    pad = ["None of the above", "Cannot be determined", "All of the above"]
    while len(result) < n:
        result.append(pad[len(result) % len(pad)])
    return result[:n]

def _fallback_generate(content, num_questions, difficulty, question_types,
                       time_limit, exam_title) -> dict:
    facts  = _extract_facts(content)
    sents  = [re.sub(r'\s+', ' ', s).strip()
              for s in re.split(r'(?<=[.!?])\s+|\n', content) if len(s.strip()) > 40]

    if question_types == "mcq":
        seq = ["mcq_single"] * num_questions
    elif question_types == "true_false":
        seq = ["true_false"] * num_questions
    elif question_types == "short":
        seq = ["short_answer"] * num_questions
    else:
        n_m = max(1, round(num_questions * 0.6))
        n_t = max(1, round(num_questions * 0.2))
        n_s = max(0, num_questions - n_m - n_t)
        seq = ["mcq_single"] * n_m + ["true_false"] * n_t + ["short_answer"] * n_s
        random.shuffle(seq)

    questions, fi, si, used = [], 0, 0, set()

    for qtype in seq[:num_questions]:
        if qtype == "mcq_single":
            fact = next((facts[i] for i in range(fi, min(fi+30, len(facts)))
                         if facts[i]["sentence"] not in used), None)
            if fact:
                fi += 1; used.add(fact["sentence"])
                ans  = fact["answer"]
                qtxt = (f"Fill in the blank: {fact['subject']}?"
                        if fact["style"] in ("numeric",)
                        else f"According to the content, what is the {fact['subject'].lower().rstrip('.')}?")
                opts = [ans] + _distractors(ans, content, 3)
                random.shuffle(opts)
                questions.append({
                    "text": qtxt, "question_type": "mcq_single", "marks": 1,
                    "explanation": f'From the text: "{fact["sentence"]}"',
                    "options": [{"text": o, "is_correct": (o == ans)} for o in opts],
                })
            else:
                sent = sents[si % len(sents)] if sents else "Review content."
                si += 1
                questions.append({
                    "text": "Which statement correctly reflects the content?",
                    "question_type": "mcq_single", "marks": 1,
                    "explanation": sent[:120],
                    "options": [
                        {"text": sent[:80] + ("..." if len(sent) > 80 else ""), "is_correct": True},
                        {"text": "The opposite is stated in the text.", "is_correct": False},
                        {"text": "Not mentioned in the content.", "is_correct": False},
                        {"text": "Only partially correct.", "is_correct": False},
                    ],
                })
        elif qtype == "true_false":
            sent = next((sents[i] for i in range(si, si + len(sents) + 1)
                         if sents[i % len(sents)] not in used), sents[si % len(sents)] if sents else "Review.")
            si += 1; used.add(sent)
            questions.append({
                "text": f"True or False: {sent}.",
                "question_type": "true_false", "marks": 1,
                "explanation": "This statement is directly stated in the content.",
                "options": [{"text": "True", "is_correct": True},
                            {"text": "False", "is_correct": False}],
            })
        else:
            fact = next((facts[i] for i in range(fi, min(fi+30, len(facts)))
                         if facts[i]["sentence"] not in used), None)
            if fact:
                fi += 1; used.add(fact["sentence"])
                qtxt = f"Explain: {fact['subject'].strip('.')} — as described in the content."
                expl = fact["sentence"]
            else:
                sent = sents[si % len(sents)] if sents else "Review content."
                si += 1
                qtxt = f'In your own words, explain: "{sent[:100]}".'
                expl = sent
            questions.append({"text": qtxt, "question_type": "short_answer",
                               "marks": 2, "explanation": expl, "options": []})

    return {
        "title":            exam_title or "Generated Exam",
        "description":      "Auto-generated from syllabus content.",
        "duration_minutes": time_limit,
        "total_marks":      sum(q["marks"] for q in questions),
        "pass_percentage":  40,
        "negative_marking": False,
        "sections":         [{"title": "Section 1", "description": "", "questions": questions}],
        "coverage_report": {
            "total_topics_in_syllabus": max(1, len(facts)),
            "topics_covered": min(len(facts), num_questions),
            "topics_missing": 0, "coverage_percentage": 100,
            "total_questions": len(questions),
            "question_distribution": {"by_type": {}, "by_difficulty": {}},
            "weak_areas": [], "source": "fallback",
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
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

    # ── STEP 1: Question bank? → parse directly, NO AI ──────────────────────
    if _is_question_bank(syllabus_text):
        logger.info("Question bank detected — parsing directly, skipping AI")
        try:
            return _parse_question_bank(
                syllabus_text, num_questions, time_limit, exam_title
            )
        except Exception as exc:
            logger.error("QB parser failed: %s — cannot fall back to AI for a question bank", exc)
            raise RuntimeError(
                f"This looks like a question bank but parsing failed: {exc}"
            ) from exc

    # ── STEP 2: Regular syllabus → try Gemini ───────────────────────────────
    if GEMINI_API_KEY:
        prompt = _build_prompt(syllabus_text, num_questions, difficulty,
                               question_types, time_limit, exam_title, focus_topics)
        try:
            raw    = await _call_gemini(prompt)
            data   = _extract_json(raw)
            result = _normalise(data, num_questions, time_limit)
            logger.info("Gemini generated %d questions",
                        sum(len(s["questions"]) for s in result["sections"]))
            return result
        except Exception as exc:
            logger.error("Gemini failed (%s) — using fallback generator", exc)

    # ── STEP 3: Fallback rule-based generator ────────────────────────────────
    logger.warning("Using fallback generator")
    return _fallback_generate(syllabus_text, num_questions, difficulty,
                              question_types, time_limit, exam_title)


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
    combined = ""
    if TAVILY_API_KEY and topics:
        try:
            query = ", ".join(topics[:5]) + (f" {extra_context}" if extra_context else "")
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    "https://api.tavily.com/search",
                    json={"api_key": TAVILY_API_KEY, "query": query, "max_results": 5},
                    headers={"Content-Type": "application/json"},
                )
            if r.status_code == 200:
                results = r.json().get("results", [])
                combined = "\n\n".join(
                    f"{x.get('title','')}\n{x.get('content','')}" for x in results
                )
        except Exception as exc:
            logger.warning("Tavily failed: %s", exc)

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
