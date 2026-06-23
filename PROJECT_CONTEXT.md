# Persona AI Studio — Project Context Document

> Accurate as of June 2026. Use this to onboard an LLM on the exact current state of the codebase.

---

## What This App Does

Persona AI Studio is a self-hosted platform for generating AI influencer content. A single admin creates fictional AI personas (characters), then creates multi-day content batches. For each batch the AI produces per-day, per-section image descriptions — outfit, lighting, camera, location, pose, hashtags — that can be copy-pasted into any image generation tool. There is **no actual image generation inside the app**. Output is text only.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.12) |
| Database | MongoDB 7 + Motor (async) |
| AI — primary | Gemini 2.0 Flash via `google-generativeai` (currently falls back due to invalid key) |
| AI — fallback | Groq via `groq` SDK (`groq/compound-mini` — the only currently working model) |
| Frontend | Vanilla HTML/CSS/JS — dark theme, Inter + JetBrains Mono fonts |
| Containerization | Docker Compose — 2 containers: MongoDB + backend (no Redis, no worker) |

---

## Active Project Structure

```
persona-ai-studio/
├── prompts/
│   └── master_image_description.md    # Main system prompt template (see note on path gap)
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI entry — mounts: characters, batches, dashboard
│   │   ├── config.py                  # Settings via .env (@lru_cache — restart to reload)
│   │   ├── database.py                # Motor client + index setup
│   │   ├── logging_config.py          # structlog
│   │   ├── models/
│   │   │   ├── character.py           # CharacterDB, CharacterStatus (active/inactive)
│   │   │   ├── batch.py               # BatchDB, BatchStatus (CREATED/GENERATING/COMPLETED/PARTIAL/FAILED)
│   │   │   └── day_section.py         # DaySectionDB (per day+section AI output)
│   │   ├── schemas/
│   │   │   ├── character.py           # CharacterCreate, CharacterUpdate, CharacterResponse
│   │   │   ├── batch.py               # BatchCreate, BatchUpdate, SectionConfig, CharacterAIGenerate
│   │   │   └── dashboard.py           # Dashboard response shape
│   │   ├── repositories/
│   │   │   ├── base.py                # BaseRepository — async Motor CRUD
│   │   │   ├── character_repository.py
│   │   │   ├── batch_repository.py
│   │   │   └── day_section_repository.py  # includes get_recent_summaries()
│   │   ├── services/
│   │   │   ├── gemini_service.py      # AI provider (Gemini → Groq fallback), JSON extraction
│   │   │   ├── generation_service.py  # Batch generation loop: days → sections → AI → DB
│   │   │   └── character_service.py   # Character CRUD + AI profile generation wrapper
│   │   └── api/
│   │       ├── characters.py          # /api/characters (CRUD + /generate-ai)
│   │       ├── batches.py             # /api/batches (CRUD + generate + days)
│   │       └── dashboard.py           # /api/dashboard
├── frontend/
│   ├── index.html                     # Dashboard — stats + recent batches table (auto-refresh 30s)
│   ├── characters.html                # Character list + create modal (AI/Manual tabs)
│   ├── batches.html                   # Batch list + create modal
│   ├── batch-detail.html              # Day tabs → section cards → image description grid (click to copy)
│   ├── settings.html                  # API credentials page
│   ├── css/styles.css                 # Dark theme design tokens + full component CSS
│   └── js/common.js                   # Shared: api helper, toast, statusBadge, fmtNum, confirmAction
├── .env.example                       # Env var reference (currently has outdated vars — see gaps)
├── docker-compose.yml
└── README.md                          # OUTDATED — describes old v1 architecture, ignore
```

---

## MongoDB Collections

### `characters`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `name` | string | |
| `age` | string | e.g. "24 years old" |
| `gender` | string | |
| `persona` | string | personality description |
| `appearance` | string | physical description |
| `fashionStyle` | string | |
| `audience` | string | target audience |
| `niche` | string | content category |
| `city` | string | |
| `country` | string | |
| `masterPrompt` | string | custom system prompt; if set, overrides master_image_description.md |
| `status` | enum | `active` / `inactive` |
| `createdAt` / `updatedAt` | datetime | |

### `batches`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `characterId` | string | ref to characters._id |
| `batchName` | string | |
| `startDate` / `endDate` | string | ISO YYYY-MM-DD |
| `sections` | array of `{name: str, imageCount: int}` | e.g. `[{name:"Morning", imageCount:3}]` |
| `contentSummary` | string | user-provided sequel/theme context for AI |
| `status` | enum | CREATED / GENERATING / COMPLETED / PARTIAL / FAILED |
| `totalDays` | int | computed on create |
| `totalImages` | int | computed after generation (actual count) |
| `errorMessage` | string | set on FAILED or PARTIAL |
| `createdAt` / `updatedAt` | datetime | |

### `daySections`
| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | |
| `batchId` | string | |
| `dayNo` | int | 1-based |
| `date` | string | ISO YYYY-MM-DD |
| `sectionName` | string | e.g. "Morning" |
| `contentType` | string | "Evergreen" / "Growth" / "Controversial" |
| `sectionIntent` | string | one-line vibe description |
| `contentSummary` | string | AI-generated summary of section content |
| `outfitFamily` | string | shared across all images in section |
| `lightingMood` | string | shared |
| `cameraStyle` | string | shared |
| `backgroundLocation` | string | shared |
| `hashtags` | string[] | 5 hashtags (4 niche + #fyp) |
| `imageDescriptions` | object[] | see below |
| `createdAt` | datetime | |

**imageDescriptions item shape:**
```json
{
  "imageNo": 1,
  "pose": "...",
  "bodyAngle": "...",
  "handPlacement": "...",
  "framing": "..."
}
```

---

## API Endpoints (All Active)

Base path: `/api` — served by FastAPI, frontend served as StaticFiles at `/`

### Characters — `/api/characters`
| Method | Path | Body / Params | Response |
|---|---|---|---|
| GET | `/api/characters` | — | `CharacterDB[]` |
| POST | `/api/characters` | `CharacterCreate` | `CharacterDB` (201) |
| GET | `/api/characters/{id}` | — | `CharacterDB` |
| PUT | `/api/characters/{id}` | `CharacterUpdate` (all fields optional) | `CharacterDB` |
| DELETE | `/api/characters/{id}` | — | 204 |
| POST | `/api/characters/generate-ai` | `{name, niche, vibe, location}` | AI-generated profile dict (not saved) |

### Batches — `/api/batches`
| Method | Path | Body / Params | Response |
|---|---|---|---|
| GET | `/api/batches` | `?character_id=` (optional) | `BatchDB[]` enriched with `characterName` |
| POST | `/api/batches` | `BatchCreate` | `BatchDB` (201) |
| GET | `/api/batches/{id}` | — | `BatchDB` + `characterName` |
| PUT | `/api/batches/{id}` | `BatchUpdate` | `BatchDB` |
| DELETE | `/api/batches/{id}` | — | 204 (also deletes its daySections) |
| POST | `/api/batches/{id}/generate` | `{}` | 202 — starts background task |
| POST | `/api/batches/{id}/generate/sync` | `{}` | Waits for result, returns summary dict |
| GET | `/api/batches/{id}/days` | — | Days grouped: `[{dayNo, date, sections[]}]` |
| GET | `/api/batches/{id}/days/{day_no}` | — | `{dayNo, date, sections[]}` |

### Dashboard — `/api/dashboard`
| Method | Path | Response |
|---|---|---|
| GET | `/api/dashboard` | `{totalCharacters, activeCharacters, totalBatches, completedBatches, totalImages, recentBatches[10]}` |

### Health
| Method | Path | Response |
|---|---|---|
| GET | `/api/health` | `{"status": "ok", "version": "..."}` |

---

## Core Schemas

### `BatchCreate`
```python
{
  "characterId": str,
  "batchName": str,          # min_length=1
  "startDate": str,          # YYYY-MM-DD
  "endDate": str,            # YYYY-MM-DD (must be >= startDate)
  "sections": [              # min 1 item
    {"name": str, "imageCount": int}  # imageCount: 1–50
  ],
  "contentSummary": str      # optional — sequel/theme hint passed to AI
}
```

### `CharacterCreate`
```python
{
  "name": str,
  "age": str,
  "gender": str,
  "persona": str,
  "appearance": str,
  "fashionStyle": str,
  "audience": str,
  "niche": str,
  "city": str,
  "country": str,
  "masterPrompt": str,       # optional — overrides default prompt file if set
  "status": "active"
}
```

---

## Generation Flow (Detailed)

```
POST /api/batches/{id}/generate
  └── Background task: GenerationService.generate_batch(batch_id)
        └── Fetch batch + character from DB
        └── Set batch.status = GENERATING
        └── Fetch previous_summaries from daySections (for dedup context)
        └── Delete existing daySections for this batch (clean regenerate)
        └── For day_no in 1..N:
              For section in batch.sections:
                └── _generate_section_with_retry(gemini, character, day_no, date, section, context)
                      └── Retry delays: [0, 30, 60, 90]s on rate_limit/429/503/timeout errors
                      └── Non-retriable errors fail immediately
                └── Parse JSON response → extract days[].sections[]
                └── Insert DaySection doc into daySections collection
                └── Sleep 3s between section calls (avoid rate limits)
        └── Final status:
              - ALL days failed → FAILED
              - SOME days failed → PARTIAL + errorMessage = "Days failed: [1, 3]"
              - No failures → COMPLETED
        └── Update batch.totalImages = actual count of imageDescriptions saved
```

---

## AI Service (`gemini_service.py`)

### Provider selection (at `__init__`)
1. If `GEMINI_API_KEY` is set → use Gemini (`google-generativeai`)
2. Else if `GROQ_API_KEY` is set → use Groq directly
3. Else → raise `RuntimeError`

### Runtime fallback
If Gemini is configured but call fails → falls back to Groq on the fly (if `GROQ_API_KEY` is available).

### JSON mode
Groq JSON mode is enabled only for models where `supports_json_mode = True`.
Excluded models (no JSON mode): anything containing `"gemma"`, `"qwen"`, or `"llama-4"`.

### Two AI methods
| Method | Used by | Purpose |
|---|---|---|
| `generate_single_section(character, day_no, date_str, section, content_summary, previous_summaries)` | `GenerationService` | Generate one section's full JSON output |
| `generate_character(name, niche, vibe, location)` | `CharacterService` | Generate a full character profile from minimal input |

### `_extract_json`
Strips markdown fences, tries `json.loads()`, falls back to bracket-depth scanner to extract outermost `{...}` or `[...]`. Raises `ValueError` if nothing found.

### Prompt construction for section generation
```
{master_prompt or character.masterPrompt}

Number of Days: 1
Dates: {date_str}
Sections per day: {section_name}: {imageCount} images
Batch theme / sequel context: {contentSummary}     ← omitted if empty
Previous batch content (avoid repeating):           ← omitted if empty
- {summary1}
- {summary2}  (up to 5)

Character Profile:
Name: ... | Age: ... | Gender: ...
Niche: ... | Location: city, country
Personality: ...
Appearance: ...
Fashion: ...
```

### AI provider notes
- **Gemini key is invalid** — starts with `AQ.` (valid keys start with `AIza`). All calls fall back to Groq.
- **Working Groq model**: `groq/compound-mini` — JSON mode supported, ~20s per section call
- **Groq models that fail**: llama-3.3-70b-versatile (TPD exhausted), llama-3.1-8b-instant (TPM 6k too low), gemma2-9b-it (decommissioned), llama-4-scout (TPD exhausted), qwen3-32b (no JSON mode, outputs `<think>` tags)
- `max_tokens = 4000` per call (sufficient for 1 section + up to 50 images)
- Full 3-day × 3-section batch ≈ 3–4 minutes total

---

## Frontend (Vanilla JS)

### `js/common.js` — Shared utilities
- `api.get(path)` / `api.post(path, body)` — fetch wrapper, throws on non-2xx
- `toast.success(title, msg)` / `toast.error(title, msg)` — toast notifications
- `statusBadge(status)` — returns `<span class="badge badge--{status_lower}">` HTML
- `fmtNum(n)` — number formatter
- `confirmAction(message, callback)` — confirm dialog

### Page: `batch-detail.html`
State machine based on `batch.status`:
- `CREATED` / `PARTIAL` / `FAILED` → "Ready to Generate" or error CTA with "Try Again"
- `GENERATING` → spinner + polling every 4s via `setInterval`
- `COMPLETED` → day tabs + section cards + image grid

Copy behaviour:
- Click image card → copies full prompt: `"Outfit: X. Lighting: Y. Camera: Z. Location: W. Pose: A. Body angle: B. Hand placement: C. Framing: D."`
- Hashtag row has `# Copy` button → copies all hashtags as space-separated string

### Sidebar navigation (all pages)
Dashboard → Characters → Batches → Settings (no dead links)

---

## Environment Variables (Required)

```env
# App
APP_NAME=Persona AI Studio
APP_VERSION=1.0.0
DEBUG=false

# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB=persona_ai_studio

# AI — set at least one
GEMINI_API_KEY=AIza...          # Must start with AIza (current key is invalid)
GROQ_API_KEY=gsk_...            # Currently the only working path
GROQ_MODEL=groq/compound-mini   # Working model as of June 2026

# CORS
CORS_ORIGINS=["http://localhost:8000"]
```

---

## Dead Code (v1 — Present in Repo, NOT Active)

These files exist on disk but are **not imported or mounted anywhere** in the active app. They are from a previous architecture that used BullMQ, Redis, Playwright browser automation, and Google Drive.

**Dead API routes** (not in `main.py`):
- `backend/app/api/sessions.py`
- `backend/app/api/plans.py`
- `backend/app/api/queue.py`

**Dead services**:
- `backend/app/services/queue_service.py`
- `backend/app/services/history_service.py`
- `backend/app/services/google_drive_service.py`

**Dead models**:
- `backend/app/models/session.py`
- `backend/app/models/content_plan.py`
- `backend/app/models/image_prompt.py`
- `backend/app/models/generated_image.py`
- `backend/app/models/history_summary.py`

**Dead repositories**:
- `backend/app/repositories/session_repository.py`
- `backend/app/repositories/content_plan_repository.py`
- `backend/app/repositories/image_prompt_repository.py`
- `backend/app/repositories/generated_image_repository.py`

**Dead worker** (entire directory):
- `backend/worker/main.py`
- `backend/worker/processors/image_processor.py`
- `backend/worker/processors/flow_automation.py`
- `backend/Dockerfile.worker`

**Dead frontend pages** (served but call non-existent API routes):
- `frontend/queue.html`
- `frontend/sessions.html`

---

## Identified Gaps and Fixes

### GAP 1 — Prompt file at wrong path (HIGH — silently broken)
**Problem**: `gemini_service.py` computes `_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"` which resolves to `backend/prompts/`. But the actual file is at the project root: `prompts/master_image_description.md`. `_load_prompt()` returns an empty string if the file is not found, so the section generation prompt becomes empty. The app silently falls back to `character.masterPrompt` or sends an empty prompt to the AI.

**Fix**: Either move `prompts/` into `backend/prompts/`, or fix the path in `gemini_service.py`:
```python
_PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"
# (4 levels up from gemini_service.py = project root)
```

---

### GAP 2 — `character_generation.md` prompt file missing (HIGH)
**Problem**: `gemini_service.generate_character()` calls `_load_prompt("character_generation.md")`. This file doesn't exist in the repo (neither at `prompts/` nor `backend/prompts/`). When missing, `_load_prompt` returns `""`, so AI character generation sends a blank prompt. The AI response will be unpredictable.

**Fix**: Create `prompts/character_generation.md` (alongside `master_image_description.md`) with a prompt that instructs the AI to return a JSON character profile given `{name}`, `{niche}`, `{vibe}`, `{location}` placeholders.

---

### GAP 3 — README is completely wrong (HIGH — misleads developers)
**Problem**: `README.md` describes the old v1 architecture — 4 Docker containers (MongoDB, Redis, backend, worker), BullMQ, Playwright, Google Drive OAuth, Sessions/Plans/Queue APIs. None of this applies to the current app.

**Fix**: Rewrite README to describe v2: 2-container setup, batch workflow, Groq/Gemini AI, text-only output, correct env vars.

---

### GAP 4 — `.env.example` has wrong variables (HIGH)
**Problem**: Contains Redis, BullMQ worker, Playwright, ImageFX, and Google Drive vars that no longer exist. Missing `GROQ_API_KEY` and `GROQ_MODEL` which are required for the app to work.

**Fix**: Replace `.env.example` content with only the vars listed in the "Environment Variables" section above.

---

### GAP 5 — Dead code clutters the repo (MEDIUM)
**Problem**: ~20 files from v1 still present. Any developer or LLM reading the repo will be confused about which architecture is real. `google_drive_service.py` also has an auth approach mismatch (uses OAuth client credentials but old env docs reference service account JSON).

**Fix**: Delete all files listed in the "Dead Code" section.

---

### GAP 6 — `PARTIAL` status not handled in `batch-detail.html` (MEDIUM)
**Problem**: `batch-detail.html` handles `COMPLETED`, `GENERATING`, `FAILED`, and a catch-all (CREATED). But `PARTIAL` status — set when some days fail but others succeed — falls into the catch-all which shows "Ready to Generate." This means partially generated batches show the generate CTA rather than showing what was generated and indicating which days failed.

**Fix**: Add a `PARTIAL` case in `loadBatch()` that shows the day tabs for successfully generated days while displaying a warning banner listing the failed day numbers (`batch.errorMessage`). Also add a "Regenerate" action.

---

### GAP 7 — No per-section regeneration (LOW)
**Problem**: If one section's AI call fails mid-batch, the entire batch must be regenerated. There is no endpoint to retry a single day or section.

**Fix**: Add `POST /api/batches/{id}/days/{day_no}/sections/{section_name}/generate` that regenerates just that section and upserts the DaySection document.

---

### GAP 8 — `batch-detail.html` poll doesn't handle `PARTIAL` status (LOW)
**Problem**: The 4-second polling loop in `startPoll()` only stops on `COMPLETED` or `FAILED`. If generation ends in `PARTIAL`, the poll continues indefinitely.

**Fix**: Add `PARTIAL` to the terminal states in `startPoll()`:
```js
} else if (['COMPLETED', 'PARTIAL', 'FAILED'].includes(updated.status)) {
```

---

### GAP 9 — Dead HTML pages still served (LOW)
**Problem**: `frontend/queue.html` and `frontend/sessions.html` are served by FastAPI's StaticFiles mount. They call v1 API routes (`/api/queue`, `/api/sessions`) that return 404. A user who navigates to these pages sees broken UI.

**Fix**: Delete `frontend/queue.html` and `frontend/sessions.html`.

---

### GAP 10 — `master_image_description.md` has a content policy violation (NOTE)
**Problem**: Line 2 of the master prompt contains an explicit rule about cleavage/body exposure content. This is a business decision but worth flagging — if the prompt file is missing (see Gap 1) the AI will not receive this instruction, which changes generation output significantly.

**No fix required** — flagged for awareness only. Resolving Gap 1 (prompt path) makes this prompt actually load.

---

## UX / Experience Gaps

### UX-GAP 1 — `?character=` URL param ignored on batches page (HIGH)
**Where**: `characters.html` character card has a "Batches" link → `batches.html?character=${c._id}`. But `batches.html` never reads `URLSearchParams` to pre-fill the filter dropdown. The link navigates to the batches page with no filter applied.
**User impact**: Clicking "Batches" on a character card does nothing useful — user still sees all characters' batches and has to re-select manually.
**Fix**: In `batches.html` `init()`, read `new URLSearchParams(location.search).get('character')` and pre-select `filter-character` dropdown before calling `loadBatches()`.

---

### UX-GAP 2 — Deleting a character orphans all its batches (HIGH)
**Where**: `DELETE /api/characters/{id}` in `characters.py` only deletes the character document. `DELETE /api/batches/{id}` in `batches.py` deletes the batch + its daySections, but character deletion never calls it.
**User impact**: After deleting a character, all its batches still exist in MongoDB with a dangling `characterId`. They appear in the batches list with "Unknown" as the character name. The user has no way to know they exist.
**Fix (option A — cascade)**: In `CharacterService.delete()`, also delete all batches for that character and all their daySections.
**Fix (option B — warn)**: Count batches before deletion and include in the confirm dialog: `"Delete Riva Mehra? This will also delete 4 batches and all their content."` Then cascade-delete on confirm.

---

### UX-GAP 3 — No batch export or copy-all (HIGH)
**Where**: `batch-detail.html` — each image description card requires an individual click to copy. There is no "Copy All" button per section and no way to export an entire batch.
**User impact**: A 7-day × 3-section × 10-image batch = 210 manual copy clicks. For the primary use case (pasting into an image generator), this makes the app extremely tedious at scale.
**Fix**:
1. Add a "Copy All" button on each section card that copies all image descriptions for that section as a numbered list.
2. Add an "Export Batch" button on the batch detail topbar that downloads a `.txt` or `.json` file with all days → sections → image descriptions.

---

### UX-GAP 4 — Batches list has no auto-refresh (MEDIUM)
**Where**: `batches.html` — the batch list renders once on load. There is no `setInterval` polling like on `index.html` (which refreshes every 30s).
**User impact**: If a user opens the batches page while a batch is generating, the status badge stays "GENERATING" forever until they manually refresh. The dashboard updates but the batches list doesn't.
**Fix**: Add `setInterval(loadBatches, 15000)` in `batches.html`, or only poll when at least one batch has status `GENERATING`.

---

### UX-GAP 5 — No generation progress feedback (MEDIUM)
**Where**: `batch-detail.html` shows a spinner with "Generating… Gemini is creating your content plan. This takes 15–60 seconds." No progress indication.
**Backend**: `GET /api/batches/{id}` returns the batch but only the final `status` — there's no `sectionsCompleted` or `sectionsTotal` counter.
**User impact**: For a large batch (e.g. 7 days × 3 sections = 21 AI calls × ~20s = ~7 minutes), the user sees a spinner with zero feedback. They don't know if it's working or stuck.
**Fix**:
1. Backend: add `generatedSections: int` counter to `BatchDB`, increment it after each successful section insert in `generation_service.py`.
2. Frontend: in `startPoll()`, render `"${batch.generatedSections} / ${batch.totalSections} sections done"` below the spinner.

---

### UX-GAP 6 — Section display order is alphabetical, not user-defined (MEDIUM)
**Where**: `DaySectionRepository.find_by_batch_and_day()` sorts by `("sectionName", 1)` — alphabetical ascending. Same in `find_by_batch()`.
**User impact**: A user who defines sections as `Morning → Evening → Night` will see them displayed as `Evening → Morning → Night` (alphabetical). This is visually wrong and confusing.
**Fix**:
1. Add a `sectionOrder: int` field to `DaySectionDB`, populated from the index of the section in `batch.sections` during generation.
2. Change repository sorts to `[("dayNo", 1), ("sectionOrder", 1)]`.

---

### UX-GAP 7 — Settings page shows v1-only content (MEDIUM)
**Where**: `settings.html`
- "Storage" tab describes Google Drive folder structure (`AI Personas / Character Name / YYYY-MM-DD / Session ID / image_001.jpg`) — this is v1 only. Drive storage doesn't exist in v2.
- "Automation" tab describes Playwright/ImageFX/headless Chrome/`GOOGLE_EMAIL` — all dead v1 features.
- "API Keys" tab checks for Redis and Google Service Account — neither exists in v2.
- Groq API key is not shown despite Groq being the active AI provider.
**User impact**: Settings page actively misleads users about how the app works.
**Fix**:
1. Remove "Storage" and "Automation" tabs entirely.
2. Replace Redis and Google Service Account rows with Groq API key status.
3. Add a `/api/health/ai` endpoint that tests the configured AI provider (Gemini or Groq) with a minimal call and returns `{provider, model, status}`. Display result in the API Keys section.

---

### UX-GAP 8 — No quick "Generate" action on batch list rows (LOW)
**Where**: `batches.html` — each batch row has "View" and "Delete" buttons. The primary action for a new batch is generation, but there's no "Generate" button on the list.
**User impact**: To generate a batch, user must: click "View" → wait for batch-detail page to load → click "Generate Descriptions". That's 3 steps where 1 would do.
**Fix**: Add a "Generate" button to the batch row, visible only when `status === 'CREATED' || status === 'FAILED' || status === 'PARTIAL'`. On click, call `POST /api/batches/{id}/generate` and redirect to batch-detail.

---

### UX-GAP 9 — Duplicate section names allowed in batch create form (LOW)
**Where**: `batches.html` `saveBatch()` — sections are collected from the form without uniqueness validation.
**User impact**: A user adding "Morning" twice creates two DaySections with identical `sectionName` per day. The AI receives two identical section definitions, likely generating near-duplicate content. The batch-detail view shows two identically-named section cards with no way to distinguish them.
**Fix**: In `saveBatch()`, check for duplicate section names before sending to API:
```js
const names = sections.map(s => s.name.toLowerCase());
if (new Set(names).size !== names.length) { toast.error('Section names must be unique'); return; }
```

---

### UX-GAP 10 — Character delete confirmation doesn't mention orphaned batches (LOW)
**Where**: `characters.html` `deleteCharacter()` confirm message: `"Delete character "${name}"? This cannot be undone."`
**User impact**: User doesn't know they'll lose access to all associated batches. The confirmation provides no context about consequences.
**Fix**: Before showing the confirm dialog, fetch the character's batch count from `GET /api/batches?character_id={id}` and include it in the message: `"Delete Riva Mehra? She has 4 batches. All will become inaccessible. This cannot be undone."`

---

### UX-GAP 11 — No generation cancellation (LOW)
**Where**: `generation_service.generate_batch()` runs as a FastAPI `BackgroundTask`. There is no cancellation endpoint.
**User impact**: If a user starts generation with wrong settings (wrong character, wrong dates), they cannot cancel. They must wait for full completion or failure, then regenerate.
**Fix**: Track the running generation in a simple in-memory dict keyed by `batch_id`. Add `POST /api/batches/{id}/cancel` that sets a `cancelled` flag checked between section iterations in the generation loop.

---

### UX-GAP 12 — `progressBar()` utility in `common.js` is unused (LOW / NOTE)
**Where**: `frontend/js/common.js` line 112 — `progressBar(pct)` renders an HTML progress bar. No page currently calls it.
**Relevance**: This utility already exists and is ready to use for UX-GAP 4 (batches list showing generation progress) and UX-GAP 5 (batch-detail generation progress).

---

## Key Files to Read First (For Any New Task)

| Priority | File | Why |
|---|---|---|
| 1 | `backend/app/main.py` | Entry point — which routers are active |
| 2 | `backend/app/services/gemini_service.py` | AI provider, prompt building, JSON extraction, fallback |
| 3 | `backend/app/services/generation_service.py` | Full generation loop, retry, DaySection structure |
| 4 | `prompts/master_image_description.md` | System prompt the AI receives (currently not loading — Gap 1) |
| 5 | `backend/app/api/batches.py` | All batch endpoints including generate |
| 6 | `frontend/batch-detail.html` | End-user view — largest and most complex frontend page |
| 7 | `frontend/js/common.js` | Shared JS utilities used by all pages |
