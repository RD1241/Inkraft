# Inkraft — AI Handoff & Progress Log

**Purpose:** This file is the shared brain between AI assistants (Claude Code + Antigravity) working on Inkraft, used one at a time. Private/tool memory does NOT transfer between tools — **this file does.** Read it fully at the start of a session; update the Task Log at the end of every task.

---

## 0. Rules for whoever is working (read first)

1. **Verify before you claim.** This project has a documented history of reports saying "done/working" while the real images showed broken output. Before reporting success: open the actual generated image, query the SQLite DB, or read the real code path. Never trust a prior description alone.
2. **Do not spend fal.ai credits without the founder's OK.** Balance is small (~$6.80 as of 2026-06-26). Reference/multi-char panels cost $0.15 each. A paid end-to-end test must be confirmed first.
3. **Commit after every task.** Leave the tree clean before handing off. Use a short branch if the change is risky. The next AI inherits your working tree.
4. **Keep this file current.** Append a Task Log entry (date, what changed, files, how verified, what's next). Keep entries short and concrete (file:line).
5. **Budget is tight (student, ~$10-15 max headroom).** Prefer free tiers and free fixes. Flag anything that costs money before doing it.

## 1. Division of labor (founder's plan)

- **Claude Code** → deep reasoning: architecture, core logic bugs, prompt/pipeline design, code structure, anything that needs careful tracing.
- **Antigravity** → UI work, broad testing, repetitive/mechanical edits, subagent fan-out tasks, anything that would burn the other tool's context on low-value work.
- Only one tool active at a time. Commit + update this file before switching.

## 2. What Inkraft is (1 paragraph)

Paste a story scene → system extracts characters & scenes (LLM) → plans a storyboard (camera/pacing) → generates panel art (fal.ai) → composites a final page with speech bubbles/SFX. 5 styles: manga, anime, manhwa, cinematic, realistic. Stack: FastAPI + vanilla JS + Supabase auth + local SQLite. App lives in `NovelToComic/` (not repo root). Repo: https://github.com/RD1241/Inkraft

## 3. Architecture map (where things live)

- Pipeline orchestration: `services/comic_service.py` (`process_job_worker`)
- LLM scene extraction: `core/llm_processor.py` (Ollama; rule-based fallback at :567)
- Storyboard planning: `core/storyboard_director.py` (Ollama)
- Prompt construction: `core/prompt_builder.py`
- Image generation + tiered routing: `providers/image/fal_ai.py`
- Provider selection: `providers/factory.py` (driven by `config/settings.py`, which force-sets `IMAGE_PROVIDER=fal_ai` when a real FAL_KEY exists — the `.env` value is ignored)
- Character Vault: `core/character_memory.db` table `character_design_sheets` (NOT in repo — `*.db` is gitignored)
- Credits/billing: `services/credits_service.py`, `services/billing_service.py`
- Character API: `api/routes/characters.py`; generation: `api/routes/generate.py`
- Frontend: `frontend/*.html` + vanilla JS, auth store in `frontend/auth.js`
- Run locally: `start_server.ps1` (kills/starts Ollama, then uvicorn on :8000)

## 4. Current state (verified 2026-06-26)

Working: full pipeline runs, auth, credits w/ ledger + refund-on-failure, vault, history/gallery, tiered routing executes (SDXL single-char / nano-banana-pro multi-char). NOT launch-ready — see open bugs + blockers.

## 5. Open bugs (verified against real images/DB)

- **[CRITICAL] Unvalidated reference portraits.** `fal_ai.py:457-471` caches/uses the SDXL reference portrait with no blank/black check (main panel path has one at :652). Confirmed: `outputs/20260626_160537/references/kaito_ref.png` = pure black, still used → Kaito looked like two different people. Cache (`<job>/references/`) is never invalidated, so a bad ref poisons future jobs.
- **[CRITICAL] Vault is not the single source of truth.** Scene character descriptions can come from positional generic fallbacks (`llm_processor.py:639-655`, e.g. char#2 female = "ponytail, casual outfit") instead of the Vault sheet (Mei's real entry: school uniform, long straight hair, red clip). Reference path uses Vault; panel prompt can use the fallback → same character described two ways in one comic.
- **[HIGH] Merged/contradictory action text.** A single panel action contained two mutually exclusive placements ("together at the desk" + "alone by the window"). LLM extraction emits fused beats; `storyboard_director.py:362-369` env-lock prepend compounds it. Needs a split/disambiguation step.
- **[MED] Ghost characters not fully fixed.** 2+ occurrence rule helps but single-occurrence fallback (`llm_processor.py:632`) re-opens it; recent outputs still show `you_ref.png`, `two_ref.png`, `everything_ref.png`.
- **[LOW] Residual daily-limit scaffolding.** `check_daily_limit` bypassed but `get_daily_usage` still returns `daily_limit:3` and frontend still tracks `ntc_daily_limit`.

## 6. Launch blockers / risks beyond bugs

- **LLM is local Ollama** (`127.0.0.1:11434`). Dockerfile has no Ollama → in a container EVERY comic falls to the crude rule-based extractor. Must switch `LLM_PROVIDER` to the existing `GroqLLMProvider` (free tier) before deploy, then re-verify quality through that path.
- **Free-credit runway.** New users get 10 credits (`credits_service.py:180`), flat 1/comic, while multi-char comics cost $0.15-$0.45. Cut free tier to ~2-3 and recompute before any beta invite. Consider defaulting beta to SDXL-only (cheap ~$0.01) and gating the $0.15 premium path behind a flag.

## 7. Priorities (recommended order)

1. Reference-portrait validation + retry + graceful fallback; invalidate black cached refs. (free)
2. Make Vault the single source of truth for character descriptions in prompt + reference paths. (free, biggest quality win)
3. Switch LLM to Groq + verify pipeline without local Ollama. (free)
4. Cut free-credit tier + recompute pricing; consider gating premium routing for beta. (free, protects runway)
5. One paid Kaito/Mei e2e to confirm both panel types look consistent. (needs founder OK, ~$0.30)
6. UI regression pass (Antigravity): confirm Phase 1/2 fixes intact.
7. Deploy: Vercel (frontend, free) + Render/Railway (backend, free tier) + Groq env vars. Domain optional.
8. Lemon Squeezy payments (deferred, post-deploy).

## 8. Accounts / keys status

- fal.ai: key in local `.env` (gitignored). Balance small — watch it.
- Supabase: configured in local `.env`.
- Ollama llama3: local only, models on `D:\AI_Models`.
- **NEEDED for deploy:** Groq API key (free tier), Render/Railway account, Vercel account. Set secrets as host env vars — never commit them.

## 9. Task Log (append newest at top)

### 2026-06-26 — Claude Code — Initial audit + handoff setup
- Verified the tiered-routing pipeline against real images/DB. Confirmed the 3 critical/high bugs in §5 and the blockers in §6. No code changed yet.
- Confirmed security: `.env` gitignored, FAL key never committed.
- Created this handoff file. Working tree had ~84 uncommitted changes at audit time — recommend founder commit a clean baseline before next task.
- **Next:** await founder go-ahead to start Priority #1 (reference validation) and #2 (Vault as source of truth) — both free, no fal spend.
