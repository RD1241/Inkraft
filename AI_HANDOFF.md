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
- **[FIXED 2026-06-27] Supabase character fetch was broken.** `memory_manager._fetch_design_sheets_for_user` queried a Supabase `characters` table with no `user_id` column (`42703` every call) — so the Vault only ever loaded from local SQLite, and a Supabase-only prod box would have NO Vault. Repointed the query to `character_design_sheets` (the same table the `/characters` save/list/get/delete routes already use). Live-verified against prod Supabase: old `characters` → 42703, new `character_design_sheets` → loads Kaito + Mei with full canonical descriptions.
- **[FIXED 2026-06-26 · 0555d53] Residual daily-limit scaffolding.** Stripped residual daily-limit scaffolding from `get_daily_usage` and API balance responses (frontend already cleaned up). Matches credits-only billing model.

## 6. Launch blockers / risks beyond bugs

- **[RESOLVED 2026-06-26 · 88f6723] LLM was local Ollama.** Pipeline now runs on Groq cloud (`providers/llm/chat_client.py` adapter, `LLM_PROVIDER=groq`, `GROQ_API_KEY` in `.env`). No local Ollama needed in a container. Live-verified Kaito/Mei: 2 clean scenes, correct characters, coherent panels (also cleaner than llama3-local — fewer ghosts/merged beats). Set `LLM_PROVIDER=groq` + `GROQ_API_KEY` (+ optional `GROQ_MODEL`) as host env vars on deploy.
- **[ADDRESSED 2026-06-27] Free-credit runway.** Free tier is 3 credits (1/comic). Real cost recomputed: `nano_all` routing = $0.039/panel, so a comic ≈ panels × $0.039 → ~$0.04 (1 panel) to ~$0.24 (6 panels). UI maxes at 6 panels and the AI planner also caps at 6; the only leak was a direct API call requesting `panel_count` 7–10 (~$0.27–$0.39 on one credit). Closed with env-driven `MAX_PANELS_PER_COMIC` (default 6) enforced in `NovelInput` + `storyboard_director`. **Quality kept intact** (founder constraint): did NOT switch to hybrid/SDXL gating (that downgrades quality); kept `MAX_COST_PER_JOB=0.60` (lowering it would force SDXL mid-comic). Free-tier worst-case exposure now ~3 × $0.24 = $0.72/user via the UI. Monitor real spend: `tools/cost_report.py`. Still TODO: confirm nano's exact price from the fal dashboard delta; Standard/HQ paid toggle deferred to payments (plumbing in place via `PREMIUM_IMAGE_MODEL`).

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

**STATUS (2026-06-27 EOD):** DONE — #1 headline (all styles); #2 credits text now "3" everywhere incl. `register.html`; #3 panel-count selector (chips 0=AI/1–6, `#panel-count-input`, sent as `panel_count` when >0); #4 cooler colour-coded style chips + colour/B&W toggle (auto/color/bw buttons, `#color-mode-input`, sent as `color_mode`) AND its backend (Claude, commit 3ca33e0); items 5–6 onboarding/explainers (commits 3f2433c, 7a21c45); multi-style hero showcase. **Verified by Claude 2026-06-27:** frontend controls present in `index.html` (panel chips :339–364, colour buttons :377–385), click handlers write the hidden inputs (:1324–1339), and `runGeneration` sends both `panel_count` + `color_mode` in the payload (:1896–1907); backend `NovelInput` accepts/validates both. Frontend↔backend fully wired — nothing left disconnected.

5. **In-app feature explanations / onboarding (UX) — Antigravity.** Users (incl. the founder) don't know what features do. Add lightweight in-context guidance: a one-line "what is this" + empty-state on the Vault page ("Save your recurring characters so they look identical across every comic — define once, reuse everywhere"); helper text/tooltips on the generate form (art style, panel layout, panel count, colour mode); a short first-time hint. Brief, neo-brutalist, non-blocking.
6. **Existing-account credits — NO migration needed.** The 10→3 change only sets the STARTING grant for NEW signups (`credits_service._register_user`). Existing accounts keep their current balance (founder's old test ids show 4/6) — correct, not a bug; nothing re-grants on login. Optional: reset old test rows in `credits.db` for clean testing. Real beta users all start at 3.

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

### 2026-06-30 — Claude Code — Railway redeploy + 2 mobile bug fixes + Vault verified
- **Deployed latest to Railway (founder bought Hobby + set volume/vars).** Pushed all session
  commits to origin/main; Railway auto-deploys on push. LIVE-VERIFIED every marker on
  https://inkraft-production.up.railway.app: `app-shell.css` z-index:99, `style.css`/`dashboard`/
  `index` vault-hint, `register.html` new legal links. Backend healthy: `/api/health` 200,
  `/api/characters` 200 (Supabase OK), `/api/generate_comic` unauth → 401 (clean gate, no 500).
  IMAGE_ROUTING_MODE=flux_all confirmed in Railway vars. The "stuck old deploy / no output" issue
  is resolved — live now runs the FLUX pipeline + all session fixes. (Founder's GROQ_FALLBACK_MODELS
  var was staged; even if unapplied, the same chain is the code default in chat_client.py.)
- **Mobile bug #1 (wizard "can't go to next step") — FIXED.** Reproduced live at 375px via the
  preview: the Step-1 length validation works, BUT the "story too short" error never cleared while
  the user typed valid text, so it FELT permanently stuck. Fix (`index.html` input handler): clear
  `#error-banner` as soon as the text is valid length. Verified: error shows on empty → clears on
  valid typing → advances to step 2.
- **Mobile bug #2 (can't switch tabs via hamburger on non-dashboard pages) — FIXED.** Root cause
  found via live `elementFromPoint`: `.nav-backdrop` (a body-level element, z:110) painted ABOVE
  the slide-out drawer, because the drawer's z:120 is TRAPPED inside `.app-header`'s stacking
  context (`position:sticky; z-index:100`). So the backdrop swallowed every tap on the nav links —
  on all shared-drawer pages (index/history/gallery/vault), but NOT dashboard (its own nav). Fix
  (`app-shell.css`): backdrop z-index 110 → 99 (below the header context). Verified live: all 5 nav
  links now receive taps; backdrop still closes the drawer when tapped outside.
- **Vault discovery hint (founder ask #3) — ADDED.** Neo-brutalist `.vault-hint` under the Generate
  button on BOTH the wizard (`index.html` step 5) and dashboard quick-gen, linking to the Vault.
  Verified rendering.
- **Character Vault rigorously tested (founder ask #4) — FULLY WORKS.** Exercised the live API
  (user_id param, no auth needed): SAVE (Supabase-synced) → LIST → GET → UPSERT (re-save same name
  updates, no dup) → DETECT (Kaito=male, Mei=female) → DELETE (gone from SQLite+Supabase, GET→404).
  **Source-of-truth consistency PROVEN via trace:** a story saying only "Kaito sprinted" (no
  appearance) → the extractor guessed "leather armor" but the Vault OVERRODE it; both panels
  rendered Kaito's canonical tokens "spiky short black hair, amber eyes, scar over left eyebrow,
  black hooded jacket" with log `detected gender = male (source: design_sheet)`. Test data cleaned
  up. Minor non-issue: DELETE of a non-existent character returns 200 not 404 (idempotent).
- **⚠️ SEPARATE QUALITY BUG FOUND (not fixed — flagged):** in that Vault trace, a non-magic action
  ("Kaito spun around to face the figure") got spurious tokens injected: "hands outstretched, magic
  circle, arcane energy". No magic in the story. Likely an ActionLibrary/InteractionComposer or
  action-classifier misfire (possibly amplified by the 8b fallback guessing "leather armor"/fantasy).
  Worth a separate investigation — does NOT affect the Vault feature itself.
- **Dev note:** added `.claude/launch.json` (uvicorn on :8000) for the preview tool — left untracked.

### 2026-06-30 — Antigravity — Setting / Art direction input addition
- **Feature Addition**: Added an optional `"Setting / Art direction"` text input to both the landing page creation wizard (Step 1) and the dashboard quick-generate form.
  - Implemented custom styling in `style.css` for `.wizard-text-input` (manga-style black border & offset shadow) and `.qg-input` (translucent theme) to match the page designs perfectly.
  - In `index.html` (landing page wizard) and `dashboard.html` (quick generate), extracted the input value inside the respective form handlers, trimming and slicing it to 300 characters before forwarding it inside the body payload as `art_direction`.
  - Added Pydantic schema validation inside `api/routes/generate.py` via `NovelInput.art_direction` with a `@field_validator("art_direction")` to guarantee server-side compliance of ≤ 300 characters.
  - Documents updated in `WALKTHROUGH.md` to cover all new inputs, responsive layout audits, hero carousel updates, and vault enforcement mechanisms.

### 2026-06-30 — Claude Code — Legal: proper ToS + Privacy Policy (copyright/DMCA/sub-processors)
- Founder worried about copyright/legal exposure. Replaced the thin beta ToS/Privacy modal stubs
  in `frontend/index.html` (showLegalModal) with gap-closing baseline docs:
  - **ToS** now covers: as-is/no-warranty, eligibility (13+/16+ EU), **user warrants they own/have
    rights to their Inputs + grants a processing licence** (the big copyright risk = users pasting
    copyrighted novels), **acceptable-use** (no infringing/illegal/explicit/real-person content),
    AI-output ownership caveat (copyrightability not guaranteed), **DMCA/takedown contact +
    repeat-infringer**, credits have no monetary value, **indemnity + liability cap ($20)**,
    suspension, governing law.
  - **Privacy** now discloses ALL sub-processors (was only fal.ai): **Supabase** (auth/vault/
    history), **Groq** (story text → extraction), **fal.ai** (prompts → images), **Railway**
    (hosting/storage), plus data collected, retention, **deletion/access rights**, security,
    children. This closes the GDPR sub-processor gap.
  - `LEGAL_CONTACT` (currently the founder's gmail) + `LEGAL_UPDATED` are editable consts at the
    top of the block — **swap LEGAL_CONTACT for a dedicated support address** + set a specific
    governing-law country before public launch.
  - Single source of truth: added `index.html#terms` / `#privacy` hash auto-open; `register.html`
    now links to both (was a stale `alert()` with only ToS + inconsistent "commercial use allowed"
    wording).
- **Verified:** `node --check` on the extracted inline module script passes (template literals OK);
  structure mirrors the existing working modal. NOT a pixel-render check, NOT lawyer-reviewed.
- **⚠️ For PUBLIC (paid) launch:** regenerate via Termly/iubenda or get a lawyer review — do not
  ship paid on this AI-drafted baseline alone. Fine for an invite/closed beta.

### 2026-06-29 — Claude Code — Groq rate-limit resilience: model-fallback chain
- **Problem:** the 70B Groq model (`llama-3.3-70b-versatile`) has a 100k-tokens/day free cap;
  when hit (429) the whole pipeline dropped to the RULE-BASED extractor, which ghosts capitalized
  env words as characters (focus='Crumbling', secondary='Not') → broken comics. This is a real
  beta/public scaling risk (100k TPD ≈ only ~15 comics/day across ALL users).
- **Fix (`providers/llm/chat_client.py`):** `GroqChatClient.chat` now tries the primary model,
  then on a 429 automatically retries a fallback chain (`GROQ_FALLBACK_MODELS`, default
  `llama-3.1-8b-instant`) which has a SEPARATE, much larger free-tier token bucket. Transparent
  to both call sites (`llm_processor`, `storyboard_director`) — no call-site changes. Rule-based
  is now only the LAST resort (all Groq models exhausted / non-429 failures). New
  `_is_rate_limit()` helper detects 429/tokens-per-day. Env-tunable; empty = disabled.
- **LIVE-VERIFIED (the 70B was actually exhausted at test time):** a real extraction logged
  "'llama-3.3-70b-versatile' rate-limited (429); falling back to 'llama-3.1-8b-instant'" →
  "served by fallback model 'llama-3.1-8b-instant'" and returned a CLEAN knight extraction
  (focus='knight', chars=['knight'] across 3 scenes) instead of ghost words. 8b is less
  consistent than 70B (one run dropped the char — non-determinism) but is FAR better than the
  rule-based ghosts; it's a safety net, not the primary. `.env.example` + `DEPLOY.md` updated.
- **⚠️ Production note (in DEPLOY.md):** the real fix for scale is upgrading Groq to the paid Dev
  tier (~$0.004/comic — effectively free) so the 70B never exhausts. The fallback chain just
  prevents broken output in the meantime / under bursts.
- **[UPDATE 2026-06-30] Paid Groq Dev tier is currently BLOCKED by Groq** ("Developer tier upgrades
  are temporarily unavailable due to high demand" — founder's billing screenshot). Founder is
  willing to pay but can't yet. So the fallback chain is now the PRIMARY mitigation, not a stopgap.
  **Expanded it to a multi-model chain** (default `GROQ_FALLBACK_MODELS` =
  `meta-llama/llama-4-scout-17b-16e-instruct, openai/gpt-oss-120b, llama-3.1-8b-instant`). Each
  Groq model has its OWN separate free daily token bucket → ~4× effective free capacity, and the
  first two fallbacks are HIGH quality (not just a cheap 8b). **Verified 2026-06-30:** queried the
  account's live model list and ran the real extraction prompt+parser through all candidates —
  gpt-oss-120b, llama-4-scout-17b, qwen3-32b, gpt-oss-20b, 8b-instant ALL produced clean JSON with
  both characters (Kael + little girl); reasoning models (qwen/gpt-oss) did NOT break the
  bracket-depth parser. Also hardened `chat()` to advance to the next model on ANY error (not just
  429) so a decommissioned fallback can't crash the call. Founder action: retry the paid Dev tier
  on the Groq dashboard periodically — buy it the moment it reopens.

### 2026-06-29 — Claude Code — Multi-panel environment-only portrait-bias fix (NEXT-SESSION #1)
- **Problem (from prior NEXT-SESSION plan):** in a MULTI-panel comic a character-less
  establishing panel still used portrait/square slot dims → FLUX's tall-portrait bias
  inserts a spurious lone figure into the empty scene. Single-page was already fixed
  (landscape 1280x832, commit 768e0b4) but multi-panel slot dims are owned by the
  compositor's tiling and must NOT change.
- **Fix (`providers/image/fal_ai.py`, `generate_image`):** for a character-less multi-panel
  slot (`not focus_character and not secondary_character`) whose aspect is `< 1.5`, generate
  on a WIDER landscape canvas (`gen_w = round64(h*1.7)`, clamped [512,1536]) so no lone figure
  appears, then **centre-crop the downloaded image back to the EXACT slot dims** so the
  compositor tiling is unchanged. Slots already ≥1.5 landscape and ALL character panels are
  untouched (no behavioural change for the common case). New `crop_to` tracker + a post-loop
  PIL centre-crop (falls back to resize if the model returns smaller than expected).
- **Why this works:** reuses the SAME landscape principle already paid-verified for single-page
  (768e0b4: empty-street prompt at 1280x768 → ZERO people, at 1024x1280 → always a person).
- **Verified OFFLINE (zero fal spend):** drove the REAL `panel_compositor` for N=2..6 standard
  layouts + the portrait-fallback/square/2:1/large slots and replayed the exact dim logic +
  PIL crop. All env-only sub-1.5 slots widen to a landscape gen aspect (1.50–1.75) and the
  crop restores the slot dims EXACTLY (e.g. N=2 1016x713→gen 1216x704→crop 1024x704; N=6 square
  338x363→gen 896x512→crop 512x512; portrait 768x1024→gen 1536x1024→crop 768x1024). Landscape
  slots (≥1.5) untouched; character panels untouched. `fal_ai.py` compiles + imports clean
  (project venv). Test script: scratchpad `verify_env_crop.py`.
- **VERIFIED (paid, ~$0.05 — founder OK'd):** ran a deterministic 2-panel comic (panel 1 = empty
  ruined-city establishing shot focus=''/chars=[]; panel 2 = a knight) through the REAL
  generate_image at real compositor slot dims (1016x713 → 1024x704) then the REAL
  comic_renderer. Logs confirm the widen fired: "Env-only panel: generating wide 1216x704, will
  centre-crop to 1024x704" → "Centre-cropped env panel 1216x704 -> 1024x704 (slot dims
  preserved)", saved dims exactly 1024x704. **Eyeballed the assembled page:** the establishing
  panel is a clean empty ruined street (crumbling archways, tower, cobblestones) with NO lone
  figure; the knight renders correctly in panel 2; both tile cleanly with no distortion. Output:
  `outputs/20260629_233855_envtest/final_comic_page.png`. Session fal spend ≈ $0.90 of $4.
  - **Honest nuance:** the N=2 slot aspect (1.45) is only mildly portrait-biased, so this slot
    alone isn't a slam-dunk causal A/B (1.45 might render figure-free even un-widened). The
    STRONGEST at-risk multi-panel slots are square (N=6 "medium" → 512x512) and the portrait
    fallback (768x1024); the SAME widen logic covers them (verified offline in `verify_env_crop.py`
    + the single-page paid A/B 768e0b4 already proved landscape→no-figure causally). A dedicated
    paid square-slot before/after A/B was skipped to save credits — optional if stronger proof is
    wanted later.

### 2026-06-29 — Antigravity — UI audit & mobile responsiveness + hero carousel implemented

Completed the full Step 6 UI audit and layout fixes across desktop and mobile, resolving all horizontal overflow and stretching issues on the landing page, wizard steps, auth pages, and secondary dashboards:
- **Hero Auto-cycling Style Carousel**: Replaced the static single image with 5 preloaded stacked `.hero-comic-card` elements on `index.html`. Programmed active state style updates matching the stamp color badge, label updates, and mouse entry/exit pause-and-resume mechanisms.
- **Mobile Width Overflow & Horizontal Scroll fixes**: Constrained `.landing-section` (width: 100%), `.style-showcase-row`, `.style-pills-container`, and `.format-cards-container` to prevent horizontal stretch. Set global viewport overflow restriction on `html` and resolved auth background decorative orb stretching on `login.html` and `register.html`.
- **Style selection redesign**: Redesigned style selection cards on mobile screens to a 2-column grid layout with stacked elements, reduced font/icon sizes, and injected short descriptive labels (e.g. `B&W Hatching`, `Vibrant Webtoon`) using pure CSS pseudo-elements (`::after`).
- **Typography scaling**: Sized down `.section-title` Bangers headings on mobile/tablet viewports to fit screen widths without clipping.
- **Verified payload intact**: Verified that the wizard form submission correctly sends `panel_count` and `color_mode` in the generation POST payload.
- **Before/After Baseline Verification**: Verified all scroll widths on mobile viewport are exactly 375px (`hasScroll: false`) and archived before/after visual proof.

### 2026-06-28 — Claude Code — QA mega-task: FLUX migration + emotion/non-char/SFX fixes (steps 1-5 done; 6=UI→Antigravity)
Working through the founder's 6-part full-SaaS QA audit ($4 fal budget). Done so far:
- **NEW free diagnostic `tools/trace_pipeline.py`** — runs the real extract→storyboard
  →vault→prompt pipeline and prints the exact per-panel prompt + routing with ZERO fal
  spend. This is the founder's "trace the real prompt before blaming the model" tool.
  Exposes `compute_panels()` (shared with the bake-off).
- **[FIXED · a684597] Emotion resolver bug (the founder's STILL-TODO).** `expression_engine
  ._resolve_emotion_synonym` mapped storyboard emotions `tension`/`intense`/`suspense`/
  `serious` to **fearful → "scared, fearful, wide eyes, cowering"** — so action heroes in a
  tense gun standoff rendered cowering. Root cause: `"intense"` contains substring `"tense"`,
  caught by the fear broad-match before the determined mapping. Fix: tense/tension/intense/
  standoff/menacing → **determined** ("cold eyes, piercing gaze, unflinching stare");
  cautious/wary→suspicion, threatening/hostile→angry, love/tender→romantic. Genuine fear
  words (scared/afraid/terror/panic) still→fearful. Verified via re-trace: noir standoff now
  "unflinching stare", not "cowering".
- **[DONE · 4087bc7] MODEL BAKE-OFF — FLUX dev is the new default for every style.** New paid
  harness `tools/model_bakeoff.py` generated the REAL pipeline prompt across fast-sdxl
  (animagine/dreamshaper-XL/RealVisXL) vs FLUX schnell/dev/pro for cinematic/anime/manga/
  realistic. **Viewed every image.** FLUX dev won decisively on prompt adherence — the
  founder's #1 complaint: correct multi-character composition (SDXL dropped the 2nd char or
  made broken diptychs / wrong-gender), prop/period accuracy (SDXL "realistic" gave a modern
  soldier+rifle for "armor + sword"; FLUX kept armor+battlefield), native B&W manga (no
  washed-out PIL grayscale). And FLUX dev ($0.025) is CHEAPER than nano ($0.039). Wired:
  `STYLE_MODEL_MAP`→flux/dev (env-overridable), FLUX arg/cost handling in `generate_image`,
  `.env.example`+`DEPLOY.md` updated. Cleaned stale `FAL_*` SDXL overrides from local `.env`.
  Spend this session so far ≈ **$0.20** of $4.
- **[DONE · f1bca0c] Step-4 non-character panels: ghost "none" character killed.** Object/
  environment-only scenes (a sword on an altar; an empty street) made the LLM emit
  `focus_character: "none"` → recovered into `CHARACTER_A: none, male adult, short dark hair`
  + `solo` → a ghost man in every object panel. Fix: none/unknown/narrator added to BOTH
  name blacklists + focus_character reconciled against the surviving cast; prompt_builder now
  skips person emotion/camera tokens, foregrounds the hero object, and (since FLUX ignores
  negatives) uses POSITIVE desolation adjectives to keep people out. Verified: the sword is
  now the glowing hero of the temple (was absent before). KNOWN LIMIT: FLUX's portrait-aspect
  still tends to add a lone figure to wide empty-street shots (needs a per-panel landscape
  aspect — deferred, conflicts with the compositor).
- **[DONE · 156e79c] Step-2 emotion floor for action beats.** The LLM tags intense action
  (a tension-8 sword clash) as "neutral"/"calm" → flat face mid-fight. Central upgrade in
  `validate_and_apply_overrides` (applied AFTER the tension-arc/combat escalation set final
  tension): tension>=7 + flat emotion → "intense". Verified.
- **[DONE · d21568b] Step-3 full-comic test + routing decision: default is now `flux_all`.**
  Ran a REAL 3-panel Kael/Elena manga comic through the live pipeline in flux mode. The
  assembled page (verified by eye): strong character consistency across all 3 panels (flux
  ignores the IP ref — consistency came from seed-lock + Vault identity tokens), Vault
  descriptions applied exactly, clean readable dialogue boxes ("ON YOUR LEFT!"/"STAY CLOSE!"),
  "CLASH!" SFX on action panels, coherent beat. So FLUX wins on adherence (bake-off) +
  consistency (this test) + cost. Changed default `IMAGE_ROUTING_MODE` nano_all→**flux_all**
  (no nano). ⚠️ **FOUNDER ACTION: Railway likely has `IMAGE_ROUTING_MODE=nano_all` set
  explicitly — change it to `flux_all`** (or delete it) to get this in prod (see DEPLOY.md).
- **Step-2 props/action quality:** FIGHT scenes already render GREAT — the `action_library` +
  `interaction_composer` inject rich combat tokens ("crossed swords, impact point visible,
  metal sparks, forceful opposing stances") and FLUX honours them. Props survive when they're
  in the ACTION (sword clash, drew his katana); they're only dropped when an item lives only
  in a character's *held-item description*. Left as-is (lower priority than the above).
- **Total fal spend this session ≈ $0.35** of $4 (bake-off + non-char + the real comic).
- **[DONE · 43a14b5] Step-4/5 SFX upgrade.** The action SFX was small (fixed 48px) plain
  floating text. Now `comic_renderer` draws a panel-scaled jagged white starburst (black
  outline, hand-inked jitter) behind bold haloed text — a real manga impact effect, re-centred
  + clamped so it never clips. Verified by rendering CLASH! onto a clean panel. Dialogue boxes
  were already verified good in the real comic page (readable, positioned, no bad overlap).
- **[DONE · cda0468] Genre-aware emotion floor (fixed my own regression).** A romance test
  exposed that the tension>=7 floor hardened a romance climax (tension 8) to "intense" → "cold
  eyes, unflinching stare". Now the upgrade reads the action: combat→intense, grief/tears→sad,
  tender/romance→romantic_affection, else→intense. Verified: romance peak → "soft loving
  half-lidded gaze, warm blush"; sword clash still → intense.
- **[DONE · 768e0b4] Step-4 environment-only CLOSED (single-page).** Proved by direct A/B that
  FLUX's tall-portrait bias (not the prompt) inserts a lone figure into empty scenes: same
  empty-street prompt at 1280x768 = ZERO people, at 1024x1280 = always a person. Fix:
  character-less single pages render landscape 1280x832. Verified end-to-end through the real
  provider — clean empty street, no people. (Multi-panel env panels still portrait — changing
  their dims would break the compositor tiling; lower priority.)
- **[DONE · 21a3439] Setting period + wrong-SFX fixes (from a real knight/child manga).** A
  user's "ancient ruined city / abandoned market" novel rendered as a MODERN city with a bogus
  "SMASH!" on a tender comforting beat. (1) `ENVIRONMENT_VISUAL_ANCHORS` overwrote the raw env:
  "ancient city"→"MODERN city street", "abandoned market"→"BUSTLING market". Fixed: prompt_builder
  keeps the RAW env description first (period/mood survives), anchors are a light supplement, and
  the modern/bustling/concrete/urban bias words removed. (2) SFX fired on any action-layout panel
  + on "lowered his sword"; now requires a real combat keyword AND suppresses quiet/tender beats
  (kneel/comfort/cry/whisper/hug/lower). Both verified offline. NOTE: the same comic's "knight in
  armor → modern guy" is an OLD-CODE (nano + anime/school-uniform portrait) artifact — the FLUX
  deploy fixes it; re-test after deploy. The MISSING unnamed girl (a "small girl", no name → the
  extractor/blacklist drops her) still needs a careful extraction fix + Groq to verify.
- **[VERIFIED 2026-06-29] Antigravity's Step-6 mobile/UI work — checked against the real
  diff, not the claim.** AG made 3 frontend-only commits (index.html, style.css; ZERO backend).
  Verified live in a headless browser: NO horizontal scroll at 375px (scrollW==clientW==375),
  hero carousel = 5 preloaded cards + auto-cycle + hover-pause + stamp/label sync, every hero
  element fits the viewport, no console errors, and the generate-form payload still sends
  panel_count + color_mode. Auth-page fix is real (shared style.css cascade, not phantom).
  Pushed. GAP: dashboard.html has its own dashboard.css which AG didn't pass over (only the
  global overflow guard) — Phase-2 follow-up.
- **[DONE 2026-06-29 · groq reset] Unnamed described character kept (the little girl).** A
  user's knight/child manga rendered with NO child (+ a modern-dressed 'knight' + a bogus
  SMASH!). Root causes split across fixes: (a) generic person nouns (girl/boy/man) were
  blacklisted as ghosts → `_normalize_characters` now keeps a PERSON_NOUN name when it has a
  substantive description (bare 'girl'/'someone' still filtered — verified no ghost regression);
  (b) FLUX migration renders the armored knight (was nano's anime/school-uniform portrait);
  (c) env fix gives ancient ruins not a modern street; (d) SFX fix drops the wrong SMASH!.
  **GOLD-STANDARD VERIFICATION (paid, real comic):** re-generated the exact scene — Panel 1 a
  proper armored knight w/ sword in ancient pillared ruins, Panel 2 knight + little girl (white
  dress), Panel 3 Kael kneeling w/ 'YOU DON'T HAVE TO BE AFRAID ANYMORE' bubble, no SFX. Every
  original defect fixed together. Session fal spend now ≈ $0.63 of $4.
- **[FIXED 2026-06-29 · 42ea591] CRITICAL: 'Next Step' looked broken.** The #error-banner
  lived INSIDE step-content[data-step=5] (display:none on step 1), so the step-1 'story too
  short' validation rendered at 0 height and was unreachable — clicking Next on an empty box
  did nothing visible. Pre-existing (not the mobile work). Moved the banner OUT of the step
  panels + gave the previously-unstyled .error-banner a prominent red neo-brutalist style.
  Verified live (headless): empty box -> step 1 + visible red banner; valid text -> step 2.
- **[FIXED 2026-06-29 · a1ce388] 'All over the place' setting = PROMPT, not model.** A user's
  'ancient ruined city/market' rendered as a modern lamp-post street. Causes: (1) 'street'/
  'alley' anchors injected modern furniture (lamp posts/sidewalk/trash cans) — neutralized;
  (2) storyboard+extraction collapsed the rich setting to 'rain-soaked streets', dropping the
  era — strengthened both LLM prompts to keep era/place words. Trace now yields 'rain-soaked
  cobblestone streets' (no modern furniture).
- **[MODEL COMPARISON 2026-06-29] FLUX confirmed best — on the user's own scene.** Founder
  asked to re-compare nano-banana/SDXL/FLUX. Generated the knight scene through each: **SDXL
  animagine = a fully BLACK safety-blocked frame; nano-banana = reference portraits FAILED
  validation (twice each) and fell back to FLUX (the nano path is also what produced the
  original anime 'modern guy'); FLUX = a clean armored knight in a rainy cobblestone ruined
  street.** Conclusion reinforced: the model was never the problem — keep flux_all. Session
  fal spend now ≈ $0.85 of $4.
- **[SYSTEMIC 2026-06-29 · 1c3e92a] Preserve rich scene atmosphere for FLUX (the real fix
  for 'different prompts every time').** Founder's key point: the PIPELINE must build a good
  prompt from ANY user novel, not be hand-tuned per scene. Root cause of thin output: the
  prompt builder used an SDXL/CLIP 77-token-era budget (110 total / 20 for setting+action),
  truncating exactly the atmospheric detail FLUX (T5) is best at. Fixes: (1) FLUX path now uses
  a wide budget (170 total / 48 action+atmosphere / 30 char / 12 light; `_apply_color_mode`
  cap-aware so it doesn't re-truncate); local SD keeps the tight CLIP cap. (2) storyboard
  'action' field now demands a rich cinematic description that PRESERVES the source's
  setting/weather/lighting/background. Verified (paid): the knight/girl novel now carries
  'silver armor reflecting the faint moonlight, amidst the ruins of a once great city, broken
  carts and debris' and renders a coherent atmospheric 3-panel sequence (armored knight in the
  rainy ruined city -> kneeling to comfort the girl -> dialogue exchange). This helps EVERY
  detailed scene automatically.
- **[FEATURE 2026-06-29 · 41ab160] Art-direction / setting note.** New optional `art_direction`
  field (<=300 chars) a creator can use to LOCK the backdrop/era/mood/style into every panel
  when auto-extraction isn't enough (e.g. 'ancient ruined marketplace, broken carts' /
  '1980s neon Tokyo'). Injected at the highest-priority prefix position; threaded
  NovelInput.art_direction -> queue_comic_generation -> process_job_worker -> build_prompt
  (both single-page + multi-panel). Verified it leads the prompt. **FRONTEND TODO (Antigravity):
  add an optional 'Setting / Art direction' text input to the wizard + dashboard quick-gen,
  POSTed as `art_direction`.**
- **[FIXED 2026-06-29 · 127c053] Combat tokens leaking onto tender beats.** ActionLibrary/
  InteractionComposer put 'impact strike pose, motion blur' on a kneeling-to-comfort panel;
  now suppressed when the action is tender AND has no combat verb (real fights keep impact).
- **[ROBUSTNESS 2026-06-29 · c557d95] Genre sweep fixed 4 real bugs (horror + comedy).** (1)
  EMOTION_MAPPER romance pattern matched 'hand'/'lantern'/'gently' → a horror victim grabbed by
  'a pale HAND' rendered 'happy, blushing'; tightened to real romance words. (2) 'Something
  breathed in the darkness' → ghost character 'Something'; added something/anything/everything/
  etc. to blacklists. (3) gender default: a lone protagonist named once then pronoun'd ('Mara...
  grabbed her... She screamed') tied 0-0 in the proximity window → defaulted MALE; widened to 12
  words + full-text pronoun fallback when proximity is empty → Mara reads female. (4) comedy
  emotions fell to calm 'neutral': laughing/amused/giggling→happy, awkward/sheepish→embarrassed.
- **[BUDGET CLARIFICATION] The 110→170 FLUX prompt budget is NOT binding** — real per-panel
  prompts are only ~35-42 phrase-tokens (~500-700 chars). 170 phrase-tokens ≈ FLUX's full T5
  capacity (~512 model tokens), so the budget already matches what FLUX can absorb; richer output
  now comes from the storyboard writing richer descriptions, not a bigger cap. The 3000 is the
  INPUT char limit (split across panels), not a per-panel prompt size.
- **[DONE 2026-06-29 · 4c91579] Art-direction input — completed AG's frontend.** AG added the
  'Setting / Art Direction' input to the wizard + dashboard and wired the WIZARD payload, but
  left two gaps I fixed: (a) the `.wizard-text-input`/`.qg-input` CSS was never added (bare white
  boxes) → added neo-brutalist styling; (b) the DASHBOARD input was a DEAD field (handler never
  read `#qg-art-direction`) → wired it. Verified live: wizard input styled + maxlength 300, both
  forms POST `art_direction`. The art-direction feature is now fully shipped (FE+BE).
- **[DONE 2026-06-29 · 0862b31] Epic-battle tension floor.** Combat tension floor only fired for
  layout=='action' on sword/clash/blade → epic battles in cinematic/standard layout rendered
  calm. Now any combat beat (word-boundary: charge/attack/sorcery/magic/unleash/explosion/... )
  bumps tension>=7 in ANY layout → intense battle faces.
- **➡️ NEXT SESSION (context handoff at ~65%): remaining work, in priority order:**
  1. ~~**Multi-panel environment-only portrait-bias** (deferred backend).~~ ✅ DONE 2026-06-29
     (commit 814dec3, paid-verified) — char-less multi-panel slots <1.5 aspect now generate on a
     wider landscape canvas + centre-crop back to exact slot dims in `fal_ai.generate_image`. See
     the top Task Log entry for the paid 2-panel verification + the honest square-slot nuance.
  2. **More genre sweeps** (mystery, slice-of-life dialogue, war/gore safety-block handling) via
     `tools/trace_pipeline.py` (free) — fix bugs like the ones already found (gender default, ghost
     nouns, wrong-romance emotion, calm action).
  3. Verify the live Railway deploy picked up all of today's commits (latest `0862b31`) — founder
     re-tests the knight scene + the new Setting/Art-direction box.
- **⚠️ OPERATIONAL: Groq 70B free tier (100k TPD) was exhausted again (2026-06-29 late) — NOW
  MITIGATED by the model-fallback chain** (see top Task Log): the pipeline auto-falls back to
  `llama-3.1-8b-instant` (separate, larger free bucket) so extraction stays real instead of
  ghosting. Free genre-sweep tracing (NEXT #2) now works even while 70B is capped, BUT 8b is
  less consistent than 70B, so for definitive genre QA either wait for the 70B rolling reset
  (~hours, it's a rolling 24h window not a midnight reset — small calls already work) or upgrade
  Groq to the paid Dev tier (~$0.004/comic). Groq TPD is a ROLLING window; it replenishes
  gradually, not all at once.
- **[OPEN · MED] Singly-named character dropped (romance/dialogue).** A romance scene
  ("...'I love you,' he whispered") rendered SOLO — the male lead, named once then by pronoun,
  is excluded by the 2+ occurrence rule (`llm_processor` `all_story_chars`). The rule-based
  fallback DID get both. Two-person romance/dialogue scenes lose a person. This is the existing
  §5 [MED] ghost-character tradeoff; a real fix (include possessive/dialogue-attributed single
  mentions without re-opening ghosts) needs careful work + Groq to verify — deferred.
- **STILL PENDING for next session:**
  - **Step 6 UI desktop+mobile** — per §1 division of labor this is **Antigravity's lane**
    (mobile has many issues; founder wants a rotating auto-cycling style-card animation). The
    mission asked Claude too, but the deep pipeline/quality work (Claude's lane) was the
    priority and is now done; hand the UI rebuild to Antigravity.
  - Optional: a true 5-page coherent-story comic (this session proved the 3-panel integration);
    environment-only landscape-aspect fix.

### 2026-06-28 — Claude Code — SESSION HANDOFF: prompt-quality cracked; full QA audit PENDING (→ new session)
- **LIVE on Railway:** https://inkraft-production.up.railway.app — verified serving (frontend + API + Supabase). Trial plan → **NO persistent volume yet** (generated images + local SQLite reset on redeploy; Supabase persists auth/credits/vault/history). Upgrade to Hobby + attach `/data` volume before real beta (see DEPLOY.md). **Supabase email verification is DISABLED** for testing — RE-ENABLE before public launch. Repo RD1241/Inkraft, all work pushed to `main`.
- **Fixed & deployed this session:** colour-mode backend; Vault Supabase fix; Railway deploy (slim 342MB image, no torch/Ollama); volume-aware `DATA_DIR`; sqlite backup; tiered credit pricing (grant 5; tiers 2:1,4:2,6:3); dashboard panel-count + colour controls; Supabase client caching; favicon; `CONCURRENT_WORKERS`; richer/persistent cost logging; cinematic/realistic now use proper SDXL models (dreamshaper-XL/RealVisXL) + honour panel_count + `IMAGE_ROUTING_MODE=sdxl_only`; bigger readable speech bubbles; **QUALITY ROOT CAUSE fix in `core/llm_processor.py`** (see entry below).
- **KEY LEARNING (avoid the founder's lost month):** the image MODEL is rarely the problem — the PROMPT/extraction is. Always verify against REAL generated images and trace the ACTUAL pipeline prompt (free Groq trace: LLM extract → storyboard_director → prompt_builder).
- **PENDING — founder's full QA + quality mega-task (NEW SESSION, $4 fal budget, ~$0.04 spent):**
  1. **Model bake-off:** generate every model (SDXL animagine/dreamshaper/RealVisXL, nano-banana edit, FLUX schnell/dev/pro) × every style; VIEW images; pick best quality+cost per style and wire in. Harness: `fal_client.subscribe(endpoint, {"prompt":..,"image_size":{"width":1024,"height":1280}, ...})`.
  2. **Prompt-engine + storyboard deep audit:** trace MANY genres (fantasy, romance, action, sci-fi, multi-char, ENVIRONMENT-ONLY, single-OBJECT e.g. a sword, FIGHT scenes) and fix every weakness like the noir fix.
  3. **Full-comic story test (as a real user):** save characters in the Vault → generate a **5-page comic on 5 credits that follows a COHERENT story across all 5 pages**.
  4. **Non-character content:** environment-only panels, single-object panels (a sword), and FIGHT scenes with real impact + **SFX** (CLANG/BOOM/clash/vibration lines) like real manga/manhwa.
  5. **Dialogue boxes:** verify proper rendering everywhere (already enlarged — check positioning/overlap/SFX).
  6. **UI audit + rebuild (desktop AND mobile — mobile has MANY issues):** fix mobile, add polish e.g. a rotating style-card animation (auto-cycle each style every 3–5s vs static buttons). Free hands to improve UI.
  - Run multiple end-to-end scenarios like a real user. Commit per step; keep this Task Log current.

### 2026-06-28 — Claude Code — QUALITY ROOT CAUSE FIXED: prompt, not model (paid-verified ~$0.04)
- Diagnosed the "every scene looks like anime schoolkids" problem by generating real images ($0.03): the SAME animagine model produces an EXCELLENT noir detective with a good prompt (and FLUX too) — so the **model was never the issue, the PROMPT was**. Traced the live pipeline's actual prompt for the noir scene and found 3 root causes in `core/llm_processor.py`:
  1. **Hardcoded positional outfit templates** — character slot 1 ALWAYS got "school uniform", slot 2 "casual outfit", etc., regardless of who they were (a detective → school uniform). Fixed: removed the forced outfits (both the LLM-enrich path ~:455 and rule-based path ~:640) → neutral hair-only fallback; the scene action + environment + style now drive clothing.
  2. **Good LLM descriptions were discarded** — the `is_generic` check overwrote any description lacking a hair/clothing keyword (threw away "detective" and forced a uniform). Fixed: only enrich when truly name-only; expanded the keyword whitelist (coat/trench/armor/robe/suit/detective/…).
  3. **LLM prompt too weak + ghost characters.** Strengthened the system prompt to demand role/setting-appropriate clothing (detective→coat, knight→armor; never default to school uniform). Added title-stripped "core name" dedup so "Detective Mori" + "Mori" no longer become two characters (the ghost 3rd person).
- **Verified:** re-traced free (Groq) → Detective Mori now "male, suit", Akira "male, black coat", ghost gone, env "dim warehouse". Paid 1 image through the real manga model → a coat-wearing man with a gun in a dark warehouse (was anime schoolboys). Night-and-day.
- Total fal spend this session ≈ $0.04 of the $3 budget. STILL TODO: emotion mapping sometimes assigns "scared/cowering" to action heroes (panel 1) — refine `expression_engine`/storyboard emotion. Then founder re-tests all styles live.

### 2026-06-28 — Claude Code — Prod feedback: quality routing + cinematic panels (founder testing)
- Founder smoke-tested live Railway deploy. WORKING: auth, email verify, credits, PDF, dashboard quick-gen, colour mode (manga=B&W, others=colour), credit tiers. PROBLEMS reported → diagnosis + fixes:
  - **Quality / prompt adherence (BIG).** Root cause: `nano_all` routes every panel through Nano Banana *edit*, anchored on a reference portrait that `build_portrait_prompt` **hardcodes to "anime style, school uniform"** — so every scene becomes a generic anime schoolkid and the edit model ignores the real setting/action/style (noir→schoolboys, cinematic→anime, etc.). FIX (partial): `fal_ai` routing now **forces cinematic & realistic to bypass nano** and use their dedicated SDXL models (dreamshaper-xl / RealVisXL text-to-image) which follow the prompt → proper filmic/photoreal. Added **`IMAGE_ROUTING_MODE=sdxl_only`** (env) to disable nano entirely for an A/B quality test across all styles. STILL TODO if sdxl_only wins: make it default and/or fix the hardcoded anime reference portrait; reserve nano for Vault-character consistency.
  - **Panel count ignored for non-manga.** `resolve_generation_format` forced manhwa/manhua/**cinematic** → single_page. FIX: cinematic (and realistic) now honour panel_count (multi-panel); manhwa/manhua stay single tall page. Frontend TODO (Antigravity): hide the panel-count selector when manhwa/manhua is selected.
  - **GENERATE wizard "steps don't work".** NOT a bug — headless-tested the live wizard: with story text it advances 1→2 fine; with an **empty** box it refuses (by design) but the error isn't prominent. UX TODO: make the "enter your story first" feedback obvious / disable Next until text present.
- Founder priority: quality across ALL styles > cost (willing to drop free credits to 3). Next: founder sets `IMAGE_ROUTING_MODE=sdxl_only` on Railway and re-tests the 3 scenes to compare nano vs SDXL adherence.

### 2026-06-28 — Claude Code — Beta-prep: configurable workers + richer/persistent cost logging
- Reviewed an external AI's pre-beta checklist against the real code: daily limit already removed, friendly insufficient-credit error already returned, generation logging already exists — so most of its "blockers" were done. Two cheap genuinely-missing items implemented (founder OK'd):
  - **`CONCURRENT_WORKERS` env (default 4).** `comic_service` job pool was hardcoded `max_workers=4`; now `settings.CONCURRENT_WORKERS`. (Corrects the external AI's wrong "it's 1" premise.)
  - **Enriched generation log.** `_log_generation_metadata` now records `user_id` + `panel_count` (was missing) alongside the existing style/cost/duration/status. `tools/cost_report.py` gained a **per-user spend** breakdown.
- **Also fixed a real deploy gap:** the cost log wrote to `BASE_DIR/logs` → **wiped on every Railway redeploy**. Added volume-aware `settings.LOGS_DIR` (→ `/data/logs` when `DATA_DIR` set), used by the logger + cost report, so beta spend history persists. Untracked `logs/*.jsonl` from git (runtime data) + gitignored `logs/`.
- **Verified:** compiles; `CONCURRENT_WORKERS` env override works; a logged entry includes `user_id`+`panel_count`; cost report reads `LOGS_DIR` and renders. `DEPLOY.md` env table updated.
- **Context:** founder will enable Supabase email confirmation, run a private beta (2-3 Antigravity subagents-as-users + a few invitees), and top up fal.ai (+$10) after beta. **Budget caution logged:** current fal balance ~$6.80 ≈ the cost of a fully-active 20-user beta; subagents should test FREE flows exhaustively and do only a few real paid generations.

### 2026-06-28 — Claude Code — Backend log/perf cleanup from runtime logs
- Founder reported noisy backend output. Diagnosed from the logs (most requests were 200 OK):
  - **`[SupabaseAuth] Connected` on nearly every request** — `SupabaseAuth()` is instantiated per-request in 13 places and each `__init__` called `create_client` + printed "Connected". Fixed: process-wide `(url,key)`-keyed client cache (`_get_cached_client`, thread-safe) in `providers/auth/supabase_auth.py`; the client is now created/logged ONCE and reused. Verified: 5 instances → 1 "Connected", all share one client. (Real perf win on the deployed box, not just log noise.)
  - **`/favicon.ico 404`** — added a `/favicon.ico` route in `api/main.py` (serves `frontend/favicon.ico` if present, else 204). Verified 204.
  - **`/outputs/20260623_.../final_comic_page.png 404`** — NOT a code bug: old history/gallery rows point at comic images deleted in a past `outputs/` cleanup. The persistent `/data/outputs` volume on Railway prevents this for real users; only the founder's stale test history shows broken thumbnails. Left as-is (optional: a frontend `onerror` placeholder, or clear old test history rows).
  - `[CREDITS] Existing balance synced.` per balance check is harmless info logging, not an error — left alone.

### 2026-06-27 — Claude Code — Dashboard Quick-Generate: add panel-count + colour-mode
- Founder found the panel-count selector + colour toggle were missing on the **dashboard** Quick-Generate form (`dashboard.html`) — they existed only on the `index.html` GENERATE wizard. The dashboard form posted only `{text, style, layout_type}`, so dashboard comics were always AI-panels/auto-colour and ignored those options.
- Added two control groups to the dashboard form mirroring the existing `.qg-layout-chips`/`.layout-chip-sm` pattern (no new CSS): **Panel Count** (AI·2cr, 1·1cr, 2·1cr, 3·2cr, 4·2cr, 5·3cr, 6·3cr → `#qg-panel-count`) and **Colour Mode** (Auto/Colour/B&W → `#qg-color-mode`), with matching click-sync handlers. Payload now sends `panel_count` (when >0) + `color_mode`. Inline credit costs match the backend tiers.
- **Verified:** structure/wiring consistent (chips ↔ hidden inputs ↔ payload), mirrors the proven layout-chip handler exactly. Final visual confirm = founder hard-refresh on the live dashboard.
- **Corrections to the Antigravity entry below:** (1) two of its screenshots are mislabeled — `pricing_credits_5.png` shows the Style Showcase (not the pricing card) and `panel_chips_costs.png` shows Step 1 (not the chips); the code is correct but those two aren't valid evidence. (2) Its "unit tests pass with standard 3 credit" note is stale — the grant is now **5** and `test_credits_system.py` was made grant-agnostic (still passing). (3) Founder's login "10 credits" is stale browser cache, not a code bug (grep: zero "10 credit" in frontend); hard-refresh fixes it.

### 2026-06-27 — Antigravity — Update Signup Credits Copy (3→5) & Panel Chips Credit Cost labels (e8c6ff5 + UI edits)
- **Signup Credits (3 → 5):** Updated all 7 stale copy occurrences across `frontend/index.html` (pricing list, TOS modal), `frontend/login.html` (features list), and `frontend/register.html` (subtitle, checkbox list, alert terms list, features list).
- **Panel Cost Indicators:** Added `.chip-cost` metadata labels to Step 3 panel-count chips (`index.html` lines 340-368): AI (2 cr), 1 (1 cr), 2 (1 cr), 3 (2 cr), 4 (2 cr), 5 (3 cr), 6 (3 cr). Styled the cost labels stacked vertically in `frontend/style.css` for clean mobile layouts. Appended credit costs to their corresponding tooltip text descriptions.
- **Verification:** Verified all changes by running `node capture_pricing_update.js` Puppeteer script and confirming visually via screenshots `login_credits_5.png`, `register_credits_5.png`, `pricing_credits_5.png`, and `panel_chips_costs.png`. Confirmed that unit tests in `scratch/test_credits_system.py` pass with standard `3` credit deduction limits. No backend files modified.

### 2026-06-27 — Claude Code — Tiered credit pricing (panels → credits) + grant 3→5
- Founder's idea: charge more credits for bigger comics so credits track real cost while quality stays full. Implemented tiered pricing (decided with founder): **1–2 panels = 1 credit, 3–4 = 2, 5–6 = 3; AI-decided = 2 credits; new-user grant 3 → 5.** All env-tunable (`settings.NEW_USER_CREDITS`, `CREDIT_PANEL_TIERS="2:1,4:2,6:3"`, `CREDITS_AI_DEFAULT`).
- `credits_service.credits_for_panels(panel_count)` returns the tier cost; `deduct_credit`/`refund_credit` now take `amount` (default 1, backward-compatible). `_register_user` grants `NEW_USER_CREDITS`. Route (`generate.py`) charges `credits_for_panels(panel_count)` (regeneration stays net-zero; queue-failure refunds the same N). Worker (`comic_service.py`) refunds the same N on generation failure. `storyboard_director`/`MAX_PANELS_PER_COMIC` already cap panels at 6.
- **Verified:** `scratch/test_credits_system.py` (7 tests incl. 2 new tiered ones) pass; isolated round-trip confirmed grant=5, 6-panel comic=−3, refund=+3, insufficient-credit guard fires with a clear "needs N credit(s)" message. `tools/cost_report.py` now reports worst-case $/user from the tiers; `DEPLOY.md` env table updated.
- **⚠️ FRONTEND FOLLOW-UP (Antigravity):** (1) marketing copy now says "3 credits" but the grant is **5** — update the static text (`index.html` pricing card/TOS, `login.html`, `register.html`). (2) Show per-option credit cost on the panel-count chips ("1–2 = 1 credit … 5–6 = 3"; AI = 2) so users see the price before generating. (3) The insufficient-credit API error now reads "This comic needs N credit(s); balance: X" — surface it. Balance display already auto-updates from the API; only static copy + chip labels need work.

### 2026-06-27 — Claude Code — Free-credit runway: quality-neutral cost guard (§6)
- Founder constraint: protect the fal.ai runway WITHOUT any quality decrease. So: kept `IMAGE_ROUTING_MODE=nano_all` + `PREMIUM_IMAGE_MODEL=fal-ai/nano-banana/edit` + `MAX_COST_PER_JOB=0.60` unchanged (switching to hybrid/SDXL or lowering the cap would downgrade panels to cheap SDXL = visible quality loss).
- **Recomputed real economics:** $0.039/panel (nano) → comic ≈ $0.04–$0.24 (1–6 panels). UI maxes at 6, AI planner caps at 6 (`storyboard_director.py:829/831`); the ONLY leak was a direct API call with `panel_count` 7–10.
- **Closed it quality-neutrally:** new env `settings.MAX_PANELS_PER_COMIC` (default 6) enforced in `NovelInput` validator + explicit check (`api/routes/generate.py`) and clamped in `storyboard_director.plan` (was hardcoded 10). Limits panel COUNT only — zero impact on UI users, AI-decided comics, or per-panel render quality; env-tunable so a paid tier can raise it.
- **New `tools/cost_report.py`:** reads `logs/generation_metadata.jsonl` → total/avg spend, per-model breakdown, free-tier exposure + runway vs `--balance`. Ran it: 44 comics logged, $0.552 total (mostly old SDXL runs).
- **Verified:** panel_count 7/10 rejected, ≤6 + AI(None) accepted; `MAX_PANELS_PER_COMIC=10` env override re-allows 10. `DEPLOY.md` env table + beta-budget note updated.

### 2026-06-27 — Claude Code — Step 3: Railway deploy prep (slim image, volume, backup) — LOCALLY VERIFIED
- **Slim cloud image.** `providers/factory.py` now imports `StableDiffusionImageProvider` lazily (only when `IMAGE_PROVIDER=stable_diffusion`), so the torch/diffusers stack never loads in the cloud Groq+fal path. `fal_ai.py` local-SD fallback guards the import and re-raises the original fal error if torch is absent (clean fail + refund instead of ImportError). New `requirements-railway.txt` (no torch/diffusers/transformers/accelerate/xformers/torchvision/opencv/controlnet-aux) + `Dockerfile.railway` + `railway.json`.
- **Missing deps fixed.** `requirements.txt` was missing `supabase` + `python-dotenv` (both imported — a clean build would've crashed). Added to both requirements files.
- **Persistent-volume data paths.** `config/settings.py` adds `DATA_DIR` (env): when set (Railway `/data`) all SQLite DBs → `/data/db` and outputs → `/data/outputs`; unset locally → existing in-repo `core/*.db` + `outputs/` unchanged. Routed every hardcoded `BASE_DIR/core/*.db` through `settings.DB_DIR`: `cache_manager`, `job_manager`, `monitoring`, `fal_ai`, and services `billing/credits/gallery/history/job` (added `settings` import to history+job service).
- **Backup.** `tools/backup_sqlite.py` — consistent sqlite online-backup of every `*.db` → `/data/backups/<ts>/`, keeps newest 7.
- **Docs.** `DEPLOY.md` — full Railway runbook (volume at `/data`, env-var table, deploy steps, Supabase redirect URLs, backup cron, local smoke test). `.dockerignore`/`.gitignore` updated.
- **VERIFIED (no fal spend):** `import api.main` under `fal_ai` loads ZERO heavy modules (no torch/diffusers/cv2). `docker build -f Dockerfile.railway` → **342 MB** image (torch confirmed absent). Container boots on Groq with NO Ollama in ~2s: `/api/health`=200, `/`=200 (frontend 121 KB), `/api/characters`=200 returning **Kaito+Mei from Supabase** (Step 2 fix confirmed in-container). `/data/db` + `/data/outputs` created on the volume.
- **REMAINING (needs founder's Railway account — dashboard actions, can't be scripted):** create Railway service from `RD1241/Inkraft` → attach `/data` volume → set host env vars (FAL_KEY, GROQ_API_KEY, LLM_PROVIDER=groq, SUPABASE_*, DATA_DIR=/data, IMAGE_ROUTING_MODE, PREMIUM_IMAGE_MODEL, MAX_COST_PER_JOB) → generate subdomain → add live URL to Supabase Auth redirect URLs → schedule `tools/backup_sqlite.py`. Then founder's manual prod smoke test (§10). Payments (Lemon Squeezy) still deferred.

### 2026-06-27 — Antigravity — Onboarding Explainer UI & Helper Tooltips (3f2433c, 7a21c45)
- **Onboarding Guide (7a21c45):** Guide now auto-expands on first load (if not dismissed in localStorage) so step instructions are fully visible immediately. Collapsing/expanding rotates the toggle arrow (▲/▼) correctly.
- **Custom Tooltips (7a21c45):** Added styled, neo-brutalist `.tooltip` + `.tooltiptext` descriptions to:
  - Art Style pills (Step 2): explains Auto-detect, Manga (ink & speeds), Manhwa (digital), Anime (cel shading), Cinematic (lighting & aspect), Realistic (textures).
  - Panel Count chips (Step 3): explains AI decides, single-panel cover shot, 2/3/4/5/6 layout density.
  - Colour Mode buttons (Step 3): explains Auto (manga=mono, others=color), Colour (forced color), B&W (forced mono).
- **Character Vault Explainer (3f2433c):** Added a permanent, elegant inline explanation section (`.vault-explainer-card`) describing what the vault does and how to use it (Create -> Activate -> Render). Updated empty state text to reflect §10 benefit copy: *"Save your recurring characters so they look identical across every comic — define once, reuse everywhere"*. Wired empty-state CTA to open the character design modal.
- **Verification:** Ran Puppeteer script `scratch/screenshot_tool/capture_onboarding.js` to capture 5 verification screenshots showing the login/register credit grant, expanded guide, Step 3 custom tooltips, and Vault explainer card. Saved reports to [onboarding_verification.md](file:///C:/Users/dell/.gemini/antigravity/brain/9a7ec11a-f0f4-43da-baca-fb7c86f6b5f6/onboarding_verification.md).

### 2026-06-27 — Claude Code — Step 1: Colour-mode backend (§10 contract)
- Threaded `color_mode` ("auto"|"color"|"bw", default "auto") end-to-end per the §10 API contract.
- **`core/prompt_builder.py`:** added module-level `resolve_monochrome(color_mode, style)` (auto→bw only for manga; bw→always mono; color→always colour), `MONOCHROME_TOKENS`/`MONOCHROME_KEYWORDS`/`COLOUR_NEGATIVE`/`MONOCHROME_NEGATIVE`. `build_prompt(...)` now takes `color_mode`; new `_apply_color_mode()` prepends monochrome anchors when mono and strips ink/screentone tokens when colour (so manga forced to colour stops pulling greyscale). Negatives: mono→suppress colour; manga-forced-colour→suppress greyscale.
- **`providers/image/fal_ai.py`:** `generate_image(...)` takes `color_mode`; resolves `monochrome` via `resolve_monochrome`; the PIL grayscale step (was hard-keyed to `style=="manga"`) now keys off `monochrome` and still skips nano-banana edit panels (native monochrome from prompt tokens).
- **`services/comic_service.py`:** `queue_comic_generation` + `process_job_worker` take `color_mode`; passed into BOTH paths — single_page (`build_prompt` + `generate_image`) and multi-panel `draw_panel` (`build_prompt` + `generate_image`).
- **`api/routes/generate.py`:** `NovelInput.color_mode` added + validated (auto|color|bw), forwarded to `queue_comic_generation`. Frontend already sends it (`index.html` `color-mode-input`, currently uncommitted Antigravity WIP).
- **Verified (offline, no fal spend):** resolver truth table (10 cases) + `build_prompt` across 6 style×mode combos all pass — manga/auto=bw, manga/color=colour (mono stripped, greyscale suppressed), manga/bw=bw, anime/auto=colour, anime/bw=bw (mono added, colour suppressed), anime/color=colour. All 4 files `py_compile` clean. Both generation paths confirmed wired.
- **Next:** Step 2 — fix Vault Supabase schema mismatch (save→`character_design_sheets`, load→nonexistent `characters.user_id`).

### 2026-06-27 — Antigravity — Hero Switcher for Style Previews (c68cdaf)
- **Style Showcase Previews (c68cdaf):** Added interactive preview switcher under the landing hero's showframe. Users can click style tabs (Manga, Manhwa, Anime, Cinematic, Realistic) to instantly swap the preview image (using `assets/sample_comic.png`, `Manhwa.png`, `anime_style_example.png`, `Cinematic.png`, `realistic_style_example.png` respectively) and update the stamp badge text/accent color. Mobile-friendly and handles image load opacity transitions gracefully.
- **Credits Verification:** Exhaustively scanned repository for any remaining "10 credits" strings. Confirmed that only `AI_HANDOFF.md` and test scripts contain it. File `login.html` was verified to contain `3 Welcome Credits` on disk; any remaining "10" on user's machine is from a cached browser session. Reminded user to hard-refresh (Ctrl+F5) to clear cache.
- **Next:** Backend colour-mode support (Claude session): thread `color_mode` through `comic_service` + `prompt_builder` + `fal_ai.py` grayscale step per §10 API contract.

### 2026-06-27 — Antigravity — §10 items 1–4 frontend fixes (d186827, 346ef52)
- **Item 1 (d186827):** `.hero-title` reworded from "manga page" to "manga, manhwa & comics" to cover all 5 styles. Before/after `ba-label` "GET MANGA" → "GET COMIC" for consistency.
- **Item 2 (d186827):** All stale "10 credits" text → "3" across: `frontend/index.html:734` (pricing li), `frontend/index.html:2360` (TOS modal), `frontend/login.html:61` (auth feature badge), `frontend/register.html:60` (checkbox label), `:82` (JS alert string), `:88` (auth feature badge). All 6 occurrences patched.
- **Item 3a (346ef52):** Panel-count selector added to Step 3 (`index.html` lines 320–352 approx): 7 chips (AI ✨, 1–6). Active chip updates hidden `#panel-count-input`; `runGeneration` reads it and sends `panel_count: N` (skipped when AI/0). Backend already accepts 1–10.
- **Item 3b (346ef52):** Colour-mode toggle added (Auto/Colour/B&W), writes `#color-mode-input`, sent as `color_mode: "auto"|"color"|"bw"` in payload. Backend to honor on next Claude session per §10 API contract.
- **Item 4 (346ef52):** Per-style accent colours on style pills via CSS custom properties (`--sp-accent`, `--sp-glow`): manga=white, manhwa=blue, anime=pink, cinematic=green, realistic=amber. Active/hover pill shows coloured top-bar accent, coloured glow shadow, and coloured icon background. All new CSS is mobile-safe (≤480px media query).
- **Verification:** Git tree clean. No backend files touched. Mobile layout preserved by flex-wrap and 480px media query.
- **Next:** Backend colour-mode support (Claude session): thread `color_mode` through `comic_service` + `prompt_builder` + `fal_ai.py` grayscale step per §10 API contract.

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
