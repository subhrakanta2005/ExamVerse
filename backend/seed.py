"""
Seed script — run once to populate the database with demo data.
Usage: python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine, Base
import models
from utils.auth import get_password_hash
from datetime import datetime, timedelta

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Admin user ────────────────────────────────────────────────────────
        if not db.query(models.User).filter(models.User.email == "admin@examforge.io").first():
            admin = models.User(
                email="admin@examforge.io",
                username="admin",
                full_name="Platform Admin",
                hashed_password=get_password_hash("Admin@1234"),
                role=models.UserRole.ADMIN,
                is_active=True,
                is_verified=True
            )
            db.add(admin)
            db.flush()
        else:
            admin = db.query(models.User).filter(models.User.email == "admin@examforge.io").first()

        # ── Candidate user ────────────────────────────────────────────────────
        if not db.query(models.User).filter(models.User.email == "candidate@example.com").first():
            candidate = models.User(
                email="candidate@example.com",
                username="johndoe",
                full_name="John Doe",
                hashed_password=get_password_hash("Candidate@1234"),
                role=models.UserRole.CANDIDATE,
                is_active=True,
                is_verified=True
            )
            db.add(candidate)
            db.flush()
        else:
            candidate = db.query(models.User).filter(models.User.email == "candidate@example.com").first()

        # ── Sample Exam ───────────────────────────────────────────────────────
        if not db.query(models.Exam).filter(models.Exam.title == "General Knowledge Test").first():
            exam = models.Exam(
                title="General Knowledge Test",
                description="A comprehensive general knowledge examination covering science, history, and mathematics.",
                instructions="""
Welcome to the General Knowledge Test!

Instructions:
1. This exam has 2 sections with 10 questions each.
2. Total duration: 30 minutes.
3. Each correct answer carries 2 marks.
4. There is 0.5 negative marking for wrong answers.
5. You can mark questions for review and revisit them later.
6. Do not switch tabs — it will be recorded.
7. The exam will auto-submit when time expires.

Good luck!
                """.strip(),
                duration_minutes=30,
                total_marks=20.0,
                pass_percentage=40.0,
                negative_marking=True,
                negative_marks_per_question=0.5,
                shuffle_questions=False,
                shuffle_options=True,
                max_attempts=3,
                is_public=True,
                is_active=True,
                show_result_immediately=True,
                allow_review=True,
                created_by=admin.id
            )
            db.add(exam)
            db.flush()

            # Section 1: Science
            sec1 = models.Section(
                exam_id=exam.id, title="Science & Technology", order=0,
                marks_per_question=2.0,
                description="Questions covering basic science and technology concepts."
            )
            db.add(sec1)
            db.flush()

            science_questions = [
                {
                    "text": "What is the chemical symbol for water?",
                    "type": models.QuestionType.MCQ_SINGLE,
                    "options": [("H2O", True), ("CO2", False), ("O2", False), ("NaCl", False)],
                    "explanation": "Water is composed of two hydrogen atoms and one oxygen atom, hence H2O."
                },
                {
                    "text": "Which planet is known as the Red Planet?",
                    "type": models.QuestionType.MCQ_SINGLE,
                    "options": [("Mars", True), ("Venus", False), ("Jupiter", False), ("Saturn", False)],
                    "explanation": "Mars appears red due to iron oxide on its surface."
                },
                {
                    "text": "The speed of light is approximately 3 × 10^8 m/s.",
                    "type": models.QuestionType.TRUE_FALSE,
                    "options": [("True", True), ("False", False)],
                    "explanation": "The speed of light in vacuum is approximately 299,792,458 m/s ≈ 3×10⁸ m/s."
                },
                {
                    "text": "Which of the following are programming languages? (Select all that apply)",
                    "type": models.QuestionType.MCQ_MULTI,
                    "options": [("Python", True), ("HTML", False), ("Java", True), ("CSS", False)],
                    "explanation": "Python and Java are programming languages. HTML and CSS are markup/styling languages."
                },
                {
                    "text": "The powerhouse of the cell is the ___________.",
                    "type": models.QuestionType.FILL_BLANK,
                    "options": [("mitochondria", True)],
                    "explanation": "Mitochondria generate most of the cell's supply of ATP, used as a source of chemical energy."
                },
            ]

            for i, q_data in enumerate(science_questions):
                q = models.Question(
                    section_id=sec1.id,
                    question_type=q_data["type"],
                    text=q_data["text"],
                    explanation=q_data.get("explanation"),
                    marks=2.0,
                    negative_marks=0.5,
                    order=i
                )
                db.add(q)
                db.flush()
                for j, (opt_text, is_correct) in enumerate(q_data["options"]):
                    db.add(models.Option(
                        question_id=q.id, text=opt_text, is_correct=is_correct, order=j
                    ))

            # Section 2: Mathematics
            sec2 = models.Section(
                exam_id=exam.id, title="Mathematics", order=1,
                marks_per_question=2.0,
                description="Basic arithmetic and mathematical reasoning."
            )
            db.add(sec2)
            db.flush()

            math_questions = [
                {
                    "text": "What is 15% of 200?",
                    "type": models.QuestionType.NUMERIC,
                    "options": [("30", True)],
                    "explanation": "15% of 200 = (15/100) × 200 = 30"
                },
                {
                    "text": "What is the value of π (pi) approximately?",
                    "type": models.QuestionType.MCQ_SINGLE,
                    "options": [("3.14159", True), ("2.71828", False), ("1.41421", False), ("1.73205", False)],
                    "explanation": "Pi (π) ≈ 3.14159. The other values are e, √2, and √3 respectively."
                },
                {
                    "text": "Solve: 2x + 5 = 15. What is x?",
                    "type": models.QuestionType.NUMERIC,
                    "options": [("5", True)],
                    "explanation": "2x = 15 - 5 = 10, so x = 5."
                },
                {
                    "text": "A triangle has angles 60°, 60°, and 60°. What type of triangle is it?",
                    "type": models.QuestionType.SHORT_ANSWER,
                    "options": [("equilateral", True)],
                    "explanation": "A triangle with all angles equal (60°) is called an equilateral triangle."
                },
                {
                    "text": "Briefly explain the Pythagorean theorem and give an example.",
                    "type": models.QuestionType.LONG_ANSWER,
                    "options": [],
                    "explanation": "a² + b² = c² where c is the hypotenuse of a right triangle."
                },
            ]

            for i, q_data in enumerate(math_questions):
                q = models.Question(
                    section_id=sec2.id,
                    question_type=q_data["type"],
                    text=q_data["text"],
                    explanation=q_data.get("explanation"),
                    marks=2.0,
                    negative_marks=0.5 if q_data["type"] not in [models.QuestionType.SHORT_ANSWER, models.QuestionType.LONG_ANSWER] else 0.0,
                    order=i
                )
                db.add(q)
                db.flush()
                for j, (opt_text, is_correct) in enumerate(q_data["options"]):
                    db.add(models.Option(
                        question_id=q.id, text=opt_text, is_correct=is_correct, order=j
                    ))

        db.commit()
        print("✅ Seed data created successfully!")
        print("Admin login: admin@examforge.io / Admin@1234")
        print("Candidate login: candidate@example.com / Candidate@1234")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
