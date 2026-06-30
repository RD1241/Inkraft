# Inkraft — Project Walkthrough (updated 2026-06-30)

A current, end-to-end tour of what Inkraft is, how it works, and where everything
lives. For the day-to-day AI handoff log see `AI_HANDOFF.md`; for deploy steps see
`DEPLOY.md`.

> **Status:** LIVE on Railway → **https://inkraft-production.up.railway.app** .
> Core product works end-to-end (paid-verified). Pre-public checklist in §12.

---

## 1. What Inkraft is

Paste a story scene → Inkraft turns it into a finished comic page. It extracts the
characters and scene, plans a cinematic storyboard, generates the panel art, and
composites a final page with speech bubbles and SFX. Five art styles: **manga (B&W),
manhwa, anime, cinematic, realistic.**

It's a single **FastAPI monolith** that serves the web frontend, the API, and the
generated images — one service, no separate frontend host.

---

## 2. How a comic gets made (the pipeline)

`services/comic_service.py → process_job_worker` orchestrates it:

1. **Scene extraction** (`core/llm_processor.py`) — an LLM reads the story and pulls out
   characters, actions, and dialogue. Runs on **Groq cloud** (`LLM_PROVIDER=groq`). On a
   429/rate-limit it auto-falls back down a **model chain** (`GROQ_FALLBACK_MODELS`:
   llama-4-scout → gpt-oss-120b → llama-3.1-8b-instant — each has its own free daily
   token bucket) so extraction never degrades to the rule-based fallback. No Ollama in prod.
2. **Storyboard planning** (`core/storyboard_director.py`) — panel count, camera shots,
   pacing, lighting, emotion, and tension per panel. Emotion/combat token logic lives in
   `core/expression_engine.py`, `core/action_library.py`, `core/interaction_composer.py`
   (all word-boundary matched so e.g. "casting shadows" never injects "magic circle").
3. **Vault override** (`core/memory_manager.py`) — if a character has a saved Character
   Vault sheet, its canonical look REPLACES whatever the extractor guessed, so characters
   stay identical across panels and across comics.
4. **Prompt building** (`core/prompt_builder.py`) — assembles the layered image prompt
   (camera, emotion, character identity, lighting, action, style, optional art-direction)
   and applies the resolved **colour mode** (monochrome vs colour tokens). Uses a wide
   T5-era token budget tuned for FLUX.
5. **Image generation** (`providers/image/fal_ai.py`) — generates each panel on **fal.ai
   using FLUX dev** (`IMAGE_ROUTING_MODE=flux_all`, straight text-to-image). FLUX won a
   bake-off on prompt adherence + character consistency (via seed-lock + Vault identity
   tokens) and is cheaper than the old nano path. Character-less establishing panels are
   generated on a wider landscape canvas and centre-cropped to dodge FLUX's lone-figure
   bias.
6. **Composition** (`core/comic_renderer.py`, `core/panel_compositor.py`) — lays panels
   into a balanced grid and draws speech bubbles / SFX. The compositor biases toward
   well-proportioned grids (no cramped wide strips) and fits each panel **object-fit:cover**
   (preserve aspect, centre-crop) so art is never squished. Speech-bubble fonts resolve to
   a real TTF (DejaVu installed in the image) with a sized fallback, so dialogue is legible.

Two generation shapes: **single_page** (one tall page — used for manhwa) and
**panel_strip / grid** (multi-panel) — chosen by style/format/panel count.

---

## 3. Features

- **5 art styles** + **Auto-detect** from the text.
- **Panel count** selector (AI-decided, or 1–6) — Generate wizard + Dashboard quick-gen.
- **Colour mode** (`auto | color | bw`) — Auto = manga B&W, others colour; or force either.
- **Setting / Art-direction** — optional ≤300-char note that locks backdrop/era/mood into
  every panel (wizard + dashboard).
- **Character Vault** — save recurring characters once (look, outfit, features); they
  render identically everywhere. Supabase (`character_design_sheets`) + SQLite fallback.
  A rule-based **detect/enforcement** step prompts you to define 2+ named characters that
  aren't in your vault (and no longer false-flags common words like "Look"/"Then").
- **Credits & tiered pricing** — new users get **5 credits**; cost scales with size:
  **1–2 panels = 1, 3–4 = 2, 5–6 = 3** (AI-decided = 2). PDF export = 1 credit. Clear
  "Insufficient credits…" messaging when exhausted.
- **History & Gallery** — past comics per user; shareable public gallery.
- **PDF export** of a finished comic.
- **Beta feedback widget** — floating "💬 Feedback" button (rating + would-you-use +
  message) → `/api/feedback`, private to the team (`frontend/feedback.js`).
- **Auth** via Supabase.

---

## 4. Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI (Python 3.10), Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (`frontend/`) |
| LLM | Groq cloud (extraction + storyboard) — primary 70B + fallback chain |
| Images | fal.ai — **FLUX dev** (text-to-image) per style |
| Auth | Supabase |
| Data | SQLite (credits, jobs, history, vault, cache, metrics, feedback) + Supabase sync |
| Deploy | Docker → Railway (slim image, persistent `/data` volume) |

---

## 5. Where things live

```
api/            FastAPI app + routes (main.py; routes/generate, status, credits, history,
                gallery, download, auth, characters, feedback)
core/           pipeline brains: llm_processor, storyboard_director, prompt_builder,
                memory_manager, comic_renderer, panel_compositor, expression_engine,
                action_library, interaction_composer, *.db (gitignored)
services/       comic_service (orchestrator), credits_service, history/gallery/job/billing,
                backup_scheduler (in-app daily SQLite backup)
providers/      image/fal_ai.py, llm/ (groq, ollama, chat_client), auth/supabase_auth.py,
                storage/local.py, factory.py
config/         settings.py (all env-driven config)
frontend/       index.html (generate wizard), dashboard.html, login/register, characters
                (vault), history, gallery, style.css, app-shell.css, auth.js, feedback.js,
                assets/ (style-showcase images)
tools/          backup_sqlite, cost_report, trace_pipeline (free prompt tracer),
                test_action_tokens, check_models, ...
Dockerfile.railway, railway.json, requirements-railway.txt   (cloud deploy)
DEPLOY.md, WALKTHROUGH.md, AI_HANDOFF.md                       (docs)
```

---

## 6. Cost & credits model

- fal.ai cost ≈ **$0.025 per panel** (FLUX dev). A comic ≈ panels × $0.025 → ~$0.03
  (1 panel) to ~$0.15 (6 panels).
- Tiered credits keep free-tier spend bounded: **5 free credits ≈ ≤$0.45 worst-case/user.**
- Guardrails: `MAX_COST_PER_JOB` (per-comic cap), `MAX_PANELS_PER_COMIC` (hard panel cap),
  caching (identical prompts don't re-charge).
- The LLM cost is negligible (Groq free tier + fallback chain; ~fractions of a cent/comic).
- Monitor spend: `python tools/cost_report.py --balance <fal_balance>`.
- **There's no quality-neutral way to make FLUX dev cheaper** (FLUX schnell is ~8× cheaper
  but visibly worse). The real lever for production is payments — paying users fund their
  own generation; the free tier is capped so free users can't drain the balance.

---

## 7. Running locally

```
# from NovelToComic/
venv\Scripts\python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000
```

Requires a local `.env` (gitignored) with `FAL_KEY`, `GROQ_API_KEY`, `LLM_PROVIDER=groq`,
and the three `SUPABASE_*` keys. Locally the SQLite DBs live under `core/` and outputs
under `outputs/`. Free, no-fal-spend prompt tracing: `python tools/trace_pipeline.py
--style manga --panels 3 --text "..."`.

---

## 8. Deploying (summary)

Single service on **Railway** (already live). The slim `Dockerfile.railway` builds the
image (no torch/Ollama — runs on Groq + fal.ai) and installs `fonts-dejavu-core` for
legible speech bubbles. A persistent volume at `/data` (with `DATA_DIR=/data`) keeps all
SQLite DBs + generated images across restarts; an in-app daily backup writes
`/data/backups/`. Full step-by-step in **`DEPLOY.md`**.

---

## 9. Key config / env vars (`config/settings.py`)

| Var | Value (prod) | Purpose |
|---|---|---|
| `FAL_KEY` | *(secret)* | fal.ai image generation (auto-selects fal provider) |
| `GROQ_API_KEY` + `LLM_PROVIDER=groq` | *(secret)* / `groq` | LLM on Groq (no Ollama) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | primary extraction/storyboard model |
| `GROQ_FALLBACK_MODELS` | `meta-llama/llama-4-scout-17b-16e-instruct,openai/gpt-oss-120b,llama-3.1-8b-instant` | auto-fallback on 429 |
| `SUPABASE_URL/PUBLISHABLE_KEY/SECRET_KEY` | *(secret)* | auth + data sync |
| `DATA_DIR` | `/data` | persistent volume root (DBs + outputs + backups) |
| `IMAGE_ROUTING_MODE` | `flux_all` | every panel = FLUX dev text-to-image |
| `MAX_COST_PER_JOB` | `0.60` | per-comic fal spend cap |
| `MAX_PANELS_PER_COMIC` | `6` | hard panel cap |
| `NEW_USER_CREDITS` | `5` | starting credits |
| `CREDIT_PANEL_TIERS` | `2:1,4:2,6:3` | panel→credit pricing |
| `BACKUP_INTERVAL_HOURS` / `BACKUP_KEEP` | `24` / `7` | in-app SQLite backup cadence/retention |

---

## 10. Quality engineering (what makes the output good)

The hard-won lesson of this project: **the image model is rarely the problem — the
prompt/extraction is.** Most quality work happens before fal.ai is ever called, and is
traceable for free with `tools/trace_pipeline.py`. Notable systems:

- **Vault = source of truth** for character identity (overrides the extractor).
- **FLUX migration** for prompt adherence + native B&W manga.
- **Emotion/genre logic** (`expression_engine`): tension floors for action, genre-aware
  emotions, no "cowering" action heroes.
- **Word-boundary action/interaction matching** — combat/magic tokens only fire on the
  real verb (no "magic circle" on a chase).
- **Setting preservation** — keeps era/weather/lighting from the source for FLUX's T5.
- **Layout**: balanced-grid selection + object-fit:cover so panels are proportioned, never
  squished; dialogue rendered in a real bold font.
- **Establishing-shot handling** — character-less panels rendered wide + cropped so FLUX
  doesn't insert a stray figure.

---

## 11. Recent UI/UX (mobile + onboarding)

- Mobile audited at 375px: no horizontal overflow; the slide-out nav drawer's backdrop
  z-index was fixed so every nav link is tappable on all pages; the wizard's "story too
  short" error now clears as you type.
- Auto-cycling hero showcase (5 style cards) with fresh, current-pipeline sample images.
- Onboarding guide, tooltips, Vault explainer, and a Character-Vault discovery hint under
  the Generate button.

---

## 12. Current state & pre-public checklist

**Done & verified (live):** full pipeline on Groq + fal.ai (FLUX); Supabase auth + sync;
Character Vault with consistency override; tiered credits; colour mode; art-direction;
panel-count selector; balanced non-distorted multi-panel layout; legible dialogue;
history/gallery; PDF export; mobile nav/wizard fixes; Groq fallback chain; in-app SQLite
backup; private beta-feedback widget; Railway deploy on a persistent volume.

**Plan: soft-launch to a few real users → gather feedback → decide on public.** Remaining
founder-side steps before inviting real users / going public:

1. **Re-enable Supabase email verification** (currently OFF for testing) + set the Supabase
   Auth Site URL / redirect URLs to the live domain.
2. **Create the Supabase `feedback` table** (SQL in `api/routes/feedback.py`) to read
   reviews in the dashboard.
3. *(Optional)* one more controlled subagent QA run — cap the fal spend (~$2).
4. **Soft-launch** to ~5–15 real people in one niche on the free tier; watch usage + the
   feedback widget's "would you use it?" signal.
5. **If validated → payments (Lemon Squeezy) → public.** Payments make per-comic cost a
   non-issue (users fund their own generation).

**Known minor/open items:** a singly-named character in a 2-person romance/dialogue scene
can be dropped by the 2+-occurrence rule (existing tradeoff); more genre robustness sweeps
are always possible via the free tracer. Neither blocks a soft launch.
