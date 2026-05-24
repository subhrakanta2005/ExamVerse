"""
ExamVerse / ExamForge — Rule-Based Exam Generator
==================================================
Zero external API. No keys. No quota. Always free.

Works by:
  1. Extracting text from uploaded syllabus (TXT / PDF / DOCX)
  2. Parsing sections, topics, key terms, and definitions
  3. Generating MCQ / True-False / Short Answer using templates
  4. Producing a syllabus coverage report

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
# 2.  SYLLABUS PARSER
# ══════════════════════════════════════════════════════════════════════════════

def _parse_syllabus(text: str) -> dict:
    """
    Extract structured data from raw syllabus text.
    Returns: sections, key_terms, definitions, sentences
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    heading_re  = re.compile(
        r'^(unit|chapter|module|section|part|topic)\s*[\d\.:]+\s*[:\-]?\s*(.+)', re.I
    )
    numbered_re = re.compile(r'^[\d]+[\.)\-]\s+(.+)')
    bullet_re   = re.compile(r'^[\-\*\•]\s+(.+)')
    define_re   = re.compile(
        r'(.+?)\s*(?:\bis\b|\bare\b|refers to|defined as|means)\s+(.+)', re.I
    )

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

        # Definitions
        dm = define_re.match(line)
        if dm and len(dm.group(1).split()) <= 6:
            definitions.append({
                "term":       dm.group(1).strip().rstrip(".,"),
                "definition": dm.group(2).strip().rstrip(".,"),
            })

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
        if tc not in seen and len(tc) > 2:
            seen.add(tc)
            unique_terms.append(t.strip(string.punctuation))

    return {
        "sections":    sections,
        "key_terms":   unique_terms[:80],
        "definitions": definitions[:25],
        "sentences":   all_sentences[:100],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3.  QUESTION BUILDERS
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
        "text":           f"True or False: {statement}",
        "question_type":  "true_false",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    (
            f"The statement is {'true' if is_true else 'false'}. "
            f"'{topic}' {'is' if is_true else 'is not'} a core part of {section_title}."
        ),
        "correct_answer": "True" if is_true else "False",
        "options":        options,
    }


def _make_fill_blank(term: str, sentence: str, difficulty: str) -> dict:
    blanked = re.sub(re.escape(term), "______", sentence, count=1, flags=re.I)
    return {
        "text":           f"Fill in the blank: {blanked}",
        "question_type":  "short_answer",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    f"The correct answer is '{term}'.",
        "correct_answer": term,
        "options":        [],
    }


def _make_short_answer(topic: str, section_title: str, difficulty: str) -> dict:
    words  = topic.split()
    templates = [
        (f"Name one key aspect of {topic}.",               words[0] if words else topic),
        (f"In one or two words, describe '{topic}'.",       words[-1] if words else topic),
        (f"Which section covers the topic '{topic}'?",      section_title),
        (f"What is the significance of {topic} in {section_title}?",
         f"{topic} is a core concept in {section_title}."),
    ]
    q_text, answer = random.choice(templates)
    return {
        "text":           q_text,
        "question_type":  "short_answer",
        "marks":          _marks(difficulty),
        "difficulty":     difficulty,
        "explanation":    f"'{topic}' is part of the {section_title} section.",
        "correct_answer": answer,
        "options":        [],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4.  SYLLABUS COVERAGE REPORT
# ══════════════════════════════════════════════════════════════════════════════

def _build_coverage_report(
    parsed:      dict,
    questions:   list,
    all_sections: list,
) -> dict:
    """
    Analyse how well the generated questions cover the syllabus.
    Returns a structured coverage report.
    """
    # Topics detected in syllabus
    all_topics = [
        {"topic": t, "section": s["title"]}
        for s in all_sections
        for t in s["topics"]
    ]
    total_topics = len(all_topics)

    # Which topics appear in at least one question?
    covered_topics: set[str] = set()
    topic_question_count: dict[str, int] = {}

    for q in questions:
        q_text = q["text"].lower()
        for entry in all_topics:
            t = entry["topic"]
            if t.lower() in q_text or (t.split()[0].lower() in q_text if t.split() else False):
                covered_topics.add(t)
                topic_question_count[t] = topic_question_count.get(t, 0) + 1

    missing_topics = [
        e["topic"] for e in all_topics if e["topic"] not in covered_topics
    ]

    coverage_pct = (
        round(len(covered_topics) / total_topics * 100, 1) if total_topics else 0.0
    )

    # Questions per section
    section_counts: dict[str, int] = {s["title"]: 0 for s in all_sections}
    for sec in all_sections:
        section_counts[sec["title"]] = sum(
            len(s.get("questions", [])) for s in []  # placeholder
        )
    # Count from the flat list
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

    # Weak areas: sections with < 1 question per 3 topics
    weak_areas = []
    for s in all_sections:
        n_topics = len(s["topics"])
        n_qs     = section_counts.get(s["title"], 0)
        if n_topics > 0 and n_qs < max(1, n_topics // 3):
            weak_areas.append({
                "section":         s["title"],
                "topics_in_syllabus": n_topics,
                "questions_generated": n_qs,
                "recommendation":  f"Add more questions for '{s['title']}' to improve coverage.",
            })

    # Question distribution by type
    type_dist: dict[str, int] = {}
    diff_dist: dict[str, int] = {}
    for q in questions:
        qt = q.get("question_type", "unknown")
        qd = q.get("difficulty", "unknown")
        type_dist[qt] = type_dist.get(qt, 0) + 1
        diff_dist[qd] = diff_dist.get(qd, 0) + 1

    return {
        "total_topics_in_syllabus": total_topics,
        "topics_covered":          len(covered_topics),
        "topics_missing":          len(missing_topics),
        "coverage_percentage":     coverage_pct,
        "covered_topic_list":      sorted(covered_topics),
        "missing_topic_list":      missing_topics[:30],
        "questions_per_topic":     questions_per_topic,
        "weak_areas":              weak_areas,
        "question_distribution": {
            "by_type":       type_dist,
            "by_difficulty": diff_dist,
        },
        "sections_detected": [s["title"] for s in all_sections],
        "total_questions":   len(questions),
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5.  MAIN ENTRY POINT
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
    # Use a stable seed so the same syllabus always gives the same exam
    random.seed(hash(syllabus_text[:200]) % (2**31))

    parsed    = _parse_syllabus(syllabus_text)
    sections  = parsed["sections"]
    key_terms = parsed["key_terms"]
    defs      = parsed["definitions"]
    sentences = parsed["sentences"]

    # Optionally filter to specific focus topics
    if focus_topics:
        focus_lower = [f.strip().lower() for f in focus_topics.split(",")]
        filtered = [s for s in sections if any(f in s["title"].lower() for f in focus_lower)]
        sections = filtered if filtered else sections

    # Flatten all topics
    all_topics_flat = [(t, s["title"]) for s in sections for t in s["topics"]]
    if not all_topics_flat:
        all_topics_flat = [
            (line, "General")
            for line in syllabus_text.splitlines()
            if line.strip()
        ]

    random.shuffle(all_topics_flat)

    # Difficulty sequence
    diff_map = {
        "easy":   ["easy"] * num_questions,
        "medium": ["medium"] * num_questions,
        "hard":   ["hard"] * num_questions,
        "mixed":  (["easy", "medium", "medium", "hard"] * (num_questions // 4 + 1))[:num_questions],
    }
    difficulties = diff_map.get(difficulty, ["medium"] * num_questions)

    # Question type sequence
    if question_types == "mcq":
        type_cycle = ["mcq"] * num_questions
    elif question_types == "true_false":
        type_cycle = ["true_false"] * num_questions
    elif question_types == "short":
        type_cycle = ["short_answer"] * num_questions
    else:  # mixed
        type_cycle = (
            ["mcq", "mcq", "mcq", "true_false", "true_false", "short_answer"]
            * (num_questions // 6 + 1)
        )[:num_questions]

    # Generate questions
    all_questions: list[dict] = []
    def_idx   = 0
    topic_idx = 0
    all_topic_texts = [t for t, _ in all_topics_flat]

    for i in range(num_questions):
        q_type = type_cycle[i]
        diff   = difficulties[i]
        topic, sec_title = all_topics_flat[topic_idx % len(all_topics_flat)]

        if q_type == "mcq":
            if def_idx < len(defs):
                d       = defs[def_idx]; def_idx += 1
                q       = _make_definition_mcq(d["term"], d["definition"], key_terms, diff)
            else:
                q = _make_topic_mcq(topic, sec_title, all_topic_texts, diff)

        elif q_type == "true_false":
            q = _make_true_false(topic, sec_title, diff)

        else:  # short_answer
            first_word   = topic.split()[0] if topic.split() else topic
            matching_sents = [s for s in sentences if first_word.lower() in s.lower()]
            if matching_sents:
                q = _make_fill_blank(first_word, matching_sents[0], diff)
            else:
                q = _make_short_answer(topic, sec_title, diff)

        all_questions.append(q)
        topic_idx += 1

    # ── Group questions into output sections ───────────────────────────────────
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

    # ── Metadata ───────────────────────────────────────────────────────────────
    total_marks  = sum(q["marks"] for q in all_questions)
    title        = exam_title or _infer_title(syllabus_text)

    # ── Coverage report ────────────────────────────────────────────────────────
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


def _infer_title(text: str) -> str:
    """Guess an exam title from the first meaningful line of the syllabus."""
    for line in text.splitlines():
        line = line.strip()
        if 5 < len(line) < 80 and not line.startswith(("#", "-", "*", ".")):
            return f"{line} — Exam"
    return "Auto-Generated Exam"
