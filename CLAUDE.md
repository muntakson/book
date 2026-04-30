# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BookMaker is a multi-user AI-powered book creation platform. Users create projects, generate book plans using Groq LLM, and proceed through a 5-stage workflow to produce complete book content with web research, fact-checking, PDF generation, and Korean translation.

## Architecture

```
┌─────────────────────────┐     ┌─────────────────────────┐
│  React Frontend (Vite)  │────▶│  FastAPI Backend        │
│  - Single App.tsx       │     │  - JWT Auth (auth.py)   │
│  - xterm.js terminal    │     │  - SQLite (models.py)   │
│  - Socket.IO client     │     │  - Groq API             │
└─────────────────────────┘     └─────────────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│  Terminal Server        │     │  Background Tasks       │
│  (Node.js + node-pty)   │     │  - Book writing         │
│  Port 8087              │     │  - Fact-checking        │
└─────────────────────────┘     │  - PDF generation       │
                                │  - Korean translation   │
                                └─────────────────────────┘
```

## 5-Stage Workflow

| Stage | Name | Description |
|-------|------|-------------|
| 1단계 | Plan | Generate book outline with Groq, user provides feedback |
| 2단계 | Write | Background task writes chapters in English with web research |
| 3단계 | Review | Fact-checking and critical review of content |
| 4단계 | PDF | Generate English PDF using pandoc/xelatex |
| 5단계 | Korean | Translate to Korean and generate Korean PDF |

Each stage requires user approval before proceeding. Stage status: `pending` → `in_progress` → `completed`

## Development Commands

### Backend
```bash
cd /var/www/aibook/bookmaker/backend
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn main:app --host 127.0.0.1 --port 9086 --reload
```

### Frontend
```bash
cd /var/www/aibook/bookmaker/frontend
npm install
npm run dev          # Dev server with HMR
npm run build        # Production build to dist/
npm test             # Playwright tests
```

### Production Deploy
```bash
cd /var/www/aibook/bookmaker/frontend && npm run build
cd /var/www/aibook/bookmaker/backend
lsof -ti :9086 | xargs kill -9 2>/dev/null
nohup ./venv/bin/uvicorn main:app --host 127.0.0.1 --port 9086 --reload > bookmaker.log 2>&1 &
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app with all endpoints and background tasks |
| `backend/models.py` | SQLAlchemy models: User, Project, ProgressLog |
| `backend/auth.py` | JWT authentication, password hashing |
| `frontend/src/App.tsx` | Single React component (2500+ lines) |

## Background Tasks (main.py)

```python
write_book_chapters(project_id, db_engine)    # Stage 2: Write chapters with Groq
fact_check_and_review(project_id, db_engine)  # Stage 3: Fact-check content
generate_book_pdf(project_id, db_engine)      # Stage 4: Generate English PDF
translate_to_korean(project_id, db_engine)    # Stage 5: Translate and generate Korean PDF
```

All tasks run in background threads. Progress logged to `progress_logs` table.

## API Endpoints

### Authentication
- `POST /api/login` - Returns JWT token
- `GET /api/me` - Current user info

### Projects
- `GET /api/projects` - List user's projects
- `POST /api/projects` - Create project
- `POST /api/generate-plan` - Generate book plan (Stage 1)
- `POST /api/proceed-stage` - Move to next stage
- `GET /api/projects/{id}/logs` - Progress logs
- `GET /api/projects/{id}/content-info` - Chapter list and word counts

### Downloads
- `GET /api/projects/{id}/pdf-status` - Check PDF availability (EN/KO)
- `GET /api/projects/{id}/download-pdf` - Download English PDF
- `GET /api/projects/{id}/download-korean-pdf` - Download Korean PDF
- `GET /api/projects/{id}/download-markdown` - Download English markdown
- `GET /api/projects/{id}/download-korean-markdown` - Download Korean markdown

### Admin
- `GET /api/admin/stats` - Dashboard statistics
- `POST /api/admin/proceed-stage` - Approve stage transition

## Database Schema

```sql
users: id, username, password_hash, created_at
projects: id, user_id, name, book_idea, adapted_prompt, user_feedback,
          generated_content, conversation_history, model_used, tokens_used,
          stage, stage_status, created_at, updated_at
progress_logs: id, project_id, stage, message, level, created_at
```

## Output Files

Generated files are stored in `backend/output/user_{id}/`:
- `{project_name}.md` - English markdown
- `{project_name}.pdf` - English PDF
- `{project_name}_KO.md` - Korean markdown
- `{project_name}_KO.pdf` - Korean PDF

## LLM Cost Tracking

Uses Groq API with `llama-3.3-70b-versatile` model. Token usage is tracked per project in `tokens_used` column. Estimated cost: ~$0.70 per million tokens (average of input/output rates).

## Environment Variables

`backend/.env`:
```env
GROQ_API_KEY=gsk_...
```

## Ports

- **9086** - FastAPI backend (serves frontend from dist/)
- **8087** - Terminal server (Socket.IO + node-pty)
- Nginx proxies both at `book.iotok.org`

## Testing

```bash
cd frontend
npm test              # Run all Playwright tests
npm run test:ui       # Interactive test UI
npm run test:debug    # Debug mode
```

## Critical Implementation Patterns

### Background Task Race Condition Prevention
When starting background tasks from endpoints, always commit status BEFORE starting the thread:
```python
# CORRECT: Commit first, then start thread
project.stage_status = "in_progress"
db.commit()
thread.start()

# WRONG: Thread may complete before commit, causing status overwrite
thread.start()
project.stage_status = "in_progress"
db.commit()
```

### Database Updates in Background Threads
Use explicit SQL UPDATE statements instead of ORM modifications for reliability:
```python
from sqlalchemy import update
db.execute(
    update(Project)
    .where(Project.id == project_id)
    .values(stage_status="completed")
)
db.commit()
```

### Unicode Filenames in HTTP Downloads
Use RFC 5987 encoding for non-ASCII filenames in Content-Disposition headers:
```python
from urllib.parse import quote
ascii_filename = f"book_{project.id}.pdf"
encoded_filename = quote(f"{project.name}.pdf")
headers = {
    "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded_filename}"
}
```

### Stage Completion Checks
When checking if a stage is complete, account for progression to later stages:
```python
# CORRECT: Check if stage >= 4 (English PDF available after stage 4 completes)
stage_num = int(project.stage[0])
if stage_num >= 4:
    # PDF is available

# WRONG: Fails when user proceeds to stage 5
if project.stage == "4단계" and project.stage_status == "completed":
    # PDF is available
```
