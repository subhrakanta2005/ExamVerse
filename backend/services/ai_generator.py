"""
ExamVerse / ExamForge — Rule-Based Exam Generator
==================================================
Zero external API. No keys. No quota. Always free.

Works by:
  1. Extracting text from uploaded syllabus (TXT / PDF / DOCX)
  2. *** NEW: Detecting and parsing structured MCQ format directly ***
  3. Stripping structural labels before the regex pipeline touches text
  4. Parsing sections, topics, key terms, and definitions
  5. Generating MCQ / True-False / Short Answer using templates
  6. Producing a syllabus coverage report

Put this file at:  backend/services/ai_generator.py
"""

import re
import random
import string
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# 1.  TEXT EXTRACTION  (TXT / PDF / DOCX)
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
        except ImportError:
            return file_bytes.decode("utf-8", errors="ignore")
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
# 2.  STRUCTURED MCQ PRE-PARSER  ← NEW
#     Detects and directly parses content that already contains formatted MCQs
#     so we never feed them through the broken regex pipeline.
# ══════════════════════════════════════════════════════════════════════════════

# Labels that must NEVER be treated as definition terms or question content.
_STRUCTURAL_LABELS = re.compile(
    r'^\s*('
    r'explanation|answer|correct answer|solution|hint|note|reference|'
    r'Q\s*\d+|question\s*\d+|'
    r'section|chapter|unit|module|part|topic'
    r')\s*[:\.\-]\s*',
    re.IGNORECASE,
)

# Matches option lines like:  (A) text  |  A) text  |  A. text  |  a) text
_OPTION_RE = re.compile(r'^\s*[\(\[]?([A-Da-d])[\)\]\.]\s+(.+)', re.IGNORECASE)

# Matches question starters like:  Q1. | Q1) | 1. | 1) | Question 1.
_QUESTION_START_RE = re.compile(
    r'^\s*(?:Q\.?\s*\d+[\.\):]?|Question\s+\d+[\.\):]?|\d+[\.\)])\s+(.+)',
    re.IGNORECASE,
)

# Matches a declared answer line: "Answer: A" or "Correct answer: B"
_ANSWER_LINE_RE = re.compile(
    r'^\s*(?:correct\s+)?answer\s*[:\-]\s*([A-Da-d])',
    re.IGNORECASE,
)

# Matches an explanation line: "Explanation: ..."
_EXPLANATION_RE = re.compile(r'^\s*explanation\s*[:\-]\s*(.+)', re.IGNORECASE)


def _is_structured_mcq(text: str) -> bool:
    """
    Heuristic: returns True when the text looks like pre-formatted MCQ content.
    We require at least 2 question starters AND at least 4 option lines.
    """
    q_count  = sum(1 for l in text.splitlines() if _QUESTION_START_RE.match(l))
    opt_count = sum(1 for l in text.splitlines() if _OPTION_RE.match(l))
    return q_count >= 2 and opt_count >= 4


def parse_structured_mcq_text(
    text: str,
    difficulty: str = "medium",
    num_questions: Optional[int] = None,
) -> list[dict]:
    """
    Directly parse pre-formatted MCQ text into the internal question dict format.

    Supported format (flexible):
        Q1. <question text>
        (A) option one
        (B) option two
        (C) option three
        (D) option four
        Answer: B
        Explanation: <optional explanation text>

    Lines that start with structural labels (Explanation:, Answer:, Q1., etc.)
    are handled correctly and are never fed to the definition extractor.

    Returns a list of question dicts compatible with generate_exam_from_syllabus output.
    """
    questions = []
    lines     = text.splitlines()

    current_q_text   = None
    current_options  = []      # list of (letter, text)
    current_answer   = None    # letter, e.g. "B"
    current_explain  = None

    def _flush():
        """Convert accumulated state into a question dict and reset."""
        nonlocal current_q_text, current_options, current_answer, current_explain
        if not current_q_text:
            return

        # Map letter → option text
        letter_map = {letter.upper(): txt for letter, txt in current_options}
        correct_text = letter_map.get(
            (current_answer or "").upper(), ""
        )

        options_out = []
        for letter, txt in current_options:
            options_out.append({
                "text":       txt.strip(),
                "is_correct": letter.upper() == (current_answer or "").upper(),
            })

        questions.append({
            "text":           current_q_text.strip(),
            "question_type":  "mcq",
            "marks":          _marks(difficulty, 2),
            "difficulty":     difficulty,
            "explanation":    (current_explain or "").strip(),
            "correct_answer": correct_text.strip(),
            "options":        options_out,
        })

        current_q_text  = None
        current_options = []
        current_answer  = None
        current_explain = None

    for raw_line in lines:
        line = raw_line.rstrip()

        # Skip blank lines between questions
        if not line.strip():
            continue

        # ── Question start ─────────────────────────────────────────────────
        qm = _QUESTION_START_RE.match(line)
        if qm:
            _flush()                          # save previous question
            current_q_text = qm.group(1)
            continue

        # ── Option line ────────────────────────────────────────────────────
        om = _OPTION_RE.match(line)
        if om and current_q_text is not None:
            current_options.append((om.group(1), om.group(2)))
            continue

        # ── Answer declaration ─────────────────────────────────────────────
        am = _ANSWER_LINE_RE.match(line)
        if am:
            current_answer = am.group(1).upper()
            continue

        # ── Explanation (safe: never fed to define_re) ─────────────────────
        em = _EXPLANATION_RE.match(line)
        if em:
            current_explain = em.group(1)
            continue

        # ── Continuation of current question text ──────────────────────────
        if current_q_text is not None and not current_options:
            # Multi-line question text — append
            current_q_text += " " + line.strip()

    _flush()  # last question

    if num_questions:
        questions = questions[:num_questions]

    return questions


# ══════════════════════════════════════════════════════════════════════════════
# 3.  TEXT PRE-PROCESSING  ← NEW
#     Strip structural labels BEFORE the regex pipeline sees the text.
#     This is what prevents "Explanation: Odisha is..." → term="Explanation".
# ══════════════════════════════════════════════════════════════════════════════

def _preprocess_text_for_parser(text: str) -> str:
    """
    Remove or neutralise lines that carry structural labels so they don't
    pollute term extraction or definition parsing.

    Rules:
    - Lines that consist ONLY of a structural label + colon are dropped.
    - Lines that START with a structural label followed by content have the
      label prefix stripped (keeping the content).
    - Question-number prefixes (Q1., 1., etc.) are stripped.
    """
    cleaned = []
    for line in text.splitlines():
        stripped = line.strip()

        # Drop completely empty lines (keep for now; syllabus parser handles them)
        if not stripped:
            cleaned.append("")
            continue

        # Drop lines that are ONLY a label with no real content after the colon
        # e.g. "Answer:" or "Explanation:" alone
        if re.match(
            r'^\s*(?:explanation|answer|correct answer|solution|hint|note)\s*[:\.\-]?\s*$',
            stripped, re.IGNORECASE
        ):
            continue

        # Strip structural label prefix and keep the rest of the content
        # e.g. "Explanation: Odisha is bordered by..." → "Odisha is bordered by..."
        m = _STRUCTURAL_LABELS.match(stripped)
        if m:
            remainder = stripped[m.end():].strip()
            if remainder:
                cleaned.append(remainder)
            # If there's nothing after the label, just drop the line
            continue

        # Strip question-number prefixes so "Q1. What is ..." becomes "What is ..."
        qm = _QUESTION_START_RE.match(stripped)
        if qm:
            # For the syllabus parser we keep the question text but drop the number
            cleaned.append(qm.group(1))
            continue

        # Option lines (A) ... (D) are noise for the rule-based parser
        if _OPTION_RE.match(stripped):
            # Keep the text part only (useful for key-terms)
            om = _OPTION_RE.match(stripped)
            if om:
                cleaned.append(om.group(2))
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


# ══════════════════════════════════════════════════════════════════════════════
# 4.  SYLLABUS PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_syllabus(text: str) -> dict:
    """
    Extract structured data from raw syllabus text.
    Runs AFTER _preprocess_text_for_parser so structural labels are gone.
    Returns: sections, key_terms, definitions, sentences
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    heading_re  = re.compile(
        r'^(unit|chapter|module|section|part|topic)\s*[\d\.:]+ \s*[:\-]?\s*(.+)', re.I
    )
    numbered_re = re.compile(r'^[\d]+[\.)\-]\s+(.+)')
    bullet_re   = re.compile(r'^[\-\*\•]\s+(.+)')

    # Tightened: require term to be ≤5 words and NOT match known structural words
    define_re   = re.compile(
        r'^(.+?)\s*(?:\bis\b|\bare\b|refers to|defined as|means)\s+(.+)',
        re.I,
    )
    # Words that must not be captured as definition terms
    _BAD_TERMS = {
        "explanation", "answer", "solution", "hint", "note",
        "reference", "question", "correct", "section", "chapter",
        "unit", "module", "part", "topic",
    }

    sections        = []
    current_section = None
    current_topics  = []
    key_terms       = []
    definitions     = []
    all_sentences   = []

    for line in lines:
        # Collect sentences for fill-in-the-blank questions
        for sent in re.split(r'(?<=[.!?])\s+', line):
            if len(sent.strip()) > 20:
                all_sentences.append(sent.strip())

        # Definitions — guard against structural label words as terms
        dm = define_re.match(line)
        if dm:
            term = dm.group(1).strip().rstrip(".,")
            defn = dm.group(2).strip().rstrip(".,")
            term_words = len(term.split())
            term_lower = term.lower()
            if (
                term_words <= 5
                and term_lower not in _BAD_TERMS
                and not re.search(r'\d', term)          # no numbers in term
                and len(term) > 2
            ):
                definitions.append({"term": term, "definition": defn})

        # Section heading
        hm = heading_re.match(line)
        if hm:
            if current_section and current_topics:
                sections.append({"title": current_section, "topics": current_topics[:]})
            current_section = hm.group(2).strip()
            current_topics  = []
            continue

        # Numbered or bullet topic
        nm = numbered_re.match(line) or bullet_re.match(line)
        if nm:
            topic = nm.group(1).strip()
            current_topics.append(topic)
            key_terms.extend(
                t.strip() for t in re.split(r"[,;]", topic)
                if len(t.strip()) > 2
            )
            continue

        # Short plain line → treat as topic
        if 5 < len(line) <= 100:
            current_topics.append(line)
            key_terms.extend(
                w for w in line.split() if w[0].isupper() and len(w) > 3
            )

    if current_section and current_topics:
        sections.append({"title": current_section, "topics": current_topics})

    if not sections:
        sections = [{"title": "General", "topics": lines[:40]}]

    # Deduplicate key terms
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
        "key_terms":   unique_terms[:80],
        "definitions": definitions[:25],
        "sentences":   all_sentences[:100],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5.  QUESTION BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

def _marks(difficulty: str, base: int = 1) -> int:
    return {"easy": base, "medium": base + 1, "hard": base + 2}.get(difficulty, base)


def _make_definition_mcq(term: str, definition: str, all_terms: list, difficulty: str) -> dict:
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
        "text":           f"What is {term}?",
        "question_type":  "mcq",
        "marks":          _marks(difficulty, 2),
        "difficulty":     difficulty,
        "explanation":    f"{term} refers to {definition}.",
        "correct_answer": definition,
        "options":        options,
    }


def _make_topic_mcq(topic: str, section_title: str, all_topics: list, difficulty: str) -> dict:
    wrong = [t for t in all_topics if t != topic and len(t) > 5]
    random.shuffle(wrong)
    distractors = wrong[:3]
    if len(distractors) < 3:
        distractors += [
            "None of the above concepts",
            "An unrelated external framework",
            "A deprecated methodology",
        ][:3 - len(distractors)]
    options = [{"text": topic, "is_correct": True}] + \
              [{"text": d, "is_correct": False} for d in distractors[:3]]
    random.shuffle(options)
    return {
        "text":           f"Which of the following is a key concept covered under '{section_title}'?",
        "question_type":  "mcq",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    f"'{topic}' is a core concept in the {section_title} section.",
        "correct_answer": topic,
        "options":        options,
    }


def _make_true_false(topic: str, section_title: str, difficulty: str) -> dict:
    true_tpl = [
        f"{topic} is a fundamental concept in {section_title}.",
        f"Understanding {topic} is essential for mastering {section_title}.",
        f"{topic} plays an important role in {section_title}.",
        f"{topic} is included in the scope of {section_title}.",
    ]
    false_tpl = [
        f"{topic} is completely unrelated to {section_title}.",
        f"{topic} is only applicable outside the scope of {section_title}.",
        f"{topic} was removed from modern {section_title} practices.",
        f"{topic} contradicts the core principles of {section_title}.",
    ]
    is_true   = random.choice([True, False])
    statement = random.choice(true_tpl if is_true else false_tpl)
    options   = [
        {"text": "True",  "is_correct": is_true},
        {"text": "False", "is_correct": not is_true},
    ]
    return {
        "text":           statement,
        "question_type":  "true_false",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    f"This statement about {topic} in {section_title} is {'true' if is_true else 'false'}.",
        "correct_answer": "True" if is_true else "False",
        "options":        options,
    }


def _make_fill_blank(keyword: str, sentence: str, difficulty: str) -> dict:
    blanked = re.sub(
        re.escape(keyword), "______", sentence, count=1, flags=re.IGNORECASE
    )
    return {
        "text":           f"Fill in the blank: {blanked}",
        "question_type":  "short_answer",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    f"The missing word is '{keyword}'.",
        "correct_answer": keyword,
        "options":        [],
    }


def _make_short_answer(topic: str, section_title: str, difficulty: str) -> dict:
    templates = [
        f"Briefly explain the significance of {topic} in the context of {section_title}.",
        f"What role does {topic} play in {section_title}?",
        f"Describe the key characteristics of {topic} as covered in {section_title}.",
        f"How does {topic} relate to the broader themes of {section_title}?",
    ]
    return {
        "text":           random.choice(templates),
        "question_type":  "short_answer",
        "marks":          _marks(difficulty, 2),
        "difficulty":     difficulty,
        "explanation":    f"{topic} is an important concept within {section_title}.",
        "correct_answer": f"Answer should cover key aspects of {topic}.",
        "options":        [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6.  COVERAGE REPORT
# ══════════════════════════════════════════════════════════════════════════════

def _build_coverage_report(parsed: dict, questions: list, all_sections: list) -> dict:
    all_topics_flat  = [t for s in all_sections for t in s["topics"]]
    total_topics     = len(all_topics_flat)
    covered_topics   = set()
    missing_topics   = []
    topic_question_count: dict[str, int] = {}

    q_texts_lower = [q["text"].lower() for q in questions]
    for topic in all_topics_flat:
        tl = topic.lower()
        if any(tl in qt or any(w in qt for w in tl.split() if len(w) > 4)
               for qt in q_texts_lower):
            covered_topics.add(topic)
            topic_question_count[topic] = sum(1 for qt in q_texts_lower if tl in qt)
        else:
            missing_topics.append(topic)

    coverage_pct = round(len(covered_topics) / max(total_topics, 1) * 100, 1)

    section_counts: dict[str, int] = {s["title"]: 0 for s in all_sections}
    for q in questions:
        for sec in all_sections:
            sec_topics_lower = [t.lower() for t in sec["topics"]]
            if any(t in q["text"].lower() for t in sec_topics_lower):
                section_counts[sec["title"]] = section_counts.get(sec["title"], 0) + 1
                break

    questions_per_topic = [
        {"topic": t, "count": c} for t, c in sorted(
            topic_question_count.items(), key=lambda x: -x[1]
        )
    ]

    weak_areas = []
    for s in all_sections:
        n_topics = len(s["topics"])
        n_qs     = section_counts.get(s["title"], 0)
        if n_topics > 0 and n_qs < max(1, n_topics // 3):
            weak_areas.append({
                "section":              s["title"],
                "topics_in_syllabus":   n_topics,
                "questions_generated":  n_qs,
                "recommendation":       f"Add more questions for '{s['title']}' to improve coverage.",
            })

    type_dist: dict[str, int] = {}
    diff_dist: dict[str, int] = {}
    for q in questions:
        qt = q.get("question_type", "unknown")
        qd = q.get("difficulty", "unknown")
        type_dist[qt] = type_dist.get(qt, 0) + 1
        diff_dist[qd] = diff_dist.get(qd, 0) + 1

    return {
        "total_topics_in_syllabus": total_topics,
        "topics_covered":           len(covered_topics),
        "topics_missing":           len(missing_topics),
        "coverage_percentage":      coverage_pct,
        "covered_topic_list":       sorted(covered_topics),
        "missing_topic_list":       missing_topics[:30],
        "questions_per_topic":      questions_per_topic,
        "weak_areas":               weak_areas,
        "question_distribution": {
            "by_type":       type_dist,
            "by_difficulty": diff_dist,
        },
        "sections_detected": [s["title"] for s in all_sections],
        "total_questions":   len(questions),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7.  MAIN ENTRY POINT
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
    No API, no keys, works completely offline.

    NEW BEHAVIOUR:
    - If the text looks like pre-formatted MCQs, parse it directly with
      parse_structured_mcq_text() and skip the rule-based generator.
    - Otherwise, strip structural labels first, then run the rule-based pipeline.

    Returns:
        {
          "title": ...,
          "description": ...,
          "duration_minutes": ...,
          "total_marks": ...,
          "pass_percentage": ...,
          "negative_marking": ...,
          "sections": [...],          ← exam questions grouped by topic
          "coverage_report": { ... }  ← syllabus analysis
        }
    """
    random.seed(hash(syllabus_text[:200]) % (2**31))

    title = exam_title or _infer_title(syllabus_text)

    # ── PATH A: Structured MCQ input ──────────────────────────────────────────
    if _is_structured_mcq(syllabus_text):
        all_questions = parse_structured_mcq_text(
            syllabus_text,
            difficulty=difficulty if difficulty != "mixed" else "medium",
            num_questions=num_questions,
        )

        # Pad if not enough questions were parsed
        if len(all_questions) < num_questions:
            # Fall through to rule-based for remaining questions using cleaned text
            cleaned_text = _preprocess_text_for_parser(syllabus_text)
            extra = _generate_rule_based_questions(
                cleaned_text,
                num_questions - len(all_questions),
                difficulty,
                question_types,
                focus_topics,
            )
            all_questions.extend(extra)

        # Group into a single section (structured input is already self-contained)
        sections_out = [{
            "title":       title,
            "description": "Questions parsed directly from structured MCQ input.",
            "questions":   all_questions[:num_questions],
        }]

        total_marks    = sum(q["marks"] for q in all_questions[:num_questions])
        parsed_dummy   = {"sections": [{"title": title, "topics": []}],
                          "key_terms": [], "definitions": [], "sentences": []}
        coverage_report = _build_coverage_report(
            parsed_dummy, all_questions[:num_questions],
            [{"title": title, "topics": []}]
        )
        coverage_report["note"] = (
            "Input was detected as pre-formatted MCQ text and parsed directly. "
            "Coverage analysis is limited for this format."
        )

        return {
            "title":            title,
            "description":      "Exam generated from structured MCQ input.",
            "duration_minutes": time_limit,
            "total_marks":      total_marks,
            "pass_percentage":  40,
            "negative_marking": False,
            "sections":         sections_out,
            "coverage_report":  coverage_report,
        }

    # ── PATH B: Generic syllabus / plain-text input ───────────────────────────
    # Pre-process to strip structural labels before the regex pipeline runs
    cleaned_text  = _preprocess_text_for_parser(syllabus_text)
    all_questions = _generate_rule_based_questions(
        cleaned_text, num_questions, difficulty, question_types, focus_topics
    )

    parsed   = _parse_syllabus(cleaned_text)
    sections = parsed["sections"]

    # Group into output sections
    n_sections  = max(1, len(sections))
    chunk_size  = max(1, (num_questions + n_sections - 1) // n_sections)
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
        "description":      (
            f"Auto-generated exam covering {len(sections)} section(s) "
            f"from the uploaded syllabus."
        ),
        "duration_minutes": time_limit,
        "total_marks":      total_marks,
        "pass_percentage":  40,
        "negative_marking": False,
        "sections":         output_sections,
        "coverage_report":  coverage_report,
    }


# ── Internal helper: rule-based question generator ───────────────────────────

def _generate_rule_based_questions(
    text:           str,
    num_questions:  int,
    difficulty:     str,
    question_types: str,
    focus_topics:   Optional[str],
) -> list[dict]:
    """
    Core rule-based generator.  Runs on PRE-PROCESSED text (labels stripped).
    Extracted from generate_exam_from_syllabus so both paths can reuse it.
    """
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
        all_topics_flat = [
            (line, "General")
            for line in text.splitlines()
            if line.strip()
        ]

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
        type_cycle = (
            ["mcq", "mcq", "mcq", "true_false", "true_false", "short_answer"]
            * (num_questions // 6 + 1)
        )[:num_questions]

    all_questions: list[dict] = []
    def_idx       = 0
    topic_idx     = 0
    all_topic_texts = [t for t, _ in all_topics_flat]

    for i in range(num_questions):
        q_type = type_cycle[i]
        diff   = difficulties[i]
        topic, sec_title = all_topics_flat[topic_idx % len(all_topics_flat)]

        if q_type == "mcq":
            if def_idx < len(defs):
                d   = defs[def_idx]; def_idx += 1
                q   = _make_definition_mcq(d["term"], d["definition"], key_terms, diff)
            else:
                q   = _make_topic_mcq(topic, sec_title, all_topic_texts, diff)

        elif q_type == "true_false":
            q = _make_true_false(topic, sec_title, diff)

        else:  # short_answer
            first_word      = topic.split()[0] if topic.split() else topic
            matching_sents  = [s for s in sentences if first_word.lower() in s.lower()]
            if matching_sents:
                q = _make_fill_blank(first_word, matching_sents[0], diff)
            else:
                q = _make_short_answer(topic, sec_title, diff)

        all_questions.append(q)
        topic_idx += 1

    return all_questions


# ══════════════════════════════════════════════════════════════════════════════
# 8.  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _infer_title(text: str) -> str:
    """Guess an exam title from the first meaningful line of the syllabus."""
    for line in text.splitlines():
        line = line.strip()
        if 5 < len(line) < 80 and not line.startswith(("#", "-", "*", ".")):
            return f"{line} — Exam"
    return "Auto-Generated Exam"
