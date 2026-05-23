from sqlalchemy.orm import Session
from datetime import datetime
import models


def auto_grade_attempt(attempt_id: int, db: Session) -> models.Result:
    """Auto-grade objective questions. Subjective questions remain pending."""
    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    if not attempt:
        raise ValueError(f"Attempt {attempt_id} not found")
    
    exam = attempt.exam
    answers = {a.question_id: a for a in attempt.answers}
    
    total_marks = 0.0
    obtained_marks = 0.0
    correct_count = 0
    incorrect_count = 0
    unattempted_count = 0
    section_scores = {}
    needs_manual = False

    for section in exam.sections:
        sec_total = 0.0
        sec_obtained = 0.0

        for question in section.questions:
            total_marks += question.marks
            sec_total += question.marks

            answer = answers.get(question.id)
            if not answer:
                unattempted_count += 1
                continue

            q_type = question.question_type
            is_correct = None
            marks = 0.0

            if q_type == models.QuestionType.MCQ_SINGLE:
                correct_opts = {o.id for o in question.options if o.is_correct}
                selected = set(answer.selected_option_ids or [])
                is_correct = selected == correct_opts and len(selected) == 1
                if is_correct:
                    marks = question.marks
                elif selected:
                    marks = -question.negative_marks if exam.negative_marking else 0

            elif q_type == models.QuestionType.MCQ_MULTI:
                correct_opts = {o.id for o in question.options if o.is_correct}
                selected = set(answer.selected_option_ids or [])
                is_correct = selected == correct_opts
                if is_correct:
                    marks = question.marks
                elif selected:
                    marks = -question.negative_marks if exam.negative_marking else 0

            elif q_type == models.QuestionType.TRUE_FALSE:
                correct_opts = {o.id for o in question.options if o.is_correct}
                selected = set(answer.selected_option_ids or [])
                is_correct = selected == correct_opts
                marks = question.marks if is_correct else (
                    -question.negative_marks if exam.negative_marking and selected else 0
                )

            elif q_type == models.QuestionType.NUMERIC:
                correct_opts = [o for o in question.options if o.is_correct]
                if correct_opts and answer.numeric_answer is not None:
                    try:
                        expected = float(correct_opts[0].text)
                        is_correct = abs(answer.numeric_answer - expected) < 0.001
                        marks = question.marks if is_correct else (
                            -question.negative_marks if exam.negative_marking else 0
                        )
                    except ValueError:
                        needs_manual = True

            elif q_type == models.QuestionType.FILL_BLANK:
                correct_opts = [o for o in question.options if o.is_correct]
                if correct_opts and answer.text_answer:
                    is_correct = answer.text_answer.strip().lower() == correct_opts[0].text.strip().lower()
                    marks = question.marks if is_correct else 0

            elif q_type in (
                models.QuestionType.SHORT_ANSWER,
                models.QuestionType.LONG_ANSWER,
                models.QuestionType.FILE_UPLOAD,
                models.QuestionType.MATCH,
                models.QuestionType.ASSERTION_REASON,
            ):
                # Mark for manual evaluation
                needs_manual = True
                answer.is_correct = None
                db.add(answer)
                continue

            answer.is_correct = is_correct
            answer.marks_obtained = max(0.0, marks) if marks < 0 else marks
            # Allow negative for scoring
            if is_correct:
                correct_count += 1
                obtained_marks += marks
                sec_obtained += marks
            elif is_correct is False and answer.selected_option_ids:
                incorrect_count += 1
                obtained_marks += marks  # negative
                sec_obtained += marks
            
            db.add(answer)

        section_scores[str(section.id)] = {
            "title": section.title,
            "total": sec_total,
            "obtained": sec_obtained
        }

    percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
    is_passed = percentage >= exam.pass_percentage

    # Create or update result
    result = db.query(models.Result).filter(models.Result.attempt_id == attempt_id).first()
    if not result:
        result = models.Result(attempt_id=attempt_id, user_id=attempt.user_id, exam_id=attempt.exam_id)
        db.add(result)

    result.total_marks = total_marks
    result.obtained_marks = max(0.0, obtained_marks)
    result.percentage = max(0.0, percentage)
    result.is_passed = is_passed
    result.correct_count = correct_count
    result.incorrect_count = incorrect_count
    result.unattempted_count = unattempted_count
    result.section_scores = section_scores
    result.status = (
        models.ResultStatus.PENDING if needs_manual else models.ResultStatus.PUBLISHED
    ) if exam.show_result_immediately else models.ResultStatus.PENDING

    if result.status == models.ResultStatus.PUBLISHED:
        result.published_at = datetime.utcnow()

    db.commit()
    db.refresh(result)
    return result
