from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base
from routers import auth, users, exams, questions, attempts, results, admin
from routers.syllabus import router as syllabus_router
from routers.evaluation import router as evaluation_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="ExamForge API",
    description="Production-ready online examination platform API",
    version="1.0.0",
    lifespan=lifespan
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "https://exam-verse-81vx5o0u7-subhrakantbehera8699-3748s-projects.vercel.app").split(",")
allowed_origins = [origin.strip() for origin in allowed_origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,       prefix="/api/auth",       tags=["Authentication"])
app.include_router(users.router,      prefix="/api/users",      tags=["Users"])
app.include_router(exams.router,      prefix="/api/exams",      tags=["Exams"])
app.include_router(questions.router,  prefix="/api/questions",  tags=["Questions"])
app.include_router(attempts.router,   prefix="/api/attempts",   tags=["Attempts"])
app.include_router(results.router,    prefix="/api/results",    tags=["Results"])
app.include_router(admin.router,      prefix="/api/admin",      tags=["Admin"])
app.include_router(syllabus_router,   prefix="/api/syllabus",   tags=["Syllabus"])
app.include_router(evaluation_router, prefix="/api/evaluation", tags=["Evaluation"])

@app.get("/")
async def root():
    return {"message": "ExamForge API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}