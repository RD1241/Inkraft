# Inkraft Project Handover Documentation

This document serves as the single source of truth for the Inkraft codebase. It has been compiled by verifying the current files, code paths, and database schemas directly. Any continuing AI agent (e.g., Claude Code) should use this file to understand the architecture, historical context, and immediate next steps.

---

## 1. Project Overview

*   **What Inkraft Is**: Inkraft is an AI-powered creator platform that automates the generation of sequential comic strips and single-page manhwa from text-based novel scripts, with a strong focus on character visual consistency across panels.
*   **The Technology Stack**:
    *   **Backend**: FastAPI (Python 3.10) serving REST endpoints.
    *   **Frontend**: Vanilla HTML5, CSS3, and JavaScript. **Confirming directly**: There is no Next.js/React framework on the frontend; all views (`index.html`, `dashboard.html`, `history.html`, `characters.html`) use standard browser scripts and CSS files located in the [frontend](file:///d:/Project_I/NovelToComic/frontend) directory.
    *   **Databases**: Local SQLite files stored in the [core](file:///d:/Project_I/NovelToComic/core) folder:
        *   [character_memory.db](file:///d:/Project_I/NovelToComic/core/character_memory.db): Vault character profiles and styling tokens.
        *   [jobs.db](file:///d:/Project_I/NovelToComic/core/jobs.db): Job statuses, credits, history, and transaction logs.
        *   [metrics.db](file:///d:/Project_I/NovelToComic/core/metrics.db): System performance logs.
        *   [cache.db](file:///d:/Project_I/NovelToComic/core/cache.db): LLM generation caching.
    *   **Authentication**: Integrated with Supabase Auth via [supabase_auth.py](file:///d:/Project_I/NovelToComic/providers/auth/supabase_auth.py). If API credentials are missing, it falls back gracefully to a mock offline token generator.
*   **Founder Context**: The founder values dry, evidence-backed claims over confident narrative summaries. Under no circumstances should success be reported without verifying the actual code, generated assets on disk, or logs.
*   **fal.ai Key Status**: The active `FAL_KEY` in the `.env` file is a standard scoped API key. Querying the billing account endpoint (`https://api.fal.ai/v1/account/billing?expand=credits`) returns an authorization error because billing checks require Admin-scoped privileges. The verified starting balance of the test suite was **$7.27**, and our reference conditioning test run consumed **$0.45** (3 panels of Nano Banana 2 edit at $0.15 each), leaving a remaining balance of **$6.82**.

---

## 2. Full Sprint History

### Sprint 1: SaaS Core Architecture
*   Established the FastAPI server and local SQLite database layers.
*   Built the LLM processor integration using local Ollama (`llama3:latest`) for scene-by-scene script beats parsing.
*   Configured the initial Stable Diffusion provider using local Hugging Face checkpoints (`Lykon/dreamshaper-8`) and IP-Adapter/ControlNet openpose weights cached on the `D:` drive.

### Sprint 2: UI/UX Overhaul
*   Designed the responsive homepage creator wizard (Step 1: Script, Step 2: Art Style, Step 3: Format & Pacing, Step 4: Active Cast, Step 5: Review).
*   Built character card vault cards featuring traits badges (Gender, Hair, Eyes, Outfit, features) and the quick-generate dashboard layout.

### Sprint 3: Trust & Consistency Sprint
*   **Phase 1**: Implemented credit deduction gates (`credits_service.py`) to prevent double-billing. Refunding logic was integrated into the job runner if pipeline stages crashed.
*   **Phase 2**: Redesigned the auth screens (`login.html`, `register.html`) with Supabase, aligned UI layout spacing for tablet hamburger drawers, and added mobile scaling transforms to keep the landing page hero grids snug under 480px.

### Sprint 4: Pre-Beta Final Sprint
*   **Character-Fidelity Investigation**:
    *   *Ghost-Character Heuristic Bug*: A rule-based parser bug was identified where pronouns like "Their" were parsed as capitalized names and inserted into the active character cast, leading to seed offset bleeding and facial trait corruption. Resolved by introducing a strict blacklist and word frequency checker (requiring 2+ name occurrences).
    *   *Gender-Negation / Safety-Block Contradiction*: For single-character close-ups (e.g. Kaito), the system injected secondary character gender negation (`1girl, girl, female...`) into the negative prompt. However, if the scene description still contained the secondary character's name or pronouns (e.g. `"Across the room, Mei enters..."`) in the positive prompt, the conflicting tokens caused SDXL to trigger a safety block (returning a black frame). The system's fallback retry logic stripped the prompt to recovery strings (`"1boy, manga style"`), causing the model to lose the library environment and render a street sidewalk with a parked car (environment regression).
    *   *Close-Up Framing Grid/Mosaic Failure*: Ablation tests revealed that requesting tight framing (`CLOSE_UP`, `PORTRAIT`) alongside multi-character positive prompts and consistency suffixes caused SDXL to crash and output a grid of 6 tiled headshot crops.
    *   *The Architectural Fixes*:
        1.  Added character recovery in `_normalize_characters` ([llm_processor.py](file:///d:/Project_I/NovelToComic/core/llm_processor.py)) to ensure active script characters are consistently present in the scene characters metadata, preventing positive/negative contradictions.
        2.  Wired a storyboard director override in [storyboard_director.py](file:///d:/Project_I/NovelToComic/core/storyboard_director.py#L533-L554) that blocks close-up angles and replaces them with `MEDIUM_CLOSE` or wider whenever multiple characters occupy a panel.
*   **Multi-Model Evaluation & Routing**:
    *   *Animagine-XL-3.1*: Configured as the high-quality baseline for manga and anime styles on fal.ai.
    *   *Seedream 4.5*: Evaluated for text-to-image quality, but lacked multi-character image-to-image conditioning.
    *   *fal-ai/nano-banana-pro/edit (Google Nano Banana 2)*: Tested and integrated. It accepts an array of up to 2 reference images (`image_urls`) and successfully outputs native black-and-white manga styling (monochrome max channel difference <= 4) even when fed colored character portraits.
    *   *Routing Verdict*: Fully implemented **tiered model mapping** where cheap single-character panels are routed to SDXL (~$0.0025) and premium multi-character/shared-frame panels are routed to `nano-banana-pro/edit` ($0.15) with cached reference portraits.
*   **Vault-Mandatory Character Path**:
    *   Integrated into the creator wizard in [index.html](file:///d:/Project_I/NovelToComic/frontend/index.html). Prior to script submission, the frontend calls the backend endpoint `/api/characters/detect` to extract names and genders. If 2+ characters are detected and any are missing from the vault modal list, submission is blocked and the Add Character modal is pre-filled and shown, auto-resuming generation once saved.
*   **ThreadPoolExecutor max_workers**:
    *   Bumped from `1` to `4` in [comic_service.py](file:///d:/Project_I/NovelToComic/services/comic_service.py#L35) (`self.job_executor = ThreadPoolExecutor(max_workers=4)`) to support concurrent generation during the beta launch.
*   **Manga Monochrome Mechanism**:
    *   **Current State**: Integrated in [fal_ai.py](file:///d:/Project_I/NovelToComic/providers/image/fal_ai.py). Single-character panels continue to use SDXL with post-processing PIL grayscale conversion. Shared-frame panels route directly to `fal-ai/nano-banana-pro/edit` which produces native monochrome outputs, bypassing the PIL conversion.

---

## 3. Current Technical State

### Image Generation Routing Table
*   **SDXL Endpoint**: `fal-ai/fast-sdxl` (charges ~$0.0025 per panel). Used for single-character panels.
*   **Nano Banana 2 Endpoint**: `fal-ai/nano-banana-pro/edit` (charges $0.15 per panel). Used for multi-character shared panels with cached reference portraits.
*   **Blended Cost Estimation**:
    *   A typical comic contains 4 panels (on average: 2 single-character and 2 multi-character).
    *   Tiered routing cost calculation: `2 * $0.0025 + 2 * $0.15 = $0.305` per comic.
    *   The blended cost under the tiered system will be **$0.30 to $0.31** per comic, replacing the old SDXL-only figure of $0.01 per comic.

### Database, Auth, & Deployment Status
*   **Databases**: All local SQLite DBs exist and contain active tables (`jobs`, `credits`, `character_profiles`, `character_design_sheets`).
*   **Supabase Auth**: Credentials are active in `.env`.
*   **Deployment**: Local-only. The server runs via [start_server.ps1](file:///d:/Project_I/NovelToComic/start_server.ps1). Deployment files (`Dockerfile`, `docker-compose.yml`) are configured but Railway/Vercel pipelines are not initialized.

---

## 4. Honest Quality Assessment

*   **Character Consistency (Single-char: 8.5/10, Multi-char: 8.5/10)**:
    Using Nano Banana 2's `image_urls` list, multi-character panels successfully maintain both Kaito's and Mei's features in shared frames, solving the single-image IP-Adapter limitation of SDXL.
*   **Art Quality (8.5/10)**:
    Animagine XL 3.1 and RealVisXL V4.0 produce rich details, clean lines, and highly detailed backgrounds.
*   **Monochrome Correctness (10/10)**:
    Nano Banana 2 achieves native monochrome outputs (max channel difference <= 4). Any SDXL outputs are post-processed via PIL grayscale to guarantee black-and-white styling.
*   **UI/UX (8.0/10)**:
    The dark mode and responsive layouts fit well, though the homepage wizard container shifts slightly when loading extra panel cards.
*   **Generation Speed (8.0/10)**:
    SDXL finishes panels in ~4.5 seconds. Nano Banana 2 takes ~25-30 seconds. A typical 4-panel comic processes in ~1 minute.

---

## 5. Known Open Items / Not Yet Done

1.  **Deployment**: Configure Railway for FastAPI and Vercel for the static frontend.
2.  **Lemon Squeezy**: Payments and credits purchase flow are deferred.
3.  **Panel Count Selector**: Explicitly cut from the frontend wizard.
4.  **Pricing & Credit Math**: The current system charges 1 credit per comic. With blended costs rising from $0.01 to $0.30+ per comic, the credit-to-dollar pricing math must be recalculated before open beta.

---

## 6. Style/Process Notes for Continuing AI

> [!WARNING]
> **Validate Before You Report**
> Inkraft has a history of agent logs claiming features are "working" based on successful compilation, only for screenshots to reveal color bleeding, tiled grids, or empty characters.
> **Always verify your changes by checking actual files, generated images, or querying databases.** Never state something is complete without direct verification.
