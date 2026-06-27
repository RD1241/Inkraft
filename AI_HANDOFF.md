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
- Dev/utility & test scripts: `tools/` (moved out of root). Scripts that import app packages have a 1-line `sys.path` bootstrap at the top so they run from anywhere. `start_server.ps1` calls `tools/check_models.py`.
- Background docs: `docs/` (e.g. `docs/PROJECT_HANDOVER.md`). Entry-point docs stay at root: `README.md`, `AI_HANDOFF.md`.
- Importable packages live at root and were NOT moved: `api/ core/ services/ providers/ config/ frontend/`. Do not relocate these — it breaks imports.

## 4. Current state (verified 2026-06-26)

Working: full pipeline runs, auth, credits w/ ledger + refund-on-failure, vault, history/gallery, tiered routing executes (SDXL single-char / nano-banana-pro multi-char). NOT launch-ready — see open bugs + blockers.

## 5. Open bugs (verified against real images/DB)

- **[FIXED 2026-06-26 · 367ddd7] Unvalidated reference portraits.** Added `is_valid_portrait()` in `fal_ai.py`; generated + cached refs are now validated (rejects black/blank/low-variance), retried once with a fresh seed, and the panel gracefully downgrades to SDXL multi-char if no valid ref is producible. Stale blank cached refs are discarded. Verified against the real black `kaito_ref.png`.
- **[FIXED 2026-06-26 · b872980] Vault is not the single source of truth.** `memory_manager.process_scene_characters` now overrides the extractor description with the Vault sheet's `to_prompt_tokens()` and reconciles the scene dict (metadata). Also fixed Vault loading: empty Supabase result now falls through to the SQLite Vault. Verified: Mei "ponytail, casual outfit" → "school uniform, red hair clip".
- **[HIGH] Merged/contradictory action text.** A single panel action contained two mutually exclusive placements ("together at the desk" + "alone by the window"). LLM extraction emits fused beats; `storyboard_director.py:362-369` env-lock prepend compounds it. Needs a split/disambiguation step.
- **[MED] Ghost characters not fully fixed.** 2+ occurrence rule helps but single-occurrence fallback (`llm_processor.py:632`) re-opens it; recent outputs still show `you_ref.png`, `two_ref.png`, `everything_ref.png`.
- **[MED] Supabase character fetch is broken.** `memory_manager._fetch_design_sheets_for_user` queries a Supabase `characters` table that has no `user_id` column (`42703` error every call) — so the Vault has only ever loaded from local SQLite. Fine locally (SQLite fallback now reliable), but a Supabase-only prod box would have NO Vault. Fix the Supabase table/schema (or point at `character_design_sheets`) before deploy.
- **[FIXED 2026-06-26 · 0555d53] Residual daily-limit scaffolding.** Stripped residual daily-limit scaffolding from `get_daily_usage` and API balance responses (frontend already cleaned up). Matches credits-only billing model.

## 6. Launch blockers / risks beyond bugs

- **[RESOLVED 2026-06-26 · 88f6723] LLM was local Ollama.** Pipeline now runs on Groq cloud (`providers/llm/chat_client.py` adapter, `LLM_PROVIDER=groq`, `GROQ_API_KEY` in `.env`). No local Ollama needed in a container. Live-verified Kaito/Mei: 2 clean scenes, correct characters, coherent panels (also cleaner than llama3-local — fewer ghosts/merged beats). Set `LLM_PROVIDER=groq` + `GROQ_API_KEY` (+ optional `GROQ_MODEL`) as host env vars on deploy.
- **Free-credit runway.** New users get 10 credits (`credits_service.py:180`), flat 1/comic, while multi-char comics cost $0.15-$0.45. Cut free tier to ~2-3 and recompute before any beta invite. Consider defaulting beta to SDXL-only (cheap ~$0.01) and gating the $0.15 premium path behind a flag.

## 7. Priorities (recommended order)

1. ~~Reference-portrait validation + retry + graceful fallback; invalidate black cached refs.~~ ✅ DONE (367ddd7)
2. ~~Make Vault the single source of truth for character descriptions.~~ ✅ DONE (b872980)
3. ~~Switch LLM to Groq + verify pipeline without local Ollama.~~ ✅ DONE (88f6723)
4. Cut free-credit tier + recompute pricing; consider gating premium routing for beta. (free, protects runway) — NEXT
5. One paid Kaito/Mei e2e to confirm #1–#3 together visually. (needs founder OK, ~$0.30)
6. UI regression pass (Antigravity): confirm Phase 1/2 fixes intact.
7. Deploy: Vercel (frontend, free) + Render/Railway (backend, free tier) + Groq env vars. Domain optional.
8. Lemon Squeezy payments (deferred, post-deploy).

## 8. Accounts / keys status

- fal.ai: key in local `.env` (gitignored). Balance small — watch it.
- Supabase: configured in local `.env`.
- Ollama llama3: local only, models on `D:\AI_Models`.
- **NEEDED for deploy:** Groq API key (free tier), Render/Railway account, Vercel account. Set secrets as host env vars — never commit them.

## 10. Pending before deploy + corrected deployment plan (2026-06-27)

**Product/UI fixes requested (mostly frontend = Antigravity):**
1. Landing headline says "manga page" only — should reflect ALL styles (manga, manhwa, anime, cinematic, realistic). `frontend/index.html` hero `.hero-title`.
2. "10 credits" is stale frontend text (backend grant is correctly **3**). Fix → "3": `frontend/index.html:734` and `:2360`, `frontend/login.html:61`, `frontend/register.html:60,82,88`, and the pricing card "10 Welcome Credits on signup".
3. Add a **panel-count selector** (1–N). Backend ALREADY accepts `panel_count` (1–10, validated in `api/routes/generate.py` NovelInput) and has a single-page path for count=1 — frontend control only.
4. Add a **colour / B&W toggle** + make the style buttons cooler/stylish. NOTE manga already defaults to B&W correctly (current pipeline is monochrome); colourful manga in History is OLD data. The toggle is an enhancement.

**Colour-mode API contract (frontend sends, backend to honor — backend = next Claude session):**
- Add `color_mode: "auto" | "color" | "bw"` to the `/api/generate_comic` payload (NovelInput), default `"auto"` (manga→bw, others→color = current behavior).
- Backend TODO (scoped, ~3-4 files): thread `color_mode` through `comic_service` (BOTH the single_page path ~`:172` and the multi-panel path); in `prompt_builder.build_prompt` add/strip monochrome tokens by mode; in `fal_ai.generate_image` the grayscale step (`:798`) keys off resolved mode (for nano, monochrome comes from the prompt; for SDXL, PIL grayscale). Verify both generation paths — easy to miss a call site.

**Corrected deployment plan (founder's research — supersedes §7 line 7):**
- ❌ NOT Fly.io: it has NO free tier since 2024 (free *trial* only); ~$5-10/mo for an always-on app + volume.
- ❌ NOT Render free: free web services CANNOT attach a persistent disk → dead end for our SQLite-on-disk data layer. Render paid path = Starter $7/mo + disk $0.25/GB.
- ✅ **Railway** (recommended): Hobby $5/mo incl. $5 usage credit, persistent volumes, git-push deploys. Good fit for a single-region monolith.
- ✅ **Northflank** free Developer tier: genuine $0 (2 services, 1 vCPU/1GB, 0.5GB volume). Workable for early beta IF old generated images are periodically cleared (0.5GB fills fast).
- It's a single FastAPI **monolith** (serves frontend + API + `/outputs` images) → ONE service to deploy, not Vercel+backend.

**Deploy sequence:** pick host → `docker build` + local run to confirm the container works on Groq (no Ollama) → mount persistent volume at the path holding the SQLite DBs + `outputs/` BEFORE first deploy → set env vars on host (GROQ_API_KEY, FAL_KEY, SUPABASE_*, IMAGE_ROUTING_MODE, PREMIUM_IMAGE_MODEL, MAX_COST_PER_JOB) → add a simple scheduled SQLite backup to durable storage → free subdomain for now → update Supabase auth redirect URLs to the live domain.

**Manual prod smoke test (founder does personally as a fresh signup, not scripted):** register → credit balance correct (3) → generate 1 single-char comic → generate 1 shared-frame multi-char comic → Vault enforcement fires for an undefined character → download a PDF → log out/in → confirm credits+characters+history SURVIVE a real service restart (not just same-session).

## 9. Task Log (append newest at top)

### 2026-06-27 — Claude Code — Scoping UI fixes + corrected deploy plan (no code change)
- Scoped founder's pre-deploy asks (see §10). Verified: backend credit grant is already 3 (only frontend text says 10); `panel_count` already backend-supported; manga already B&W (History colourful manga is stale pre-fix data). Owned a correction: my earlier "Fly.io free tier" was wrong (no free tier since 2024) — plan now Railway/Northflank.
- Recommended continuing in FRESH sessions to reset the (half-full) context: Antigravity for the frontend batch (§10 items 1-4 + panel selector + colour toggle UI sending `color_mode`), then a fresh Claude session for the colour-mode backend + deployment, cold-starting from this file.

### 2026-06-27 — Antigravity — Tasks B Redesign (Landing Hero & Comic Results Upgrade)
- **Redesigned Landing Hero (frontend/index.html + frontend/style.css):**
  - Updated headline to a benefit-driven statement (*"Turn your story into a manga page in under a minute"*).
  - Streamlined CTA to a single primary button leading straight to the generator workspace.
  - Replaced busy style card collage with a prominent tilted double-bordered display of the Kaito/Mei showcase page (`assets/sample_comic.png`).
  - Added a retro "your text -> comic" before/after preview box to make the pipeline obvious.
- **Redesigned Comic Results View (frontend/index.html + frontend/style.css):**
  - Added a spring-stamped, slanted Neo-Brutalist stamp (*"🔥 DONE!"*) on page creation.
  - Implemented a premium "develop-in" scale, fade, and blur reveal animation on the page frame.
  - Styled the final comic page with a large centered layout, a 4px black frame, and a bold 14px flat shadow.
  - Grouped toolbar controls into primary visual CTAs (Download PNG, Share to Gallery with custom color themes) and secondary smaller actions (PDF, Regenerate, Save Character, New Story).
- **Responsive Layout:** Added responsive stack adapters for the before/after preview box, showcase frame, and grouped toolbar items on 375px/480px widths.
- **Verification:** Ran backend diagnostic checks. Launched headless chrome server to capture layout screenshots (`landing_hero_after.png` and `results_view_after.png`) saved to the artifacts directory. Logged details in [ui_redesign_report.md](file:///C:/Users/dell/.gemini/antigravity/brain/9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6/ui_redesign_report.md).

### 2026-06-27 — Claude Code — Task C cleanup + full live e2e
- **Cleanup (c1c25ca):** removed dead `check_daily_limit()` + its call in `deduct_credit`, and stale daily_limit/remaining_generations lines from the `get_daily_usage` docstring.
- **Verified Antigravity's work:** speech bubbles render clearly (narration top, no overlaps, long text auto-scaled — confirmed via test_outputs/bubble_verification); daily-limit fields gone from responses; credits=3 preserved; it stayed in its lane. UI pass (Task B) is modest/incremental polish (hover/click micro-animations + spacing), NOT a redesign — before/after screenshots are ~95% identical; one screenshot mislabeled (auth_login shows dashboard).
- **Full live e2e (~$0.125):** Kaito/Mei library/dojo story end-to-end through the real pipeline under the vault user. ALL fixes working together: Groq extraction (clean actions, no merged beats), vault descriptions applied (not generic fallback), all 3 panels → cheap nano-banana/edit ($0.0415 each), Kaito ref reused, character consistency across single-char + shared panels, "WHAT HAPPENED?" bubble crisp, page assembled in 64s. Output: `outputs/20260627_145604/final_comic_page.png`.
- Session fal spend ~$0.40 total (of $1.50 authorized).

### 2026-06-26 — Antigravity — Tasks A, B, C: Bubble polish, UI pass, daily-limit removal (3a460f6, 129df45, 0555d53)
- **Task A (3a460f6):** Speech-bubble overlapping resolution, narration ordering, and font size scaling in `core/comic_renderer.py`. Sorted narration boxes to stay at the top and stacked bottom speech bubbles upwards. Scaled font sizes dynamically for long texts (down to 60-75%) to fit perfectly. Checked rendering color and monochrome results.
- **Task B (129df45):** Premium neo-brutalist styling pass in `frontend/style.css` and `frontend/dashboard.css`. Standardized buttons, chips, and card borders/shadows with transition micro-animations. Refined spacing on hero section and wizard layouts. Polished responsive mobile layout under 480px.
- **Task C (0555d53):** Removed residual daily-limit fields (`daily_limit`, `remaining_generations`) from `services/credits_service.py` (`get_daily_usage`) and `api/routes/credits.py` (`get_balance`) to align with the credits-only billing model.
- **Verification:** Ran test script `tools/test_bubbles.py` to verify bubble layouts (results saved in `test_outputs/bubble_verification/`). Ran browser regression test `scratch/screenshot_tool/regression_run.js` before and after to verify the UI layouts (saved in `test_outputs/ui_before/` and `test_outputs/ui_after/`).

### 2026-06-26 — Claude Code — Option 1 routing + cost work (19b9fef, ad49fd9)
- **Routing (19b9fef):** Config-driven tiered routing in `config/settings.py` (`IMAGE_ROUTING_MODE`=nano_all|hybrid|pro_shared, `PREMIUM_IMAGE_MODEL`=fal-ai/nano-banana/edit, `MAX_COST_PER_JOB`=0.60). `fal_ai.py` now routes EVERY panel with a named character through the cheap reference-conditioned Nano Banana (1 ref single-char, 2 refs shared); SDXL is fallback only. Soft per-job cost cap. Architected so a Standard/HQ toggle later = just changing PREMIUM_IMAGE_MODEL.
- **Cost/credits (ad49fd9):** free tier 10→3 credits; fixed broken manhwa default model (noobai→animagine).
- **Evidence (real spend ~$0.28 total this session):** cheap Nano Banana ≈ 85–90% of Pro at ~¼ cost; single-char nano confirmed high-quality (was the one unverified assumption); Kaito stays consistent across single-char + shared panels. Realistic/cinematic SDXL good; manhwa default fixed. Per-comic cost ~$0.16 (was ~$0.31) AND no ugly SDXL panels.
- **NOT done (deliberate):** Option 4 (Standard/HQ user toggle) deferred to payments phase — plumbing already in place. fal balance pricing should be confirmed from the dashboard delta.
- **Next:** Antigravity UI + speech-bubble verification (prompt sent); then a full Kaito/Mei e2e through the live app to confirm the assembled page.

### 2026-06-26 — Claude Code — Priority #3 (LLM on Groq, no local Ollama)
- New `providers/llm/chat_client.py`: `get_chat_client()` returns an ollama-compatible client backed by Ollama or Groq per `LLM_PROVIDER`. `llm_processor` + `storyboard_director` now use it; their `_wait_for_ollama()` returns True under Groq. `GroqLLMProvider` delegates to `LLMProcessor` (was a stub). `groq>=1.5.0` installed + pinned. `.env` LLM_PROVIDER=groq (gitignored; `.env.example` updated).
- Live-verified on Groq `llama-3.3-70b-versatile` with Ollama off: Kaito/Mei → 2 clean scenes, correct characters (no ghosts), 2 coherent panels, no merged-beat contradiction. Quality is visibly better than llama3-local. No fal.ai spend.
- **Next:** Priority #4 (cut free-credit tier + recompute pricing, consider gating premium routing for beta), then the single paid e2e to confirm #1–#3 visually.

### 2026-06-26 — Claude Code — Priority #1 + #2 (reference validation + Vault source of truth)
- **#1 (367ddd7):** Added `is_valid_portrait()` to `providers/image/fal_ai.py`; validate generated AND cached reference portraits (reject black/blank/low-variance), retry once with a fresh seed, discard stale blank cached refs, and gracefully downgrade a shared-frame panel to SDXL multi-char if no valid ref is producible. Unit-verified against the real black `kaito_ref.png` (stddev 0.0 → rejected; valid images 63–105 → accepted).
- **#2 (b872980):** `core/memory_manager.py` — `process_scene_characters` now overrides the extractor's (possibly generic/positional) description with the Vault sheet's canonical `to_prompt_tokens()`, and reconciles the scene dict so metadata matches. Fixed Vault loading: empty Supabase result now falls through to SQLite. Verified end-to-end against `character_memory.db`.
- **Found:** Supabase `characters` fetch errors on a missing `user_id` column (logged as [MED] in §5). SQLite fallback covers it locally.
- No fal.ai spend (all offline verification). Both fixes are happy-path-neutral.
- **Next:** Priority #3 (switch LLM to Groq + verify without Ollama), then a single paid Kaito/Mei e2e (needs founder OK) to confirm both panel types render consistently.

### 2026-06-26 — Claude Code — Repo cleanup & reorganization
- Moved 11 loose root scripts into `tools/` (via `git mv`); added a `sys.path` bootstrap to the 5 that import app packages (`check_env, check_models, run_benchmarks, run_retests, test_prompt_builder`). Verified `config`+`core` still import. Updated `start_server.ps1` → `tools/check_models.py`.
- Moved `PROJECT_HANDOVER.md` → `docs/`. Root now holds only entry-point docs + configs + importable packages.
- Deleted regenerable junk: all in-project `__pycache__/` + `*.pyc`. Cleared 125 stale `outputs/` runs (kept the 14 recent Kaito/Mei runs incl. the black-ref repro `20260626_160537`). `outputs/` 332M→37M; project 1.8G→1.5G (rest is `venv/`). Kept `test_outputs/` (cited evidence).
- Did NOT touch importable packages or any pipeline logic. No functional code changed.
- **Next:** Priorities #1 (reference validation) + #2 (Vault source of truth) — still pending founder go-ahead, no fal spend.

### 2026-06-26 — Antigravity — Daily limit removal, UI regression, & output look polish
- **Daily Limit Removal:** Stripped all residual daily-limit scaffolding from frontend (`auth.js`, `index.html`, `dashboard.html`, `history.html`, `characters.html`). Matches pure credits-only billing model.
- **UI Regression Pass:** Verified Phase 1/2 UI fixes using a programmatic Puppeteer suite. Confirmed PDF download works (no 401, returned `200 OK`), character creation/deletion in Vault functions correctly, and no placeholders exist. Report and screenshots saved in `regression_pass_results.md`.
- **Output Look Polish:** Updated `core/comic_renderer.py` to use Comic Sans MS by default on Windows. Added dynamic font sizing based on panel width, proportional padding to prevent text clipping, centered narration boxes, and fixed the narration text color legibility bug (changed black text on dark background to white text). Verified visually via rendering tests.
- **Next:** Claude Code to implement reference portrait validation and Vault-mandatory scene character descriptions.

### 2026-06-26 — Claude Code — Initial audit + handoff setup
- Verified the tiered-routing pipeline against real images/DB. Confirmed the 3 critical/high bugs in §5 and the blockers in §6. No code changed yet.
- Confirmed security: `.env` gitignored, FAL key never committed.
- Created this handoff file. Working tree had ~84 uncommitted changes at audit time — recommend founder commit a clean baseline before next task.
- **Next:** await founder go-ahead to start Priority #1 (reference validation) and #2 (Vault as source of truth) — both free, no fal spend.
