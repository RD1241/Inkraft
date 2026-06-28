import os
import time
import httpx
import sqlite3
from PIL import Image
from config import settings
from providers.image.base import ImageProvider
from core.storyboard_director import is_shared_frame_panel

def get_character_sheet(name: str, job_id: str) -> dict:
    """Helper to retrieve character design sheet by name and job_id."""
    if not job_id:
        return {}
    
    # 1. Lookup user_id from jobs database
    user_id = None
    jobs_db_path = os.path.join(settings.DB_DIR, "jobs.db")
    if os.path.exists(jobs_db_path):
        try:
            conn = sqlite3.connect(jobs_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                user_id = row[0]
            conn.close()
        except Exception as e:
            print(f"[FalAI] Failed to lookup user_id in jobs.db: {e}")

    if not user_id:
        user_id = "00000000-0000-0000-0000-000000000000"  # fallback

    # 2. Query character_design_sheets from character_memory.db
    char_db_path = settings.DB_PATH
    if os.path.exists(char_db_path):
        try:
            conn = sqlite3.connect(char_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT gender, age_range, hair_style, hair_color, eye_color, body_type, primary_outfit, distinguishing_features
                FROM character_design_sheets
                WHERE user_id = ? AND LOWER(name) = ?
            """, (user_id, name.lower()))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "gender": row[0],
                    "age_range": row[1],
                    "hair_style": row[2],
                    "hair_color": row[3],
                    "eye_color": row[4],
                    "body_type": row[5],
                    "primary_outfit": row[6],
                    "distinguishing_features": row[7]
                }
        except Exception as e:
            print(f"[FalAI] Failed to fetch character sheet: {e}")

    return {}

def build_portrait_prompt(name: str, sheet: dict) -> str:
    # Build structured prompt segment
    gender = sheet.get("gender") or "male"
    age = sheet.get("age_range") or "adult"
    
    hair_parts = []
    if sheet.get("hair_style"):
        hair_parts.append(sheet["hair_style"])
    if sheet.get("hair_color"):
        hair_parts.append(sheet["hair_color"])
    hair = f"{' '.join(hair_parts)} hair" if hair_parts else ""
    
    eye_color = sheet.get("eye_color") or ""
    eye_str = f"{eye_color} eyes" if eye_color and "eye" not in eye_color.lower() else eye_color
    
    outfit = sheet.get("primary_outfit") or ""
    features = sheet.get("distinguishing_features") or ""
    body_type = sheet.get("body_type") or ""
    
    # Assembly
    core_parts = [
        f"portrait of a teenage {gender} named {name}" if "teen" in age.lower() else f"portrait of a {gender} named {name}",
        f"{gender} {age}",
        hair,
        eye_str,
        features,
        outfit,
        body_type,
        "neutral expression, front-facing, plain white background, upper body shot, sharp linework, detailed anime art"
    ]
    cleaned = [p.strip() for p in core_parts if p and p.strip()]
    prompt = "masterpiece, best quality, anime style, " + ", ".join(cleaned)
    return prompt

def is_valid_portrait(image_path: str, min_stddev: float = 6.0) -> bool:
    """
    Validate that a generated reference portrait actually contains an image —
    not a blank/solid/black safety-block frame or a corrupt file.

    Returns False for: unreadable files, near-black frames (max < 10),
    near-solid single colors (max-min < 12), or images whose grayscale
    pixel variance is below a sane threshold (almost no detail).
    """
    try:
        from PIL import ImageStat
        with Image.open(image_path) as img:
            gray = img.convert("L")
            lo, hi = gray.getextrema()
            if hi < 10:            # pure black — classic safety block
                return False
            if hi - lo < 12:       # near-solid single color
                return False
            if ImageStat.Stat(gray).stddev[0] < min_stddev:  # almost no detail
                return False
        return True
    except Exception:
        return False

# Default text-to-image model per style.
# The paid model bake-off (2026-06-28; images in test_outputs/bakeoff/) compared
# fast-sdxl (animagine/dreamshaper-XL/RealVisXL) against FLUX schnell/dev/pro on the
# REAL pipeline prompt across every style. FLUX dev followed the prompt dramatically
# better — correct multi-character composition (SDXL kept dropping the 2nd character
# or producing broken diptychs), period/prop accuracy (SDXL "realistic" gave a modern
# soldier with a rifle for "armor + sword"; FLUX gave armor + sword), and NATIVE
# monochrome manga (no washed-out PIL-grayscale needed) — at $0.025/img, which is
# actually CHEAPER than the nano-banana edit path ($0.039). So the default
# text-to-image model is now FLUX dev for every style. Each is env-overridable; the
# proven fast-sdxl models are documented below as fallbacks, and realistic/cinematic
# can be pushed to flux-pro (FAL_*_ENDPOINT=fal-ai/flux-pro/v1.1) for max fidelity.
FLUX_DEV_ENDPOINT = "fal-ai/flux/dev"
# Fallback SDXL models (set FAL_<STYLE>_ENDPOINT=fal-ai/fast-sdxl + FAL_<STYLE>_MODEL
# to revert a style to SDXL): manga/manhwa/anime=cagliostrolab/animagine-xl-3.1,
# cinematic=Lykon/dreamshaper-xl-v2-turbo, realistic=SG161222/RealVisXL_V4.0.
STYLE_MODEL_MAP = {
    "manga": {
        "endpoint": os.environ.get("FAL_MANGA_ENDPOINT", FLUX_DEV_ENDPOINT),
        "model_name": os.environ.get("FAL_MANGA_MODEL"),
    },
    "manhwa": {
        "endpoint": os.environ.get("FAL_MANHWA_ENDPOINT", FLUX_DEV_ENDPOINT),
        "model_name": os.environ.get("FAL_MANHWA_MODEL"),
    },
    "anime": {
        "endpoint": os.environ.get("FAL_ANIME_ENDPOINT", FLUX_DEV_ENDPOINT),
        "model_name": os.environ.get("FAL_ANIME_MODEL"),
    },
    "cinematic": {
        "endpoint": os.environ.get("FAL_CINEMATIC_ENDPOINT", FLUX_DEV_ENDPOINT),
        "model_name": os.environ.get("FAL_CINEMATIC_MODEL"),
    },
    "realistic": {
        "endpoint": os.environ.get("FAL_REALISTIC_ENDPOINT", FLUX_DEV_ENDPOINT),
        "model_name": os.environ.get("FAL_REALISTIC_MODEL"),
    },
}

PRE_SAFETY_SANITIZATION_MAP = {
    "confronts": "meets",
    "confront": "meets",
    "confronting": "meeting",
    "confronted": "met",
    
    "betrayal": "disagreement",
    "betray": "disagree",
    "betrays": "disagrees",
    "betrayed": "disagreed",
    
    "threaten": "challenges",
    "threatens": "challenges",
    "threatening": "challenging",
    "threatened": "challenged",
    
    "accuse": "disputes",
    "accuses": "disputes",
    "accusing": "disputing",
    "accused": "disputed",
    
    "clash": "encounter",
    "clashes": "encounters",
    "clashing": "encountering",
    "clashed": "encountered",
    
    "collide": "impact",
    "collides": "impact",
    "colliding": "impacting",
    "collided": "impacted"
}

RISK_KEYWORDS = {
    "betrayal": 2,
    "betray": 2,
    "accuse": 2,
    "accuses": 2,
    "threaten": 2,
    "threatens": 2,
    "murder": 3,
    "murders": 3,
    "murdered": 3,
    "kill": 3,
    "kills": 3,
    "killed": 3,
    "blood": 2,
    "bloody": 2,
    "violent": 2,
    "violence": 2,
    "clash": 2,
    "clashes": 2,
    "confront": 2,
    "confronts": 2,
    "execute": 2,
    "executes": 2,
    "executed": 2,
    "war": 2,
    "assassinate": 3,
    "assassinated": 3,
    "assassinates": 3
}

import re

class PromptRiskAnalyzer:
    def __init__(self, risk_map: dict = None, threshold: int = 3):
        self.risk_map = risk_map or RISK_KEYWORDS
        self.threshold = threshold

    def analyze(self, prompt: str) -> tuple[int, bool]:
        """
        Returns (score, should_sanitize)
        """
        score = 0
        prompt_lower = prompt.lower()
        
        for word, points in self.risk_map.items():
            pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
            matches = pattern.findall(prompt_lower)
            if matches:
                score += points * len(matches)
                
        should_sanitize = score >= self.threshold
        return score, should_sanitize

class FalAIImageProvider(ImageProvider):
    def sanitize_prompt(self, prompt: str) -> str:
        sanitized = prompt
        for target, replacement in PRE_SAFETY_SANITIZATION_MAP.items():
            pattern = re.compile(rf"\b{re.escape(target)}\b", re.IGNORECASE)
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def simplify_to_safe_prompt(self, prompt: str, style_prefix: str = "") -> str:
        """
        Simplify a prompt that triggered a safety block, then re-inject
        the style-specific prefix so monochrome/art-style tokens are preserved.
        style_prefix should be the full SDXL_STYLE_TEMPLATES prefix string.
        """
        sanitized = prompt
        fallback_map = {
            "disputes": "stands near",
            "dispute": "stands near",
            "disagreement": "meeting",
            "betrayal": "meeting",
            "betray": "meet",
            "confronts": "stands near",
            "confront": "meets",
            "tension rises": "calm scene",
            "tension": "calm",
            "back down": "stand still",
            "accuses": "stands near",
            "accuse": "stands near",
            "clash": "meet",
            "collided": "met",
            "fighting": "standing",
            "fight": "stand",
            "battlefield": "ruined field",
            "battle": "scene",
            "swords collide": "holding swords",
            "collide": "meet"
        }
        for target, replacement in fallback_map.items():
            pattern = re.compile(rf"\b{re.escape(target)}\b", re.IGNORECASE)
            sanitized = pattern.sub(replacement, sanitized)
        sanitized += ", calm expression, peaceful atmosphere, high quality"
        # Re-inject style prefix so art-style tokens (monochrome, screentone, etc.)
        # survive the safety simplification step.
        if style_prefix and style_prefix.strip():
            sanitized = f"{sanitized}, {style_prefix.strip()}"
        return sanitized

    def __init__(self, api_key: str = None):
        """
        Initializes the Fal AI image provider.
        """
        self.api_key = api_key or os.environ.get("FAL_KEY")
        if self.api_key:
            os.environ["FAL_KEY"] = self.api_key
        self.character_seeds = {}
        import threading
        self.seed_lock = threading.Lock()
        
        # Cost Tracking V2 fields
        self.job_metrics = {}
        self.metrics_lock = threading.Lock()
        self.risk_analyzer = PromptRiskAnalyzer(threshold=3)

    def get_and_clear_job_metrics(self, job_id: str) -> list:
        with self.metrics_lock:
            return self.job_metrics.pop(job_id, [])

    def create_base_latents(self, seed: int = 42):
        """
        Fal AI API does not consume raw base noise latents directly.
        Returns None.
        """
        return None

    def generate_image(
        self,
        positive_prompt: str,
        negative_prompt: str,
        output_path: str,
        seed: int = 42,
        reference_image_path: str = None,
        reference_strength: float = None,
        base_latents=None,
        scene_id: int = 1,
        panel_index: int = 0,
        style: str = None,
        action: str = "",
        panel_count: int = None,
        layout_type: str = None,
        panel_width: int = 768,
        panel_height: int = 1024,
        focus_character: str = "",
        secondary_character: str = "",
        job_id: str = "",
        color_mode: str = "auto",
    ) -> str:
        """
        Generates an image via the fal.ai API using fal_client.
        Falls back to local StableDiffusionImageProvider on any API error.
        """
        from core.prompt_builder import resolve_monochrome
        monochrome = resolve_monochrome(color_mode, style)
        actual_submissions = 0
        actual_request_ids = []
        actual_safety_retries = 0
        actual_network_retries = 0
        actual_reroutes = 0
        estimated_request_cost = 0.0
        panel_start_time = time.time()
        
        # Determine defaults for style and config inside try block
        style_key = style.lower() if style else "anime"
        if style_key not in STYLE_MODEL_MAP:
            style_key = "anime"
        model_config = STYLE_MODEL_MAP[style_key]
        current_endpoint = model_config["endpoint"]
        current_model_log_name = model_config.get("model_name") or current_endpoint

        try:
            import fal_client

            # Ensure API key is set for client authentication
            if not os.environ.get("FAL_KEY"):
                raise ValueError("FAL_KEY environment variable is not set")

            # When panel is single page format
            if panel_count == 1:
                w, h = 1024, 1450
            else:
                # Fix 1: Round to nearest 64 pixels (SDXL requirement), clamping to [512, 1536]
                w = int(round(panel_width / 64.0) * 64)
                h = int(round(panel_height / 64.0) * 64)
                w = max(512, min(1536, w))
                h = max(512, min(1536, h))

            # Fix 2: Seed logic (Thread-safe)
            char_key = focus_character.strip().lower() if focus_character else "default"
            char_pair_key = f"{char_key}_{secondary_character.strip().lower()}" if secondary_character else None

            import hashlib
            offset = 0
            if secondary_character:
                offset = int(hashlib.md5(secondary_character.strip().lower().encode('utf-8')).hexdigest(), 16) % 1000

            with self.seed_lock:
                if char_pair_key and char_pair_key in self.character_seeds:
                    panel_seed = self.character_seeds[char_pair_key]
                    primary_seed = self.character_seeds.get(char_key, panel_seed - offset)
                    print(f"[FalAI] 2-character panel seed: {panel_seed} (primary: {primary_seed}, secondary_offset: {offset})")
                elif char_key in self.character_seeds:
                    primary_seed = self.character_seeds[char_key]
                    if secondary_character:
                        combined_seed = primary_seed + offset
                        self.character_seeds[char_pair_key] = combined_seed
                        panel_seed = combined_seed
                        print(f"[FalAI] 2-character panel seed: {combined_seed} (primary: {primary_seed}, secondary_offset: {offset})")
                    else:
                        panel_seed = primary_seed + (panel_index * 100)
                elif "default" in self.character_seeds:
                    primary_seed = self.character_seeds["default"]
                    if secondary_character:
                        combined_seed = primary_seed + offset
                        self.character_seeds[char_pair_key] = combined_seed
                        panel_seed = combined_seed
                        print(f"[FalAI] 2-character panel seed: {combined_seed} (primary: {primary_seed}, secondary_offset: {offset})")
                    else:
                        panel_seed = primary_seed + (panel_index * 100)
                else:
                    if panel_index == 0:
                        panel_seed = None  # let API choose
                    else:
                        primary_seed = seed
                        if secondary_character:
                            combined_seed = primary_seed + offset
                            self.character_seeds[char_pair_key] = combined_seed
                            panel_seed = combined_seed
                            print(f"[FalAI] 2-character panel seed: {combined_seed} (primary: {primary_seed}, secondary_offset: {offset})")
                        else:
                            panel_seed = primary_seed + (panel_index * 100)

            # Set up parameters
            is_shared_frame = is_shared_frame_panel(focus_character, secondary_character, action)
            image_urls = []

            # --- Tiered routing decision (config-driven) --------------------------
            routing_mode = getattr(settings, "IMAGE_ROUTING_MODE", "nano_all")
            premium_model = getattr(settings, "PREMIUM_IMAGE_MODEL", "fal-ai/nano-banana/edit")
            if routing_mode == "pro_shared":
                premium_model = "fal-ai/nano-banana-pro/edit"

            # Cinematic & realistic MUST render on their dedicated SDXL models
            # (filmic / photoreal) which actually follow the scene prompt — never the
            # anime reference-editor, which forces an anime look and ignores the
            # setting/action. So they always bypass the premium nano edit.
            photoreal_style = style_key in ("cinematic", "realistic")

            if routing_mode == "sdxl_only" or photoreal_style:
                # No reference conditioning: straight text-to-image on the style's
                # model, so the prompt (setting/action/style) drives the result.
                use_premium = False
            elif routing_mode in ("hybrid", "pro_shared"):
                # Premium only for shared (multi-character) frames.
                use_premium = is_shared_frame
            else:  # "nano_all" — any panel with a named character is reference-conditioned.
                use_premium = bool(focus_character or secondary_character)
            premium_chars = [focus_character, secondary_character]

            # Soft per-job cost guardrail: stop using the premium model once this job's
            # estimated spend reaches the cap, so one comic can't runaway-spend.
            if use_premium and job_id:
                cap = getattr(settings, "MAX_COST_PER_JOB", 0.60)
                with self.metrics_lock:
                    spent_so_far = sum(m.get("estimated_request_cost", 0.0)
                                       for m in self.job_metrics.get(job_id, []))
                if spent_so_far >= cap:
                    print(f"[FalAI] Job cost cap (${cap:.2f}) reached (${spent_so_far:.3f}) — "
                          f"using cheap SDXL for this panel.")
                    use_premium = False

            if use_premium:
                print(f"[FalAI] Routing to reference-conditioned model {premium_model} (mode={routing_mode}).")
                # We need a VALIDATED reference portrait for each character in frame.
                ref_dir = os.path.join(os.path.dirname(output_path), "references")
                os.makedirs(ref_dir, exist_ok=True)

                for char_name in premium_chars:
                    if not char_name:
                        continue
                    ref_img_path = os.path.join(ref_dir, f"{char_name.lower()}_ref.png")
                    ref_url_path = os.path.join(ref_dir, f"{char_name.lower()}_ref.url")

                    # 1) Reuse a cached reference ONLY if the cached image is still valid.
                    #    A previously cached blank/black portrait must not poison this job.
                    char_url = None
                    if os.path.exists(ref_img_path) and os.path.exists(ref_url_path):
                        if is_valid_portrait(ref_img_path):
                            try:
                                with open(ref_url_path, "r", encoding="utf-8") as url_f:
                                    char_url = url_f.read().strip()
                            except Exception as url_err:
                                print(f"[FalAI Warning] Failed to read cached URL for {char_name}: {url_err}")
                        else:
                            print(f"[FalAI Warning] Cached reference for {char_name} is blank/invalid — discarding and regenerating.")
                            for stale in (ref_img_path, ref_url_path):
                                try:
                                    os.remove(stale)
                                except OSError:
                                    pass

                    if char_url:
                        image_urls.append(char_url)
                        print(f"[FalAI] Found valid cached reference image URL for {char_name}: {char_url}")
                        continue

                    # 2) Generate the reference portrait, validating the result.
                    #    Up to 2 attempts: original + one fresh-seed retry on a blank/invalid frame.
                    print(f"[FalAI] Reference portrait not cached. Generating for {char_name}...")
                    sheet = get_character_sheet(char_name, job_id)
                    portrait_prompt = build_portrait_prompt(char_name, sheet)
                    valid_ref = False
                    for gen_attempt in range(2):
                        portrait_args = {
                            "prompt": portrait_prompt,
                            "negative_prompt": negative_prompt,
                            "image_size": {
                                "width": 1024,
                                "height": 1024,
                            },
                            "num_inference_steps": 25,
                            "model_name": "cagliostrolab/animagine-xl-3.1"
                        }
                        if gen_attempt > 0:
                            # Fresh random seed to escape a deterministic safety block.
                            import random
                            portrait_args["seed"] = random.randint(1, 2_000_000_000)
                            print(f"[FalAI] Retrying reference portrait for {char_name} with a fresh seed...")

                        portrait_req_id = None
                        for attempt in range(3):
                            try:
                                handler = fal_client.submit("fal-ai/fast-sdxl", portrait_args)
                                portrait_req_id = handler.request_id
                                actual_submissions += 1
                                actual_request_ids.append(portrait_req_id)
                                estimated_request_cost += 0.0025
                                break
                            except Exception as e:
                                print(f"[FalAI Warning] Portrait submit attempt {attempt + 1} failed: {e}")
                                if attempt == 2:
                                    raise e
                                time.sleep(2)

                        if not portrait_req_id:
                            raise ValueError(f"Failed to submit reference portrait for {char_name}")

                        # Poll portrait
                        poll_start = time.time()
                        p_result = None
                        while time.time() - poll_start < 180:
                            status_info = fal_client.status("fal-ai/fast-sdxl", portrait_req_id)
                            if isinstance(status_info, fal_client.Completed):
                                p_result = fal_client.result("fal-ai/fast-sdxl", portrait_req_id)
                                break
                            time.sleep(2)

                        if not p_result or "images" not in p_result or len(p_result["images"]) == 0:
                            raise ValueError(f"Failed to generate reference portrait for {char_name}")

                        portrait_url = p_result["images"][0]["url"]

                        # Download portrait
                        resp = httpx.get(portrait_url, timeout=45)
                        resp.raise_for_status()
                        with open(ref_img_path, "wb") as f:
                            f.write(resp.content)

                        # 2a) VALIDATE before caching/using. A blank/black frame is a
                        #     silent safety block — never anchor a premium edit on it.
                        if is_valid_portrait(ref_img_path):
                            valid_ref = True
                            break
                        print(f"[FalAI Warning] Reference portrait for {char_name} came back blank/invalid (attempt {gen_attempt + 1}).")

                    if not valid_ref:
                        # 3) Graceful fallback: do NOT anchor a premium edit on a broken
                        #    reference. Downgrade this panel to a standard SDXL render
                        #    (cheaper, and avoids the two-different-people failure).
                        print(f"[FalAI Warning] No valid reference for {char_name} after 2 attempts — "
                              f"falling back to SDXL render (skipping premium reference routing).")
                        try:
                            if os.path.exists(ref_img_path):
                                os.remove(ref_img_path)
                        except OSError:
                            pass
                        use_premium = False
                        image_urls = []
                        break

                    # 4) Cache the validated reference and upload to fal CDN.
                    cdn_url = fal_client.upload_file(ref_img_path)
                    with open(ref_url_path, "w", encoding="utf-8") as url_f:
                        url_f.write(cdn_url)

                    image_urls.append(cdn_url)
                    print(f"[FalAI] Generated and uploaded VALID reference portrait for {char_name}: {cdn_url}")

            # Configure routing AFTER reference acquisition: only use the premium edit
            # endpoint if we still hold valid references (the loop above may have
            # downgraded use_premium to False on a failed reference).
            if use_premium and image_urls:
                current_endpoint = premium_model
                current_model_log_name = premium_model
                current_model_config = {"endpoint": premium_model}
            else:
                use_premium = False
                # Handle character consistency / reference image for single character panels
                if reference_image_path and os.path.exists(reference_image_path):
                    # Upload the local reference image to fal.ai CDN to get public URL
                    image_url = fal_client.upload_file(reference_image_path)

            # Call the fal.ai API endpoint synchronously with internal safety retry loop
            current_seed = panel_seed
            from ssl import SSLError
            network_exceptions = (httpx.HTTPError, httpx.TimeoutException, httpx.NetworkError, SSLError, TimeoutError, ConnectionError)

            current_prompt = positive_prompt
            current_model_config = model_config if not use_premium else current_model_config

            # Amendment 2: Prompt Risk Scoring
            score, should_sanitize = self.risk_analyzer.analyze(current_prompt)
            if should_sanitize:
                current_prompt = self.sanitize_prompt(current_prompt)
                print(f"[RiskAnalyzer] Score: {score} — Pre-sanitization applied")

            for safety_attempt in range(3):
                # Setup parameters dynamically depending on endpoint
                if current_endpoint.startswith("fal-ai/nano-banana"):
                    # Reference-conditioned edit endpoints (nano-banana / nano-banana-pro).
                    arguments = {
                        "prompt": current_prompt,
                        "image_urls": image_urls,
                        "num_images": 1
                    }
                elif current_endpoint.startswith("fal-ai/flux"):
                    # FLUX text-to-image (dev / schnell / pro). FLUX does NOT accept
                    # negative_prompt or model_name; it follows the positive prompt and
                    # honours monochrome tokens natively (manga comes out true B&W).
                    arguments = {
                        "prompt": current_prompt,
                        "image_size": {"width": w, "height": h},
                        "num_inference_steps": 4 if "schnell" in current_endpoint else 28,
                        "num_images": 1,
                        "enable_safety_checker": False,
                    }
                    if current_seed is not None:
                        arguments["seed"] = current_seed
                else:
                    arguments = {
                        "prompt": current_prompt,
                        "negative_prompt": negative_prompt,
                        "image_size": {
                            "width": w,
                            "height": h,
                        },
                        "num_inference_steps": getattr(settings, "SD_INFERENCE_STEPS", 25)
                    }
                    if current_seed is not None:
                        arguments["seed"] = current_seed
                    if "model_name" in current_model_config:
                        arguments["model_name"] = current_model_config["model_name"]
                    
                    if not use_premium and reference_image_path and os.path.exists(reference_image_path):
                        if 'image_url' in locals():
                            if style_key == "realistic":
                                arguments["control_image_url"] = image_url
                                if reference_strength is not None:
                                    arguments["controlnet_conditioning_scale"] = reference_strength
                            else:
                                arguments["image_url"] = image_url
                                if reference_strength is not None:
                                    arguments["strength"] = reference_strength

                print(f"[FalAI] Submitting API request — model: {current_model_log_name}, size: {w}x{h}")
                
                # Amendment 2 & 3: Submit and Poll to prevent duplicate billing
                request_id = None
                for attempt in range(3):
                    try:
                        handler = fal_client.submit(current_endpoint, arguments)
                        request_id = handler.request_id
                        actual_request_ids.append(request_id)
                        actual_submissions += 1
                        
                        # Add cost based on the endpoint we submitted to
                        if current_endpoint == "fal-ai/nano-banana-pro/edit":
                            cost_rate = 0.15
                        elif current_endpoint == "fal-ai/nano-banana/edit":
                            cost_rate = 0.039
                        elif current_endpoint == "fal-ai/realistic-vision":
                            cost_rate = 0.039
                        elif current_endpoint.startswith("fal-ai/flux-pro"):
                            cost_rate = 0.05
                        elif current_endpoint == "fal-ai/flux/dev":
                            cost_rate = 0.025
                        elif current_endpoint == "fal-ai/flux/schnell":
                            cost_rate = 0.003
                        else:
                            cost_rate = 0.0025
                        estimated_request_cost += cost_rate
                        break
                    except network_exceptions as e:
                        actual_network_retries += 1
                        print(f"[FalAI Warning] Submit attempt {attempt + 1} failed: {e}")
                        if attempt == 2:
                            raise e
                        else:
                            time.sleep(2)
                            continue

                if not request_id:
                    raise ValueError("Failed to submit request and retrieve a request_id from fal.ai")

                # Poll status
                poll_start = time.time()
                timeout = 180
                result = None
                while time.time() - poll_start < timeout:
                    try:
                        status_info = fal_client.status(current_endpoint, request_id)
                        if isinstance(status_info, fal_client.Completed):
                            # Retrieve the result, retry on network error
                            for attempt in range(3):
                                try:
                                    result = fal_client.result(current_endpoint, request_id)
                                    break
                                except network_exceptions as e:
                                    actual_network_retries += 1
                                    print(f"[FalAI Warning] Result retrieval attempt {attempt + 1} failed: {e}")
                                    if attempt == 2:
                                        raise e
                                    time.sleep(2)
                            break
                        elif isinstance(status_info, fal_client.Queued) or isinstance(status_info, fal_client.InProgress):
                            # Job is still in queue or processing, keep waiting
                            pass
                        else:
                            raise ValueError(f"Fal AI job failed with unknown status type: {type(status_info)}")
                        time.sleep(2)
                    except network_exceptions as e:
                        actual_network_retries += 1
                        print(f"[FalAI Warning] Network error while polling status: {e}. Retrying status check...")
                        time.sleep(2)
                        continue

                if not result or "images" not in result or len(result["images"]) == 0:
                    raise ValueError("Empty image response from fal.ai API")

                # Retrieve the seed actually used by fal.ai
                actual_seed = result.get("seed")
                seed_source = "api_response"
                
                if actual_seed is None:
                    # Fallback: hash of focus_character + job_id
                    import hashlib
                    combined_str = f"{focus_character}_{job_id}_{scene_id}_{panel_index}"
                    actual_seed = int(hashlib.md5(combined_str.encode('utf-8')).hexdigest(), 16) % 1000000000
                    seed_source = "deterministic_fallback"
                    
                # Cache the seed on panel 1 (panel_index == 0)
                if panel_index == 0:
                    with self.seed_lock:
                        if secondary_character:
                            primary_seed = actual_seed - offset
                            self.character_seeds[char_key] = primary_seed
                            self.character_seeds[char_pair_key] = actual_seed
                            self.character_seeds["default"] = primary_seed
                            print(f"[FalAI] Character seed locked for {focus_character if focus_character else 'default'}: {primary_seed}")
                            print(f"[FalAI] 2-character panel seed: {actual_seed} (primary: {primary_seed}, secondary_offset: {offset})")
                        else:
                            self.character_seeds[char_key] = actual_seed
                            self.character_seeds["default"] = actual_seed
                            print(f"[FalAI] Character seed locked for {focus_character if focus_character else 'default'}: {actual_seed}")
                    
                print(f"[FalAI] Seed source: {seed_source}")

                generated_image_url = result["images"][0]["url"]

                # Download generated image and save to destination path with retry loop
                response_content = None
                for attempt in range(3):
                    try:
                        response = httpx.get(generated_image_url, timeout=45)
                        response.raise_for_status()
                        response_content = response.content
                        break
                    except network_exceptions as e:
                        actual_network_retries += 1
                        print(f"[FalAI Warning] Image download attempt {attempt + 1} failed: {e}")
                        if attempt == 2:
                            raise e
                        else:
                            time.sleep(2)
                            continue

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response_content)

                # Validate image is not black (safety filter trigger)
                is_black = False
                try:
                    with Image.open(output_path) as img:
                        extrema = img.convert("L").getextrema()
                        # If the max value is extremely dark (max < 10), it is a safety block
                        if extrema[1] < 10:
                            is_black = True
                except Exception as img_err:
                    print(f"[FalAI Warning] Image inspection failed: {img_err}")
                    is_black = True

                if is_black:
                    if safety_attempt == 0:
                        actual_safety_retries += 1
                        # Apply prompt sanitization
                        print(f"[FalAI Warning] Safety filter triggered (black image) on seed {actual_seed}. Retrying with sanitized prompt...")
                        current_prompt = self.sanitize_prompt(current_prompt)
                        current_seed = (actual_seed + 1234) % 1000000000
                        continue
                    elif safety_attempt == 1:
                        actual_reroutes += 1
                        # Reroute model to animagine-xl-3.1 and simplify prompt to safe fallback.
                        # FIX: pass the active style prefix so monochrome/art-style tokens
                        # are preserved in the simplified prompt instead of being discarded.
                        print(f"[FalAI Warning] Safety block persisted. Rerouting to cagliostrolab/animagine-xl-3.1 with style-preserving simplified prompt...")
                        # Determine style prefix for re-injection
                        from core.prompt_builder import SDXL_STYLE_TEMPLATES, STYLE_TEMPLATES
                        from config import settings as _settings
                        _is_sdxl = getattr(_settings, "IMAGE_PROVIDER", "") == "fal_ai"
                        _templates = SDXL_STYLE_TEMPLATES if _is_sdxl else STYLE_TEMPLATES
                        _style_key = (style or "anime").lower()
                        _style_prefix = _templates.get(_style_key, {}).get("prefix", "")
                        current_prompt = self.simplify_to_safe_prompt(current_prompt, style_prefix=_style_prefix)
                        current_endpoint = "fal-ai/fast-sdxl"
                        current_model_config = {
                            "endpoint": "fal-ai/fast-sdxl",
                            "model_name": "cagliostrolab/animagine-xl-3.1"
                        }
                        current_model_log_name = "cagliostrolab/animagine-xl-3.1"
                        current_seed = (actual_seed + 5678) % 1000000000
                        continue
                    else:
                        raise ValueError("Safety filter triggered on all retry attempts; generated image is black")

                # If we reached here, the image is valid (not black)
                break

            # If the resolved colour mode is monochrome, convert the image to
            # greyscale to override any model/IP-Adapter colour bias.
            # Skip PIL grayscale post-processing (stopgap) for nano-banana edit
            # panels — they produce native monochrome from the prompt tokens.
            if monochrome and not current_endpoint.startswith("fal-ai/nano-banana"):
                try:
                    with Image.open(output_path) as img:
                        grayscale_img = img.convert("L").convert("RGB")
                        grayscale_img.save(output_path)
                    print(f"[FalAI] Successfully converted {output_path} to grayscale (color_mode={color_mode}).")
                except Exception as grayscale_err:
                    print(f"[FalAI Warning] Failed to convert image to grayscale: {grayscale_err}")

            # Cost tracking log & Save Metrics V2
            duration = time.time() - panel_start_time
            panel_metrics = {
                "actual_submissions": actual_submissions,
                "actual_request_ids": actual_request_ids,
                "actual_safety_retries": actual_safety_retries,
                "actual_network_retries": actual_network_retries,
                "actual_reroutes": actual_reroutes,
                "actual_endpoint": current_endpoint,
                "actual_model": current_model_log_name,
                "generation_duration": int(duration),
                "estimated_request_cost": estimated_request_cost,
                "style": style,
                "model": current_model_log_name
            }
            if job_id:
                with self.metrics_lock:
                    if job_id not in self.job_metrics:
                        self.job_metrics[job_id] = []
                    self.job_metrics[job_id].append(panel_metrics)

            print(f"[FalAI] Panel generated — model: {current_model_log_name}, estimated cost: ${estimated_request_cost:.4f}")
            
            # Double check that the final saved image exists and is valid
            if not os.path.exists(output_path):
                raise ValueError("Generated image file does not exist")
            if os.path.getsize(output_path) < 1024:
                raise ValueError("Generated image file is empty or too small")
            with Image.open(output_path) as img:
                extrema = img.convert("L").getextrema()
                if extrema[1] < 10:
                    raise ValueError("Safety filter triggered: final output image is black")
                    
            return output_path

        except Exception as error:
            # Record metrics even on exception to log cost of requests made before failure
            duration = time.time() - panel_start_time
            panel_metrics = {
                "actual_submissions": actual_submissions,
                "actual_request_ids": actual_request_ids,
                "actual_safety_retries": actual_safety_retries,
                "actual_network_retries": actual_network_retries,
                "actual_reroutes": actual_reroutes,
                "actual_endpoint": current_endpoint,
                "actual_model": current_model_log_name,
                "generation_duration": int(duration),
                "estimated_request_cost": estimated_request_cost,
                "style": style,
                "model": current_model_log_name
            }
            if job_id:
                with self.metrics_lock:
                    if job_id not in self.job_metrics:
                        self.job_metrics[job_id] = []
                    self.job_metrics[job_id].append(panel_metrics)

            if "Safety filter" in str(error):
                print(f"[FalAI Critical] Safety filter block: {error}")
                raise error
            # Fall back to local StableDiffusionImageProvider gracefully.
            # In the cloud image torch/diffusers aren't installed (Groq+fal only),
            # so this import can fail — surface the original fal error in that case
            # rather than a confusing ImportError, so the job fails cleanly + refunds.
            print(f"[FalAI] API call failed: {error} — falling back to local SD")
            try:
                from providers.image.stable_diffusion import StableDiffusionImageProvider
            except Exception as import_err:
                print(f"[FalAI] Local SD fallback unavailable ({import_err}); re-raising fal error.")
                raise error
            local_provider = StableDiffusionImageProvider()
            return local_provider.generate_image(
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                output_path=output_path,
                seed=seed,
                reference_image_path=reference_image_path,
                reference_strength=reference_strength,
                base_latents=base_latents,
                scene_id=scene_id,
                panel_index=panel_index,
                style=style,
                action=action,
                panel_count=panel_count,
                layout_type=layout_type,
                focus_character=focus_character,
                secondary_character=secondary_character,
                job_id=job_id,
            )

    def extract_character_anchor(self, image_path: str, output_path: str) -> str:
        """
        Extracts character reference anchor from an image locally using PIL and saves it to output_path.
        """
        image  = Image.open(image_path).convert("RGB")
        w, h   = image.size
        cw, ch = int(w * 0.60), int(h * 0.80)
        l      = max((w - cw) // 2, 0)
        t      = max((h - ch) // 2, 0)
        anchor = image.crop((l, t, min(l + cw, w), min(t + ch, h))).resize(
            (getattr(settings, "SD_WIDTH", 512), getattr(settings, "SD_HEIGHT", 512)), Image.Resampling.LANCZOS
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        anchor.save(output_path)
        return output_path

    def unload_model(self):
        """
        No-op for API-based provider.
        """
        print("[FalAIImageProvider] Unloading model (no-op for API)")
