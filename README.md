# Persona AI Studio

AI Persona Content Generation Platform — self-hosted, production-ready MVP.

Automates the full pipeline: character creation → AI content planning (Gemini) → image generation (Google ImageFX via Playwright) → Google Drive storage → dashboard monitoring.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Structure](#2-project-structure)
3. [Step 1 — Get API Keys & Credentials](#step-1--get-api-keys--credentials)
4. [Step 2 — Configure Environment](#step-2--configure-environment)
5. [Step 3 — Start with Docker (Recommended)](#step-3--start-with-docker-recommended)
6. [Step 4 — Verify Everything is Running](#step-4--verify-everything-is-running)
7. [Step 5 — Create Your First Character](#step-5--create-your-first-character)
8. [Step 6 — Create a Session](#step-6--create-a-session)
9. [Step 7 — Generate Content Plan](#step-7--generate-content-plan)
10. [Step 8 — Start Image Generation](#step-8--start-image-generation)
11. [Step 9 — Monitor Progress](#step-9--monitor-progress)
12. [Local Development (No Docker)](#local-development-no-docker)
13. [API Reference](#api-reference)
14. [Troubleshooting](#troubleshooting)

---

## 1. Prerequisites

Make sure the following are installed on your machine:

| Tool | Version | Check |
|------|---------|-------|
| Docker Desktop | 24+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |
| Git | any | `git --version` |

> For local dev (no Docker): Python 3.12+, MongoDB 7, Redis 7

---

## 2. Project Structure

```
persona-ai-studio/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # All settings via .env
│   │   ├── database.py          # MongoDB client + index setup
│   │   ├── models/              # MongoDB document schemas
│   │   ├── schemas/             # Pydantic request/response models
│   │   ├── repositories/        # Motor async data access layer
│   │   ├── services/            # Business logic (Gemini, Drive, planning, queue)
│   │   └── api/                 # FastAPI route handlers
│   ├── worker/
│   │   ├── main.py              # BullMQ worker process
│   │   └── processors/
│   │       ├── image_processor.py    # Job handler (DB updates)
│   │       └── flow_automation.py    # Playwright → Google ImageFX
│   ├── prompts/
│   │   └── master_image_description.md   # Default content generation template
│   ├── scripts/
│   │   └── seed.py              # Load sample character + session
│   ├── Dockerfile               # API container
│   └── Dockerfile.worker        # Worker container (includes Playwright)
├── frontend/
│   ├── index.html               # Dashboard overview
│   ├── characters.html          # Character management
│   ├── sessions.html            # Session creation & monitoring
│   ├── queue.html               # Real-time queue monitor
│   ├── settings.html            # Credentials & system status
│   ├── css/styles.css
│   └── js/common.js
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Step 1 — Get API Keys & Credentials

You need **three** external services configured before starting.

### A. Gemini API Key (Required — for content generation)

1. Go to [https://aistudio.google.com/](https://aistudio.google.com/)
2. Sign in with your Google account
3. Click **Get API key** → **Create API key**
4. Copy the key (starts with `AIza...`)
5. Save it — you'll use it as `GEMINI_API_KEY`

### B. Google Service Account — Google Drive (Required — for image storage)

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Go to **APIs & Services → Library**
4. Search for **Google Drive API** → click **Enable**
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → Service Account**
   - Name: `persona-ai-studio`
   - Click **Done**
7. Click the service account you just created
8. Go to **Keys** tab → **Add Key → Create new key → JSON**
9. Download the JSON file (e.g. `persona-ai-studio-xxxx.json`)
10. Convert the JSON to a single line for the `.env` file:
    ```bash
    # On Mac/Linux:
    cat persona-ai-studio-xxxx.json | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)))"
    ```
    Copy the output — you'll use it as `GOOGLE_SERVICE_ACCOUNT_JSON`
11. Note the `client_email` field inside the JSON (looks like `persona-ai-studio@project.iam.gserviceaccount.com`)
12. Go to **Google Drive** (drive.google.com)
13. Create a folder called `AI Personas`
14. Right-click the folder → **Share** → paste the `client_email` → set role to **Editor** → click **Done**

### C. Google Account for ImageFX (Required — for image generation)

The worker logs into Google ImageFX using your Google credentials.

1. Use an existing Google account or create a dedicated one
2. **Recommended**: Enable 2-Step Verification and create an **App Password**:
   - Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
   - Under "How you sign in to Google" → **2-Step Verification** → enable it
   - Go back to Security → scroll down → **App passwords**
   - Select app: `Other (Custom name)` → name it `persona-ai-studio`
   - Copy the 16-character password
3. Save the email as `GOOGLE_EMAIL` and the app password as `GOOGLE_PASSWORD`

> If you don't use an App Password, set `GOOGLE_PASSWORD` to your regular password. Note that Google may block automated logins — App Password is strongly recommended.

---

## Step 2 — Configure Environment

```bash
# From the project root directory:
cp .env.example .env
```

Open `.env` in your editor and fill in the values:

```bash
# Required — fill these in
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
GOOGLE_EMAIL=yourname@gmail.com
GOOGLE_PASSWORD=your-app-password-here

# These have sensible defaults — change only if needed
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=persona_ai_studio
REDIS_HOST=redis
REDIS_PORT=6379
GEMINI_MODEL=gemini-2.5-pro
GOOGLE_DRIVE_ROOT_FOLDER=AI Personas
WORKER_CONCURRENCY=2
MAX_RETRIES=3
```

> **Important:** `GOOGLE_SERVICE_ACCOUNT_JSON` must be the entire JSON content on a **single line** with no line breaks.

---

## Step 3 — Start with Docker (Recommended)

From the project root directory:

```bash
docker compose up -d
```

This starts four containers:

| Container | What it does | Port |
|-----------|-------------|------|
| `persona_mongodb` | MongoDB database | 27017 |
| `persona_redis` | Redis (queue backend) | 6379 |
| `persona_backend` | FastAPI API + serves frontend | 8000 |
| `persona_worker` | BullMQ worker + Playwright | — |

The first run will take 2–5 minutes as Docker builds images and downloads Playwright browsers.

**Watch the startup logs:**
```bash
docker compose logs -f
```

Wait until you see:
```
persona_backend  | INFO: Application startup complete.
persona_worker   | worker_ready queue=image-generation
```

Press `Ctrl+C` to stop following logs (containers keep running).

---

## Step 4 — Verify Everything is Running

### Check container health:
```bash
docker compose ps
```

All four containers should show `healthy` or `running`.

### Check the API:
```bash
curl http://localhost:8000/api/health
# Expected: {"status":"ok","version":"1.0.0"}
```

### Open the dashboard:
Go to **[http://localhost:8000](http://localhost:8000)** in your browser.

You should see the dark-themed dashboard with zero stats — that's correct for a fresh install.

### Check API documentation:
Go to **[http://localhost:8000/api/docs](http://localhost:8000/api/docs)** — interactive Swagger UI.

---

## Step 5 — Create Your First Character

### Via the Dashboard (UI)

1. Open [http://localhost:8000/characters.html](http://localhost:8000/characters.html)
2. Click **+ New Character**
3. Fill in the form:
   - **Name** (required): e.g. `Riva Mehra`
   - **Age**: `24 years old`
   - **Gender**: `Female, feminine, soft-glam`
   - **Personality**: `Confident, playful, slightly mysterious, classy`
   - **Appearance**: `Tall, slim, South Asian features, long dark hair, warm skin tone`
   - **Fashion Style**: `Soft-glam luxury — beige, black, satin, fitted dresses, gold accessories`
   - **Audience**: `Men aged 21-38 who enjoy lifestyle and fashion content`
   - **Niche**: `Luxury lifestyle, fashion, travel, beauty`
   - **City**: `Mumbai`
   - **Country**: `India`
   - **Custom Master Prompt**: Leave blank to use the default template
4. Click **Create Character**

### Via API (cURL)

```bash
curl -X POST http://localhost:8000/api/characters \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Riva Mehra",
    "age": "24 years old",
    "gender": "Female, feminine, soft-glam luxury lifestyle creator",
    "persona": "Confident, playful, slightly mysterious, classy, emotionally engaging",
    "appearance": "Tall, slim, South Asian features, long dark hair, warm skin tone, expressive eyes",
    "fashionStyle": "Soft-glam luxury — beige, black, ivory, champagne, satin, fitted dresses, gold accessories",
    "audience": "Men aged 21-38 who enjoy lifestyle creators, fashion, beauty, fitness",
    "niche": "Luxury lifestyle, soft-glam fashion, nightlife, fitness, travel, beauty",
    "city": "Mumbai",
    "country": "India",
    "status": "active"
  }'
```

Save the `_id` from the response — you'll need it in the next step.

### Or load sample data:

```bash
docker compose exec backend python scripts/seed.py
```

This creates a sample character "Riva Mehra" and a 3-day session.

---

## Step 6 — Create a Session

A session represents a batch content generation job (e.g. "7 days of content for Riva").

### Via the Dashboard

1. Open [http://localhost:8000/sessions.html](http://localhost:8000/sessions.html)
2. Click **+ New Session**
3. Fill in:
   - **Character**: Select from dropdown
   - **Start Date**: e.g. `2026-06-10`
   - **End Date**: e.g. `2026-06-12` (3 days)
   - **Content Structure**: Define sections per day
     - Click **+ Add section** for each time slot
     - Example sections:
       - `Morning` → `3` images
       - `Evening` → `5` images
       - `Night` → `10` images
4. Click **Create Session**

This creates a session with `totalImages = days × images_per_day` = `3 × 18 = 54 images`.

### Via API

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "characterId": "YOUR_CHARACTER_ID_HERE",
    "startDate": "2026-06-10",
    "endDate": "2026-06-12",
    "contentStructure": {
      "sections": {
        "Morning": 3,
        "Evening": 5,
        "Night": 10
      }
    }
  }'
```

---

## Step 7 — Generate Content Plan

This calls Gemini 2.5 Pro to create image descriptions for every day, section, and image.

### Via the Dashboard

1. On the Sessions page, find your session
2. Click **Generate Plan** button next to it
   - Or click **View** → then **Generate Content Plan** inside the detail panel
3. The status changes to `PLANNING` then `PLANNED`
4. This takes 30–90 seconds depending on the number of days and images

> The system automatically fetches content history for the character and passes it to Gemini to avoid repetitive outfits/locations.

### Via API

```bash
# Async (returns immediately, generation runs in background)
curl -X POST http://localhost:8000/api/plans/generate \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "YOUR_SESSION_ID_HERE"}'

# Synchronous (waits for completion, returns the full plan)
curl -X POST http://localhost:8000/api/plans/generate/sync \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "YOUR_SESSION_ID_HERE"}'
```

### Check the generated plan:
```bash
curl http://localhost:8000/api/plans/YOUR_SESSION_ID_HERE
```

This returns all content plan sections with `contentType`, `sectionIntent`, `sharedDescription`, and `hashtags`.

```bash
# See individual image prompts
curl http://localhost:8000/api/plans/YOUR_SESSION_ID_HERE/prompts
```

---

## Step 8 — Start Image Generation

Once the plan is in `PLANNED` status, start the queue.

### Via the Dashboard

1. On the Sessions page, find your `PLANNED` session
2. Click **Start Queue** button
3. Status changes to `GENERATING`
4. Go to the **Queue** page to watch progress in real time

### Via API

```bash
curl -X POST http://localhost:8000/api/queue/start \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "YOUR_SESSION_ID_HERE"}'
```

**What happens next (automated):**

1. All image prompts are enqueued in BullMQ (Redis)
2. The worker picks up jobs (up to `WORKER_CONCURRENCY` at a time)
3. For each job, Playwright:
   - Opens Chromium headless browser
   - Navigates to Google ImageFX
   - Logs in with your Google credentials (first time only — session is cached)
   - Pastes the image prompt
   - Clicks Generate
   - Waits for the image to appear
   - Downloads it
4. The image is uploaded to Google Drive under `AI Personas / Character Name / Date / Session /`
5. MongoDB is updated with Drive file ID and URL
6. Session `generatedImages` counter increments

### Retry failed jobs:

```bash
# Retry all failed jobs in a session
curl -X POST http://localhost:8000/api/queue/retry \
  -H "Content-Type: application/json" \
  -d '{"sessionId": "YOUR_SESSION_ID_HERE"}'

# Retry a single job
curl -X POST http://localhost:8000/api/queue/retry \
  -H "Content-Type: application/json" \
  -d '{"promptId": "YOUR_PROMPT_ID_HERE"}'
```

---

## Step 9 — Monitor Progress

### Dashboard Overview

[http://localhost:8000](http://localhost:8000)

Shows:
- Total characters, sessions, images
- Queue stats (pending / processing / completed / failed)
- Recent sessions with progress bars
- Auto-refreshes every 30 seconds

### Queue Monitor

[http://localhost:8000/queue.html](http://localhost:8000/queue.html)

- Filter by status (QUEUED / PROCESSING / COMPLETED / FAILED)
- Filter by session
- Shows prompt text, attempts, and Drive link when complete
- Auto-refreshes every 10 seconds

### Session Detail

[http://localhost:8000/sessions.html](http://localhost:8000/sessions.html) → Click **View** on any session

Shows:
- Status flow diagram (Created → Planning → Planned → Generating → Done)
- Progress bar with generated/total count
- Content plan table (sections, content types, intents)

### API polling:

```bash
# Session status + completion %
curl http://localhost:8000/api/sessions/YOUR_SESSION_ID

# Queue counts for a session
curl http://localhost:8000/api/queue/status/YOUR_SESSION_ID

# Global queue counts
curl http://localhost:8000/api/queue/status
```

---

## Local Development (No Docker)

Use this if you want to run and modify the code directly.

### Prerequisites
- Python 3.12
- MongoDB 7 running locally (`brew install mongodb-community` on Mac)
- Redis 7 running locally (`brew install redis` on Mac)

### Setup

```bash
# 1. Start MongoDB and Redis
brew services start mongodb-community
brew services start redis

# 2. Set up Python environment
cd /path/to/persona-ai-studio/backend
python3.12 -m venv .venv
source .venv/bin/activate       # Mac/Linux
# .venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser
playwright install chromium

# 5. Configure environment
cp ../.env.example .env
# Edit .env — set MONGODB_URL=mongodb://localhost:27017 and REDIS_HOST=localhost

# 6. Start the API server (Terminal 1)
uvicorn app.main:app --reload --port 8000

# 7. Start the worker (Terminal 2)
source .venv/bin/activate
python -m worker.main

# 8. Open dashboard
# http://localhost:8000
```

### Seed sample data

```bash
python scripts/seed.py
```

---

## API Reference

Full interactive docs: **[http://localhost:8000/api/docs](http://localhost:8000/api/docs)**

### Characters

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/characters` | `CharacterCreate` | Create a character |
| `GET` | `/api/characters` | — | List all characters |
| `GET` | `/api/characters/{id}` | — | Get character by ID |
| `PUT` | `/api/characters/{id}` | `CharacterUpdate` | Update character |
| `DELETE` | `/api/characters/{id}` | — | Delete character |

### Sessions

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/sessions` | `SessionCreate` | Create a session |
| `GET` | `/api/sessions` | — | List all sessions |
| `GET` | `/api/sessions/{id}` | — | Get session by ID |

### Plans

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/plans/generate` | `{sessionId}` | Generate plan (async, background) |
| `POST` | `/api/plans/generate/sync` | `{sessionId}` | Generate plan (wait for result) |
| `GET` | `/api/plans/{sessionId}` | — | Get content plan sections |
| `GET` | `/api/plans/{sessionId}/prompts` | — | Get all image prompts |
| `GET` | `/api/plans/{sessionId}/prompts?status=FAILED` | — | Filter prompts by status |

### Queue

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/queue/start` | `{sessionId}` | Enqueue all image jobs |
| `POST` | `/api/queue/retry` | `{sessionId}` or `{promptId}` | Retry failed jobs |
| `GET` | `/api/queue/status/{sessionId}` | — | Queue counts for a session |
| `GET` | `/api/queue/status` | — | Global queue counts |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard` | Full dashboard summary |
| `GET` | `/api/dashboard/characters` | Per-character stats |
| `GET` | `/api/dashboard/sessions` | All sessions with stats |
| `GET` | `/api/health` | Health check |

---

## MongoDB Collections

```
characters       — AI persona profiles (name, appearance, niche, masterPrompt, status)
sessions         — Generation sessions (characterId, dates, status, progress counters)
contentPlans     — Day/section content plans (contentType, sharedDescription, hashtags)
imagePrompts     — Individual image prompts (prompt text, status, jobId, attempts)
generatedImages  — Completed images (driveFileId, driveUrl, generationTime)
historySummary   — Per-character history summaries for content deduplication
```

---

## Troubleshooting

### Docker containers not starting

```bash
# View logs for a specific service
docker compose logs backend
docker compose logs worker
docker compose logs mongodb

# Rebuild from scratch
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

### API returns 500 / Gemini errors

- Verify `GEMINI_API_KEY` is correct in `.env`
- Check the key has quota available at [https://aistudio.google.com/](https://aistudio.google.com/)
- Check logs: `docker compose logs backend`

### Worker not generating images / Playwright login fails

- Verify `GOOGLE_EMAIL` and `GOOGLE_PASSWORD` (use App Password)
- Check worker logs: `docker compose logs worker`
- The first run may fail if Google prompts for 2FA — run the worker locally once to complete the login interactively:
  ```bash
  # Run headful (visible browser) for first login:
  # Edit flow_automation.py: change headless=True to headless=False temporarily
  cd backend && python -m worker.main
  ```
- After first successful login, the session is cached at `/tmp/persona_browser_profile`

### Google Drive upload fails

- Ensure the service account JSON is valid single-line JSON in `.env`
- Verify the service account email has **Editor** access to the Drive folder
- Check: `docker compose logs worker | grep drive`

### Plan generation stuck in PLANNING

- Check backend logs: `docker compose logs backend`
- Verify Gemini API key has access to `gemini-2.5-pro`
- The plan generation is async — check session status via API:
  ```bash
  curl http://localhost:8000/api/sessions/YOUR_SESSION_ID
  ```

### Resetting everything

```bash
# Stop all containers and remove data volumes
docker compose down -v

# Start fresh
docker compose up -d
```

---

## Useful Commands

```bash
# View all running containers
docker compose ps

# Stream all logs
docker compose logs -f

# Stream only worker logs
docker compose logs -f worker

# Run seed script
docker compose exec backend python scripts/seed.py

# Open MongoDB shell
docker compose exec mongodb mongosh persona_ai_studio

# Check Redis queue
docker compose exec redis redis-cli LLEN bull:image-generation:wait

# Scale workers (run 3 workers in parallel)
docker compose up -d --scale worker=3

# Stop everything (keeps data)
docker compose stop

# Stop and delete all data
docker compose down -v
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI (Python 3.12) |
| Database | MongoDB 7 + Motor (async) |
| Queue | BullMQ (Python) + Redis 7 |
| AI Content | Gemini 2.5 Pro |
| Image Generation | Google ImageFX (via Playwright) |
| Asset Storage | Google Drive API (service account) |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Docker Compose |
