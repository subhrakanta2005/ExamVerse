from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum, BigInteger
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CANDIDATE = "candidate"


class QuestionType(str, enum.Enum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    TRUE_FALSE = "true_false"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    NUMERIC = "numeric"
    MATCH = "match"
    ASSERTION_REASON = "assertion_reason"
    FILE_UPLOAD = "file_upload"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    EVALUATED = "evaluated"


class ResultStatus(str, enum.Enum):
    PENDING = "pending"
    PUBLISHED = "published"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.CANDIDATE, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    reset_token = Column(String(255), nullable=True)
    reset_token_expiry = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    attempts = relationship("Attempt", back_populates="user")
    assigned_exams = relationship("ExamAssignment", back_populates="user")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    instructions = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    total_marks = Column(Float, nullable=False)
    pass_percentage = Column(Float, default=40.0)
    negative_marking = Column(Boolean, default=False)
    negative_marks_per_question = Column(Float, default=0.25)
    shuffle_questions = Column(Boolean, default=False)
    shuffle_options = Column(Boolean, default=False)
    max_attempts = Column(Integer, default=1)
    is_public = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    show_result_immediately = Column(Boolean, default=True)
    allow_review = Column(Boolean, default=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sections = relationship("Section", back_populates="exam", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="exam")
    assignments = relationship("ExamAssignment", back_populates="exam")
    creator = relationship("User", foreign_keys=[created_by])


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    order = Column(Integer, default=0)
    marks_per_question = Column(Float, default=1.0)
    time_limit_minutes = Column(Integer, nullable=True)

    exam = relationship("Exam", back_populates="sections")
    questions = relationship("Question", back_populates="section", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    section_id = Column(Integer, ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    question_type = Column(SAEnum(QuestionType), nullable=False)
    text = Column(Text, nullable=False)
    explanation = Column(Text)
    marks = Column(Float, default=1.0)
    negative_marks = Column(Float, default=0.0)
    order = Column(Integer, default=0)
    is_required = Column(Boolean, default=True)
    media_url = Column(String(500))
    metadata = Column(JSON)  # For match/assertion questions
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    section = relationship("Section", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="question")


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    media_url = Column(String(500))

    question = relationship("Question", back_populates="options")


class ExamAssignment(Base):
    __tablename__ = "exam_assignments"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    exam = relationship("Exam", back_populates="assignments")
    user = relationship("User", back_populates="assigned_exams")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(SAEnum(AttemptStatus), default=AttemptStatus.IN_PROGRESS)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    time_spent_seconds = Column(Integer, default=0)
    tab_switch_count = Column(Integer, default=0)
    question_order = Column(JSON)  # Shuffled question IDs
    current_question_id = Column(Integer, nullable=True)

    exam = relationship("Exam", back_populates="attempts")
    user = relationship("User", back_populates="attempts")
    answers = relationship("Answer", back_populates="attempt", cascade="all, delete-orphan")
    result = relationship("Result", back_populates="attempt", uselist=False)


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_option_ids = Column(JSON)  # For MCQ
    text_answer = Column(Text)  # For text-based answers
    numeric_answer = Column(Float)  # For numeric
    file_url = Column(String(500))  # For file upload
    match_answer = Column(JSON)  # For match the following
    is_marked_review = Column(Boolean, default=False)
    is_correct = Column(Boolean, nullable=True)
    marks_obtained = Column(Float, nullable=True)
    evaluator_comment = Column(Text)
    evaluated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    answered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    attempt = relationship("Attempt", back_populates="answers")
    question = relationship("Question", back_populates="answers")


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("attempts.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    total_marks = Column(Float, nullable=False)
    obtained_marks = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)
    is_passed = Column(Boolean, nullable=False)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    unattempted_count = Column(Integer, default=0)
    section_scores = Column(JSON)  # Per-section breakdown
    status = Column(SAEnum(ResultStatus), default=ResultStatus.PENDING)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attempt = relationship("Attempt", back_populates="result")
