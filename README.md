# ExamForge — Production-Ready Online Exam Platform

Full-stack exam platform with React/Vite frontend (Vercel) and FastAPI backend (Render), PostgreSQL database, JWT auth, and a real exam engine with anti-cheat, auto-grading, and manual evaluation.

---

## Project Structure

```
examforge/
├── backend/                  # FastAPI — deploy on Render
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── seed.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── exams.py
│   │   ├── questions.py
│   │   ├── attempts.py
│   │   ├── results.py
│   │   └── admin.py
│   ├── services/
│   │   └── grading.py
│   └── utils/
│       └── auth.py
│
└── frontend/                 # React/Vite — deploy on Vercel
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── package.json
    ├── .env.example
    └── src/
        ├── App.jsx
        ├── main.jsx
        ├── index.css
        ├── services/api.js
        ├── store/authStore.js
        ├── components/layout/
        └── pages/
            ├── LoginPage.jsx
            ├── SignupPage.jsx
            ├── ForgotPasswordPage.jsx
            ├── ResetPasswordPage.jsx
            ├── candidate/
            │   ├── Dashboard.jsx
            │   ├── ExamInstructions.jsx
            │   ├── ExamRoom.jsx
            │   ├── ResultPage.jsx
            │   └── AttemptHistory.jsx
            └── admin/
                ├── Dashboard.jsx
                ├── Exams.jsx
                ├── ExamEditor.jsx
                ├── Users.jsx
                ├── Results.jsx
                ├── Analytics.jsx
                └── Evaluate.jsx
```

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### 1. Clone and set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy and fill in env variables
cp .env.example .env
```

Edit `backend/.env`:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/examforge
SECRET_KEY=your-random-secret-key-at-least-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FRONTEND_URL=http://localhost:5173
```

Create the database and run migrations / table creation:
```bash
# The app auto-creates tables on startup via SQLAlchemy
uvicorn main:app --reload --port 8000
```

Seed demo data (admin + candidate + sample exams):
```bash
python seed.py
```

**Demo credentials after seeding:**
- Admin: `admin@examforge.io` / `Admin@1234`
- Candidate: `candidate@examforge.io` / `Test@1234`

### 2. Set up the frontend

```bash
cd frontend
npm install

cp .env.example .env.local
# .env.local content:
# VITE_API_BASE_URL=http://localhost:8000
```

Start the dev server:
```bash
npm run dev
# Opens at http://localhost:5173
```

---

## Deploying the Backend on Render

1. Create a new **Web Service** on [render.com](https://render.com)
2. Connect your GitHub repo and set the **Root Directory** to `backend`
3. Configure:

| Setting | Value |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Environment | Python 3 |

4. Add these **Environment Variables** in Render dashboard:

```
DATABASE_URL          = <Internal URL from your Render PostgreSQL service>
SECRET_KEY            = <generate with: python -c "import secrets; print(secrets.token_hex(32))">
ALGORITHM             = HS256
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
FRONTEND_URL          = https://your-app.vercel.app
```

5. Create a **PostgreSQL** database on Render (free tier available) and copy the **Internal Database URL** into `DATABASE_URL`.

6. After first deploy, open the Render shell and run:
```bash
python seed.py
```

---

## Deploying the Frontend on Vercel

1. Import your repo into [vercel.com](https://vercel.com)
2. Set **Framework Preset** to `Vite`
3. Set **Root Directory** to `frontend`
4. Add this **Environment Variable** in Vercel dashboard:

```
VITE_API_BASE_URL = https://your-backend.onrender.com
```

5. Deploy. Vercel will run `npm run build` automatically.

---

## Connecting Frontend ↔ Backend

### CORS
In `backend/main.py`, the `FRONTEND_URL` env var controls which origins are allowed.
For production, set `FRONTEND_URL=https://your-app.vercel.app` in Render.

For local dev, `http://localhost:5173` is always in the allowed list.

To allow multiple Vercel preview URLs, you can extend the `allowed_origins` list or use a wildcard pattern.

### JWT across separate domains
The app uses `Authorization: Bearer <token>` headers (not cookies), so there are **no cross-domain cookie issues**. The token is stored in `localStorage` and attached to every API request automatically via the Axios interceptor in `frontend/src/services/api.js`.

---

## Environment Variable Reference

### Backend (`.env` / Render)
| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | JWT signing secret (32+ random chars) |
| `ALGORITHM` | ✅ | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | Token TTL (default 1440 = 24h) |
| `FRONTEND_URL` | ✅ | Vercel frontend URL for CORS |
| `SMTP_HOST` | ❌ | SMTP server for password reset emails |
| `SMTP_PORT` | ❌ | SMTP port (default 587) |
| `SMTP_USER` | ❌ | SMTP username |
| `SMTP_PASSWORD` | ❌ | SMTP password |
| `FROM_EMAIL` | ❌ | Sender address for emails |

### Frontend (`.env.local` / Vercel)
| Variable | Required | Description |
|---|---|---|
| `VITE_API_BASE_URL` | ✅ | Your Render backend URL |

---

## Features

### Candidate
- Sign up / log in / forgot & reset password
- Browse available exams with start window and duration info
- Full exam instructions page before starting
- Exam room with: countdown timer, question palette, mark-for-review, prev/next navigation
- Auto-save answers on every answer change
- Tab-switch warning (recorded server-side)
- Auto-submit on timer expiry
- Submit confirmation modal with attempt summary
- Results page with score ring, pass/fail, section analysis
- Attempt history with resume support

### Admin
- Dashboard with platform-wide stats
- Create / edit / delete exams with sections
- Add questions in 10 formats: MCQ single/multiple, True/False, Fill in blank, Short/Long answer, Numeric, Match, Assertion & Reason, File upload
- Set duration, marks, negative marking, shuffle, pass %, max attempts, availability window
- Publish/unpublish exams; assign to users or leave open
- View all results; publish individual results to candidates
- Manual evaluation queue for subjective (long/short answer) questions
- Analytics dashboard: exam stats, score distribution chart, leaderboard top-10
- User management: activate/deactivate/delete

### Exam Engine
- Section-wise question flow
- Real-time auto-save
- Fullscreen warning on exit
- Tab-switch counter
- Anti-cheat warnings (no copy, no right-click in exam)
- Randomized questions/options (configurable)
- Resume in-progress attempts (if allowed)
- Auto-grading for objective questions
- Manual grading queue for subjective questions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Zustand, Axios, React Router v6 |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2 |
| Database | PostgreSQL |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Deployment | Vercel (frontend), Render (backend + DB) |
