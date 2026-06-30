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
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | primary extraction/storyboard model |
| `GROQ_FALLBACK_MODELS` | `meta-llama/llama-4-scout-17b-16e-instruct,openai/gpt-oss-120b,llama-3.1-8b-instant` | tried in order on a 429/unavailable so extraction never degrades to the ghost-producing rule-based fallback. Each model has its OWN separate free daily bucket → ~4× effective free capacity with high-quality fallbacks (all verified 2026-06-30). ⚠️ **Free Groq 70B = 100k tokens/day ≈ ~15 comics/day**; the chain multiplies that. The real scale fix is the paid Dev tier (~$0.004/comic) — but it was **"temporarily unavailable" on Groq as of 2026-06-30**; retry later, use this chain meanwhile. |
| `SUPABASE_URL` | *(your project URL)* | reuse from local `.env` |
| `SUPABASE_PUBLISHABLE_KEY` | *(anon/publishable key)* | reuse from local `.env` |
| `SUPABASE_SECRET_KEY` | *(service/secret key)* | reuse from local `.env` |
| `DATA_DIR` | `/data` | matches the mounted volume |
| `IMAGE_ROUTING_MODE` | `flux_all` | **(changed 2026-06-28)** every panel = FLUX dev text-to-image. ⚠️ If your Railway service still has this set to `nano_all`, change it to `flux_all` — see note below. |
| `PREMIUM_IMAGE_MODEL` | `fal-ai/nano-banana/edit` | only used by nano_all/hybrid/pro_shared |
| `MAX_COST_PER_JOB` | `0.60` | per-comic fal.ai runaway guard (keep above a full comic's cost) |
| `MAX_PANELS_PER_COMIC` | `6` | hard panel cap (UI already maxes at 6); raise for a paid tier |
| `NEW_USER_CREDITS` | `5` | starting credits for new signups |
| `CREDIT_PANEL_TIERS` | `2:1,4:2,6:3` | tiered credit pricing: ≤2 panels=1cr, ≤4=2cr, ≤6=3cr |
| `CREDITS_AI_DEFAULT` | `2` | credits charged when panel count is AI-decided |
| `CONCURRENT_WORKERS` | `4` | parallel comic jobs; raise for open beta |

`IMAGE_PROVIDER` does **not** need setting — the app auto-selects `fal_ai` whenever a
real `FAL_KEY` is present. `PORT` is provided by Railway automatically.

> **⚠️ ROUTING CHANGE (2026-06-28) — flip your Railway env var.** The default
> `IMAGE_ROUTING_MODE` is now **`flux_all`** (was `nano_all`). The QA pass verified on
> a real Kael/Elena manga page that routing every panel through FLUX dev text-to-image
> gives better prompt adherence AND keeps Vault characters consistent (strong identity
> tokens + seed-lock) at lower cost than the nano reference-editor. **If your Railway
> service has `IMAGE_ROUTING_MODE=nano_all` set explicitly, change it to `flux_all`**
> (or delete the var to use the new default). Keep `nano_all` only if you specifically
> want reference-anchored consistency over prompt adherence.
>
> **Image model (new default 2026-06-28):** every style's text-to-image model now
> defaults to **FLUX dev** (`fal-ai/flux/dev`, ~$0.025/img). The paid model bake-off
> showed it follows the prompt dramatically better than fast-sdxl (correct multi-
> character composition, prop/period accuracy, native B&W manga) — and it's *cheaper*
> than the nano-banana path ($0.039). No env var needed; leave `FAL_*_MODEL` /
> `FAL_*_ENDPOINT` unset. To revert one style to SDXL, set both
> `FAL_<STYLE>_ENDPOINT=fal-ai/fast-sdxl` and `FAL_<STYLE>_MODEL=<hf id>`; for max
> fidelity push a style to `fal-ai/flux-pro/v1.1`. Cost note: a 6-panel comic is
> ~$0.15 on FLUX dev (was ~$0.015 on SDXL but visibly worse) — still well under
> `MAX_COST_PER_JOB=0.60`.

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

**Automatic (default):** when `DATA_DIR` is set (i.e. on Railway with the volume), the app runs an
in-process daily SQLite backup on startup — no extra service needed (a separate cron can't reach a
single-service Railway volume). Tune with env vars: `BACKUP_INTERVAL_HOURS` (default 24, floored at
1) and `BACKUP_KEEP` (default 7). Writes `/data/backups/<timestamp>/`. Disabled in local dev
(no `DATA_DIR`). NOTE: critical data (accounts/credits/vault/history) also lives in Supabase, which
is the primary durability layer — these snapshots are secondary insurance for the on-volume SQLite.

**Manual run** (still available):

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
