from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from models import UserRole, QuestionType, AttemptStatus, ResultStatus


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class UserSignup(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


# ── User Schemas ──────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


# ── Option Schemas ────────────────────────────────────────────────────────────

class OptionCreate(BaseModel):
    text: str
    is_correct: bool = False
    order: int = 0
    media_url: Optional[str] = None

class OptionOut(BaseModel):
    id: int
    text: str
    is_correct: bool
    order: int
    media_url: Optional[str] = None

    class Config:
        from_attributes = True

class OptionOutCandidate(BaseModel):
    id: int
    text: str
    order: int
    media_url: Optional[str] = None

    class Config:
        from_attributes = True


# ── Question Schemas ──────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    section_id: int
    question_type: QuestionType
    text: str
    explanation: Optional[str] = None
    marks: float = 1.0
    negative_marks: float = 0.0
    order: int = 0
    media_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    options: Optional[List[OptionCreate]] = []

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    explanation: Optional[str] = None
    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    order: Optional[int] = None
    media_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    options: Optional[List[OptionCreate]] = None

class QuestionOut(BaseModel):
    id: int
    section_id: int
    question_type: QuestionType
    text: str
    explanation: Optional[str] = None
    marks: float
    negative_marks: float
    order: int
    media_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    options: List[OptionOut] = []

    @validator('metadata', pre=True, always=True)
    def coerce_metadata(cls, v):
        if isinstance(v, dict):
            return v
        return None

    class Config:
        from_attributes = True

class QuestionOutCandidate(BaseModel):
    id: int
    section_id: int
    question_type: QuestionType
    text: str
    marks: float
    order: int
    media_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    options: List[OptionOutCandidate] = []

    @validator('metadata', pre=True, always=True)
    def coerce_metadata(cls, v):
        if isinstance(v, dict):
            return v
        return None

    class Config:
        from_attributes = True


# ── Section Schemas ───────────────────────────────────────────────────────────

class SectionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: int = 0
    marks_per_question: float = 1.0
    time_limit_minutes: Optional[int] = None

class SectionOut(BaseModel):
    id: int
    exam_id: int
    title: str
    description: Optional[str] = None
    order: int
    marks_per_question: float
    time_limit_minutes: Optional[int] = None
    questions: List[QuestionOut] = []

    class Config:
        from_attributes = True

class SectionOutCandidate(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    order: int
    questions: List[QuestionOutCandidate] = []

    class Config:
        from_attributes = True


# ── Exam Schemas ──────────────────────────────────────────────────────────────

class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: int = Field(..., ge=1)
    total_marks: float = Field(..., ge=0)
    pass_percentage: float = Field(40.0, ge=0, le=100)
    negative_marking: bool = False
    negative_marks_per_question: float = 0.25
    shuffle_questions: bool = False
    shuffle_options: bool = False
    max_attempts: int = Field(1, ge=1)
    is_public: bool = False
    show_result_immediately: bool = True
    allow_review: bool = True
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: Optional[int] = None
    total_marks: Optional[float] = None
    pass_percentage: Optional[float] = None
    negative_marking: Optional[bool] = None
    negative_marks_per_question: Optional[float] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    max_attempts: Optional[int] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None
    show_result_immediately: Optional[bool] = None
    allow_review: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class ExamOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    duration_minutes: int
    total_marks: float
    pass_percentage: float
    negative_marking: bool
    negative_marks_per_question: float
    shuffle_questions: bool
    shuffle_options: bool
    max_attempts: int
    is_public: bool
    is_active: bool
    show_result_immediately: bool
    allow_review: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime
    sections: List[SectionOut] = []

    class Config:
        from_attributes = True

class ExamListOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    duration_minutes: int
    total_marks: float
    pass_percentage: float
    max_attempts: int
    is_public: bool
    is_active: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime
    question_count: Optional[int] = 0

    class Config:
        from_attributes = True


# ── Attempt Schemas ───────────────────────────────────────────────────────────

class AttemptCreate(BaseModel):
    exam_id: int

class AnswerSubmit(BaseModel):
    question_id: int
    selected_option_ids: Optional[List[int]] = None
    text_answer: Optional[str] = None
    numeric_answer: Optional[float] = None
    file_url: Optional[str] = None
    match_answer: Optional[Dict[str, Any]] = None
    is_marked_review: bool = False

class AttemptOut(BaseModel):
    id: int
    exam_id: int
    user_id: int
    status: AttemptStatus
    started_at: datetime
    submitted_at: Optional[datetime] = None
    time_spent_seconds: int
    tab_switch_count: int
    question_order: Optional[List[int]] = None

    class Config:
        from_attributes = True

class AttemptDetail(AttemptOut):
    exam: ExamOut
    answers: List["AnswerOut"] = []

    class Config:
        from_attributes = True

class AnswerOut(BaseModel):
    id: int
    question_id: int
    selected_option_ids: Optional[List[int]] = None
    text_answer: Optional[str] = None
    numeric_answer: Optional[float] = None
    file_url: Optional[str] = None
    match_answer: Optional[Dict[str, Any]] = None
    is_marked_review: bool
    is_correct: Optional[bool] = None
    marks_obtained: Optional[float] = None

    class Config:
        from_attributes = True


# ── Result Schemas ────────────────────────────────────────────────────────────

class ResultOut(BaseModel):
    id: int
    attempt_id: int
    user_id: int
    exam_id: int
    total_marks: float
    obtained_marks: float
    percentage: float
    is_passed: bool
    correct_count: int
    incorrect_count: int
    unattempted_count: int
    section_scores: Optional[Dict[str, Any]] = None
    status: ResultStatus
    published_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class EvaluateAnswer(BaseModel):
    answer_id: int
    marks_obtained: float
    is_correct: bool
    evaluator_comment: Optional[str] = None


# ── Analytics ─────────────────────────────────────────────────────────────────

class ExamAnalytics(BaseModel):
    exam_id: int
    exam_title: str
    total_attempts: int
    completed_attempts: int
    average_score: float
    pass_rate: float
    highest_score: float
    lowest_score: float


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int
