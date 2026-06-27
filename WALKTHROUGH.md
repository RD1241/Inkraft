# Inkraft — Project Walkthrough (updated 2026-06-28)

A current, end-to-end tour of what Inkraft is, how it works, and where everything
lives. For the day-to-day AI handoff log see `AI_HANDOFF.md`; for deploy steps see
`DEPLOY.md`.

---

## 1. What Inkraft is

Paste a story scene → Inkraft turns it into a finished comic page. It extracts the
characters and scene, plans a cinematic storyboard, generates the panel art, and
composites a final page with speech bubbles and SFX. Five art styles: **manga,
manhwa, anime, cinematic, realistic.**

It's a single **FastAPI monolith** that serves the web frontend, the API, and the
generated images — one service, no separate frontend host.

---

## 2. How a comic gets made (the pipeline)

`services/comic_service.py → process_job_worker` orchestrates it:

1. **Scene extraction** (`core/llm_processor.py`) — an LLM reads the story and pulls
   out characters, actions, and dialogue. Runs on **Groq cloud** (`LLM_PROVIDER=groq`),
   so no local Ollama is needed in production.
2. **Storyboard planning** (`core/storyboard_director.py`) — decides panel count,
   camera shots, pacing, lighting, and tension per panel.
3. **Vault override** (`core/memory_manager.py`) — if a character has a saved Character
   Vault sheet, its canonical look replaces whatever the extractor guessed, so
   characters stay identical across panels and across comics.
4. **Prompt building** (`core/prompt_builder.py`) — assembles the layered image prompt
   (camera, emotion, character identity, lighting, action, style) and applies the
   resolved **colour mode** (monochrome vs colour tokens).
5. **Image generation** (`providers/image/fal_ai.py`) — generates each panel on
   **fal.ai**. Tiered routing sends character panels through the cheap, reference-
   conditioned **Nano Banana** model for consistency; SDXL is the fallback.
6. **Composition** (`core/comic_renderer.py`, `core/panel_compositor.py`) — lays out
   the panels into a page and draws speech bubbles / sound effects.

Two generation shapes: **single_page** (one big panel) and **panel_strip**
(multi-panel grid) — chosen by style/format/panel count.

---

## 3. Features

- **5 art styles** + **Auto-detect** from the text.
- **Panel count** selector (AI-decided, or 1–6) — on both the Generate wizard and the
  Dashboard quick-generate form.
- **Colour mode** (`color_mode`: `auto | color | bw`) — Auto = manga is B&W, others
  colour; or force Colour / B&W on any style. Threaded through the prompt builder and
  fal.ai grayscale step.
- **Character Vault** — save recurring characters once (look, outfit, features) and
  reuse them so they render identically everywhere. Stored in Supabase
  (`character_design_sheets`) with a local SQLite fallback.
- **Credits & tiered pricing** — new users get **5 credits**; a comic costs credits by
  size: **1–2 panels = 1, 3–4 = 2, 5–6 = 3** (AI-decided = 2). Credits track real
  fal.ai cost while keeping full render quality. PDF export costs 1 credit.
- **History & Gallery** — past comics saved per user; shareable gallery.
- **PDF export** of a finished comic.
- **Auth** via Supabase.

---

## 4. Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (Python 3.10), Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (`frontend/`) |
| LLM | Groq cloud (scene extraction + storyboard) |
| Images | fal.ai (Nano Banana edit + SDXL models) |
| Auth | Supabase |
| Data | SQLite (credits, jobs, history, character vault, cache, metrics) + Supabase sync |
| Deploy | Docker → Railway (slim image, persistent volume) |

---

## 5. Where things live

```
api/            FastAPI app + routes (main.py, routes/generate.py, characters.py, ...)
core/           pipeline brains: llm_processor, storyboard_director, prompt_builder,
                memory_manager, comic_renderer, panel_compositor, *.db (gitignored)
services/       comic_service (orchestrator), credits_service, history/gallery/job/billing
providers/      image/fal_ai.py, llm/ (groq, ollama, chat_client), auth/supabase_auth.py,
                storage/local.py, factory.py
config/         settings.py (all env-driven config)
frontend/       index.html (generate wizard), dashboard.html, login/register, vault,
                history, gallery, style.css, auth.js
tools/          backup_sqlite.py, cost_report.py, check_models.py, ...
Dockerfile.railway, railway.json, requirements-railway.txt   (cloud deploy)
DEPLOY.md, WALKTHROUGH.md, AI_HANDOFF.md                       (docs)
```

---

## 6. Cost & credits model

- fal.ai cost ≈ **$0.039 per panel** (Nano Banana). A comic ≈ panels × $0.039 →
  ~$0.04 (1 panel) to ~$0.24 (6 panels).
- Tiered credits keep spend bounded: **5 free credits ≈ ≤$0.40 worst-case per user.**
- Guardrails: `MAX_COST_PER_JOB` (per-comic spend cap), `MAX_PANELS_PER_COMIC` (hard
  panel cap), and a soft SDXL fallback if a job ever approaches the cap.
- Monitor real spend anytime: `python tools/cost_report.py --balance <fal_balance>`.

All of this is env-tunable (see §9) — pricing can change without a code edit.

---

## 7. Running locally

```
# from NovelToComic/
venv\Scripts\python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000
```

Requires a local `.env` (gitignored) with `FAL_KEY`, `GROQ_API_KEY`, `LLM_PROVIDER=groq`,
and the three `SUPABASE_*` keys. Locally the SQLite DBs live under `core/` and outputs
under `outputs/` (unchanged from before).

---

## 8. Deploying (summary)

Single service on **Railway**. The slim `Dockerfile.railway` builds a ~342 MB image
(no torch/Ollama — runs on Groq + fal.ai). A persistent volume at `/data` (with
`DATA_DIR=/data`) keeps all SQLite DBs + generated images across restarts. Full
step-by-step in **`DEPLOY.md`**.

---

## 9. Key config / env vars (`config/settings.py`)

| Var | Default | Purpose |
|---|---|---|
| `FAL_KEY` | — | fal.ai image generation (auto-selects fal provider) |
| `GROQ_API_KEY` + `LLM_PROVIDER=groq` | — | LLM on Groq (no Ollama) |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` | — | auth + sync |
| `DATA_DIR` | (unset) | set to `/data` on Railway for the persistent volume |
| `IMAGE_ROUTING_MODE` | `nano_all` | tiered image routing |
| `PREMIUM_IMAGE_MODEL` | `fal-ai/nano-banana/edit` | reference-conditioned model |
| `MAX_COST_PER_JOB` | `0.60` | per-comic fal spend cap |
| `MAX_PANELS_PER_COMIC` | `6` | hard panel cap |
| `NEW_USER_CREDITS` | `5` | starting credits |
| `CREDIT_PANEL_TIERS` | `2:1,4:2,6:3` | panel→credit pricing tiers |
| `CREDITS_AI_DEFAULT` | `2` | credits for AI-decided panel count |

---

## 10. Current state

**Done & verified:** full pipeline on Groq+fal; auth; Character Vault (Supabase +
SQLite); tiered credits; colour mode; panel-count selector (wizard + dashboard);
history/gallery; PDF export; Railway deploy prep (slim image container-tested);
per-request Supabase client caching.

**Pending:** the founder's Railway deploy (account + dashboard steps in `DEPLOY.md`),
a manual prod smoke test, and an optional real favicon. **Payments (Lemon Squeezy)
are deferred** until the beta validates.
```
