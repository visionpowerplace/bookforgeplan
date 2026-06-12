# BookForge — hosting guide

A web service that turns an uploaded `.docx` manuscript into a print-ready book PDF.
It wraps the BookForge engine with a landing page, accounts, a per-user library, a
background render queue, and a download endpoint.

## Accounts & persistence (multi-user) — IMPORTANT

BookForge has a landing page, sign-up / log-in, and a per-user library. Accounts and
book records live in **SQLite** under `BOOKFORGE_DATA`; uploaded manuscripts and
rendered PDFs live there too. Sessions are signed cookies (stdlib, no extra deps).

**To keep accounts and books across deploys you must mount a persistent disk.** On
Render: service → **Disks** → add a disk mounted at `/data`, then set:
```
BOOKFORGE_DATA      = /data
BOOKFORGE_ART_CACHE = /data/art-cache
SECRET_KEY          = (any long random string)   # stable session signing
```
Without a disk, `BOOKFORGE_DATA` defaults to `/tmp` and **all accounts/books reset on
every restart**. `SECRET_KEY` is auto-generated and stored under the data dir if unset,
but setting it explicitly is recommended.

Routes: `/` landing · `/signup` · `/login` · `/app` dashboard · `POST /auth/signup|login`,
`POST /auth/logout` · `POST /api/jobs` (auth) · `GET /api/library` ·
`GET /api/books/{id}/download`. For many concurrent users, move SQLite → Postgres and the
thread pool → Celery/RQ + Redis (only `db.py` and `jobs.py` change).

```
bookforge/            the formatting engine (parser, layout, render) + bundled fonts
bookforge_service/    the web layer
  app.py              FastAPI routes
  jobs.py             background render workers (thread pool)
  storage.py          per-job filesystem storage
  templates/index.html  the upload page
Dockerfile            bakes in WeasyPrint's system libraries + fonts
docker-compose.yml    one-command local run
```

## Run it locally

```bash
docker compose up --build
# open http://localhost:8000
```

Or without Docker (you must install WeasyPrint's system libs first — see its docs):

```bash
pip install -r bookforge_service/requirements.txt
uvicorn bookforge_service.app:app --port 8000
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/` | upload page |
| POST | `/api/jobs` | multipart: `file` (.docx) + `title, subtitle, author, isbn, publisher, year, epigraph, mode, trim, crop_marks` → `202 {id,status}` |
| GET  | `/api/jobs/{id}` | poll job status → `queued \| rendering \| done \| error` |
| GET  | `/api/jobs/{id}/download` | the finished PDF |
| GET  | `/healthz` | liveness probe |

`mode` = `bw\|color` · `trim` = `4x6\|5x8\|5.25x8\|5.5x8.5\|6x9\|8.5x11` ·
`font` = `classic\|editorial\|modern\|bold` · `art_style` = `emblem\|photographic\|cinematic\|watercolor\|painterly\|lineart\|abstract` ·
`crop_marks` = `true\|false`.
Env: `BOOKFORGE_MAX_MB` (default 25), `BOOKFORGE_DATA` (job storage dir), `PORT`.

### Real chapter art (optional)

By default chapter openers are drawn as **emblem crests** (a themed vector seal per
title) — no API, no cost, always works. To use **real images**, pick an `art_style`
other than `emblem` and configure a provider with `IMAGE_PROVIDER`:

**Pexels — free, commercial-safe stock photos (recommended).** No GPU, no per-image
cost, no verification. Get a key at pexels.com/api, then set:
```
IMAGE_PROVIDER=pexels
PEXELS_API_KEY=...
BOOKFORGE_ART_CACHE=/data/art-cache   # optional: reuse fetched images across renders
```
A thematic query is derived from each chapter title (e.g. "How to Grow Your Faith" →
"seedling growth sunrise"), the photo is cover-cropped to the trim, and the title band
is applied for legibility. Color books keep full-colour photos; B&W books convert to
grayscale. Pexels grants free commercial use with no attribution required.

**Unsplash** — same idea, free commercial use: `IMAGE_PROVIDER=unsplash` +
`UNSPLASH_ACCESS_KEY=...` (attribution appreciated per their guidelines).

**OpenAI gpt-image-1** — *generated* images instead of stock. `IMAGE_PROVIDER=openai`
+ `OPENAI_API_KEY=...`; needs billing and org verification for gpt-image-1, costs a few
cents per image, and is slower. `BOOKFORGE_IMAGE_QUALITY` (low/medium/high) and
`BOOKFORGE_IMAGE_MODEL` tune it.

Verify any setup at `/healthz` — it reports `"ai_images": true` once a provider is
configured. If a provider isn't set or a call fails, the build silently falls back to
the emblem crests and says so in the job message, so the tool never breaks.

### Typefaces

`font` selects an OFL pairing (bundled in `bookforge/assets/fonts/`): `classic`
(Oswald + EB Garamond), `editorial` (Playfair Display + Lora), `modern`
(Montserrat + Lora), `bold` (Anton + EB Garamond).

## Deploy to a managed host

Any host that builds a Dockerfile works. The image is self-contained.

- **Render / Railway / Fly.io**: point at this repo, it detects the `Dockerfile`. Set
  a persistent disk mounted at `/data` (so in-flight jobs survive a restart). Health
  check path `/healthz`. These platforms inject `$PORT`, which the CMD already honors.
- **A VM**: `docker compose up -d` behind nginx/Caddy for TLS.

## Scaling out (what to change, and where)

The demo runs **one process with an in-memory job table**, so run a **single worker**.
The code is structured so the two pieces you'd swap are isolated:

1. **Job queue → Redis.** Replace `jobs.py` with Celery or RQ backed by Redis, and run
   N render workers separately from the web process. `app.py` only calls `submit()` and
   `get()`, so nothing else changes. This is required before running multiple web
   replicas (otherwise replica A can't see a job created on replica B).
2. **Storage → S3/GCS.** Implement the four methods in `storage.py` (`save_upload`,
   `output_path`, `job_dir`, `cleanup`) against object storage. Serve downloads via a
   short-lived presigned URL instead of `FileResponse`.

## Before real users (production checklist)

- **Accounts & auth.** Add a user table and protect `/api/jobs*` (API key per account
  or session auth). Attach `user_id` to each job.
- **Quotas & billing.** Rate-limit uploads; meter renders per plan.
- **Retention.** TTL job dirs (e.g. delete after 24h) — `storage.cleanup()` is ready;
  wire it to a scheduled sweep.
- **Upload safety.** Cap size (done), validate the .docx really unzips, and run an AV
  scan on uploads.
- **Print fidelity** (engine-side, see engine README): CMYK / PDF-X export, font-license
  checks, image-DPI validation, and a cover-wrap generator. The service exposes these as
  soon as the engine does.

## Notes

- Renders take a few seconds to ~30s depending on chapter count and `color` mode (image
  generation dominates) — that's why it's a background job, not a blocking request.
- Each `mode`/`trim`/`crop_marks` combination is a fresh render; nothing is cached yet.

## Preparing a manuscript (what authors should know)

The parser detects chapters from several cues, so most real `.docx` files work as-is —
but it splits most reliably when each chapter title is one of:

- a paragraph in Word's **Heading 1** style (Home → Styles → Heading 1), **or**
- a short title line that **starts on a new page** (Insert → Page Break before it), **or**
- a line beginning **"Chapter 3", "Part II", "Secret 5"**, etc.

Other supported cues: ALL-CAPS or bold/centered title lines, and a larger font than the
body. Action-step modules are any short line containing "action step"; pull-quotes are
the Quote style or a standalone bold line; bullet/numbered lists use Word's list buttons.

If **no** chapter cues are found, the whole manuscript is still formatted — as one
continuous section — and the job message says so, rather than dropping the text.
