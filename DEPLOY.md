# Inkraft — Deployment Guide (Railway)

Inkraft is a single **FastAPI monolith** that serves the frontend, the API, and
`/outputs` images. It runs the LLM on **Groq** and image generation on **fal.ai**,
so the container needs **no GPU, no torch, and no Ollama**. One service to deploy.

## What was prepared for deploy (this repo)

- **`Dockerfile.railway`** — slim image (`python:3.10-slim` + `requirements-railway.txt`,
  no torch/diffusers/Ollama). The local Stable-Diffusion stack is imported lazily, so
  it is never pulled into the cloud image.
- **`requirements-railway.txt`** — cloud-only deps. (The full `requirements.txt`, used
  for local GPU dev, now also includes the previously-missing `supabase` + `python-dotenv`.)
- **`railway.json`** — tells Railway to build with `Dockerfile.railway`.
- **Volume-aware data paths** — set `DATA_DIR=/data` and ALL SQLite DBs land in
  `/data/db` and generated pages in `/data/outputs`, so they survive restarts/redeploys.
  Unset locally → nothing moves (existing in-repo `core/*.db` + `outputs/` are untouched).
- **`tools/backup_sqlite.py`** — consistent online backup of every `*.db` → `/data/backups`,
  keeps the newest 7.

## 1. Persistent volume (do this BEFORE the first deploy)

In the Railway service → **Variables/Settings → Volumes**, attach a volume mounted at:

```
/data
```

Then set `DATA_DIR=/data` (see env vars below). Without this, every redeploy wipes
users, credits, and history. (Northflank: same idea, attach a 0.5 GB+ volume at `/data`.)

## 2. Environment variables (set on the host — never commit)

| Variable | Value | Source |
|---|---|---|
| `FAL_KEY` | *(your fal.ai key)* | reuse from local `.env` |
| `GROQ_API_KEY` | *(your Groq key)* | reuse from local `.env` |
| `LLM_PROVIDER` | `groq` | required (default is ollama) |
| `SUPABASE_URL` | *(your project URL)* | reuse from local `.env` |
| `SUPABASE_PUBLISHABLE_KEY` | *(anon/publishable key)* | reuse from local `.env` |
| `SUPABASE_SECRET_KEY` | *(service/secret key)* | reuse from local `.env` |
| `DATA_DIR` | `/data` | matches the mounted volume |
| `IMAGE_ROUTING_MODE` | `nano_all` | tiered routing (default) |
| `PREMIUM_IMAGE_MODEL` | `fal-ai/nano-banana/edit` | cheap reference model (default) |
| `MAX_COST_PER_JOB` | `0.60` | per-comic fal.ai runaway guard (keep above a full comic's cost) |
| `MAX_PANELS_PER_COMIC` | `6` | hard panel cap (UI already maxes at 6); raise for a paid tier |

`IMAGE_PROVIDER` does **not** need setting — the app auto-selects `fal_ai` whenever a
real `FAL_KEY` is present. `PORT` is provided by Railway automatically.

> **Beta budget, without losing quality:** keep `IMAGE_ROUTING_MODE=nano_all` and
> `MAX_COST_PER_JOB=0.60` as-is. Lowering the cap or switching to `hybrid` would push
> panels onto cheap SDXL = visibly worse output. The quality-neutral lever is
> `MAX_PANELS_PER_COMIC` (panel COUNT, not per-panel quality). Monitor real spend with
> `python tools/cost_report.py --balance <your_fal_balance>`.

## 3. Deploy

1. Create a Railway project → **Deploy from GitHub repo** → `RD1241/Inkraft`
   (set the service root to `NovelToComic/` if Railway deploys from the repo root).
2. Railway picks up `railway.json` → builds `Dockerfile.railway`.
3. Attach the `/data` volume (step 1) and set the env vars (step 2).
4. Deploy. Railway assigns a free `*.up.railway.app` subdomain (Settings → Networking →
   Generate Domain).

## 4. Supabase redirect URLs

In Supabase → **Authentication → URL Configuration**, add the live domain to
**Site URL** and **Redirect URLs**, e.g.:

```
https://<your-app>.up.railway.app
https://<your-app>.up.railway.app/login.html
```

Otherwise email-confirmation / OAuth redirects bounce to localhost.

## 5. SQLite backups

Run `tools/backup_sqlite.py` on a schedule (Railway Cron service, or any host cron):

```
python tools/backup_sqlite.py        # writes /data/backups/<timestamp>/, keeps newest 7
BACKUP_KEEP=14 python tools/backup_sqlite.py
```

## Local container smoke test (no fal.ai spend)

```
docker build -f Dockerfile.railway -t inkraft-railway .
docker run --rm -p 8000:8000 --env-file .env -e DATA_DIR=/data -v inkraft_data:/data inkraft-railway
# then: GET http://localhost:8000/api/health  and open http://localhost:8000/
```

Only register/login + reads are free; running a generation spends fal.ai credits.

## First-deploy smoke test (founder, as a fresh signup)

register → balance = 3 → 1 single-char comic → 1 shared-frame multi-char comic →
Vault enforcement fires for an undefined character → download a PDF → log out/in →
confirm credits + characters + history **survive a service restart**.
