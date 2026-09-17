# AI Resume Analyzer - Backend

A production-ready FastAPI backend that accepts PDF resume uploads, runs a LangChain + GPT-4o analysis pipeline, and returns ATS scores, grammar feedback, and job-role recommendations.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115 + Uvicorn |
| Database | PostgreSQL 16 (Docker locally, AWS RDS in production) |
| ORM / Migrations | SQLAlchemy (async) + Alembic |
| AI Orchestration | LangChain + OpenAI GPT-4o |
| PDF Parsing | pdfplumber (primary) + pypdf (fallback) |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Validation | Pydantic v2 |

## Local Development (Docker — no native Postgres required)

### Prerequisites
- Docker Desktop
- Python 3.11+

### 1. Clone and configure environment
```bash
cp .env.example .env
# Edit .env and fill in your values (OPENAI_API_KEY, JWT_SECRET_KEY, etc.)
```

### 2. Start PostgreSQL in Docker
```bash
docker compose up -d db
```
This starts a postgres:16 container on port 5432. No local Postgres install needed.

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Run database migrations
```bash
alembic upgrade head
```
Creates all tables and seeds 10 job roles in the database.

### 5. Start the API server
```bash
uvicorn app.main:app --reload
```
API is available at http://localhost:8000/api
Interactive docs: http://localhost:8000/api/docs

### 6. (Optional) Run everything in Docker
```bash
docker compose up --build
```
Starts both `db` and `api` containers. The API container also needs `alembic upgrade head` on first run:
```bash
docker compose exec api alembic upgrade head
```

---

## API Endpoints

Base URL: `http://localhost:8000/api`

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register a new user → `{ user, token }` |
| POST | `/auth/login` | Login → `{ user, token }` |
| GET | `/auth/me` | Get current user (JWT required) |

### Resumes
| Method | Path | Description |
|--------|------|-------------|
| POST | `/resumes/upload` | Upload PDF (multipart) → `{ resume_id, status }` |
| GET | `/resumes` | List current user's resumes |
| GET | `/resumes/{id}` | Get resume + analysis |
| DELETE | `/resumes/{id}` | Delete a resume |
| POST | `/resumes/{id}/analyze` | Run LangChain analysis pipeline |
| GET | `/resumes/{id}/analysis` | Get full analysis result |

### Admin (admin role required)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/users` | List all users |
| GET | `/admin/resumes` | List all resumes |
| GET | `/admin/analytics` | Aggregated analytics |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Returns `{ "status": "ok" }` |

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `POSTGRES_USER` | Yes | Docker Compose DB user |
| `POSTGRES_PASSWORD` | Yes | Docker Compose DB password |
| `POSTGRES_DB` | Yes | Docker Compose DB name |
| `OPENAI_API_KEY` | Yes | OpenAI API key (never logged) |
| `JWT_SECRET_KEY` | Yes | JWT signing secret (never logged) |
| `JWT_EXPIRE_MINUTES` | No | Token TTL in minutes (default: 60) |
| `ALLOWED_ORIGIN` | Yes | CORS origin (your Vercel frontend URL) |
| `ENVIRONMENT` | No | `development` or `production` |

---

## Production Deployment (AWS)

### App Runner / EC2
1. Build and push Docker image to ECR:
```bash
docker build -t ai-resume-analyzer .
aws ecr get-login-password | docker login --username AWS --password-stdin <ecr-uri>
docker tag ai-resume-analyzer:latest <ecr-uri>/ai-resume-analyzer:latest
docker push <ecr-uri>/ai-resume-analyzer:latest
```
2. Create an App Runner service pointing to the ECR image.
3. Set environment variables in App Runner configuration (swap `DATABASE_URL` to RDS endpoint).
4. Run migrations against RDS:
```bash
DATABASE_URL=postgresql+asyncpg://<rds-user>:<rds-pass>@<rds-endpoint>:5432/<db> alembic upgrade head
```

### RDS PostgreSQL
- Create a PostgreSQL 16 RDS instance in the same VPC as App Runner.
- Set `DATABASE_URL` in App Runner env vars to point to RDS.

---

## Project Structure

```
app/
  main.py                         FastAPI app, CORS, routers
  core/
    config.py                     Settings from env vars (pydantic-settings)
    security.py                   JWT + bcrypt + RBAC dependencies
  db/
    models.py                     SQLAlchemy ORM models
    session.py                    Async engine + get_db dependency
  schemas/
    auth.py                       Auth request/response models
    resumes.py                    Resume + Analysis Pydantic models
    admin.py                      Admin response models
  routers/
    auth.py                       /auth/* endpoints
    resumes.py                    /resumes/* endpoints
    admin.py                      /admin/* endpoints
  services/
    pdf_parser.py                 PDF text extraction + section splitting
    agent/
      agent.py                    Pipeline orchestrator
      tools/
        skill_extraction_tool.py  Extracts skills via GPT-4o
        ats_scoring_tool.py       ATS + formatting + keyword scoring
        grammar_tool.py           Grammar issues + section feedback
        job_matching_tool.py      DB-backed job role matching
alembic/
  env.py                          Async Alembic env
  versions/
    0001_initial_schema.py        Full schema + seed job_roles
requirements.txt
Dockerfile
docker-compose.yml
.env.example
```
