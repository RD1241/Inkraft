import os
from dotenv import load_dotenv

# Load .env from project root before reading any env vars
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=_env_path, override=False)

# --- DYNAMIC ROUTING FOR FAL.AI ---
FAL_KEY = os.environ.get("FAL_KEY")
FAL_AI_ENABLED = bool(FAL_KEY) and FAL_KEY != "your_fal_api_key_here"
IMAGE_PROVIDER = "fal_ai" if FAL_AI_ENABLED else "stable_diffusion"
os.environ["IMAGE_PROVIDER"] = IMAGE_PROVIDER

# --- IMAGE ROUTING (tiered model selection) ---
# IMAGE_ROUTING_MODE:
#   "flux_all"   -> every panel is straight text-to-image on the style's model (FLUX
#                   dev by default). The 2026-06-28 QA bake-off + a real Kael/Elena
#                   manga page showed FLUX follows the prompt far better than the nano
#                   reference-editor AND keeps Vault characters consistent (strong
#                   identity tokens + seed-lock), at lower cost ($0.025 vs $0.039).
#                   (default)  ["sdxl_only"/"text_to_image" are aliases.]
#   "nano_all"   -> every panel with a named character uses the reference-conditioned
#                   premium model (PREMIUM_IMAGE_MODEL). Reference-anchored consistency,
#                   but the portrait is anime-biased and it ignores setting/action more.
#   "hybrid"     -> only shared-frame (multi-character) panels use the premium model;
#                   single-character panels stay on cheap text-to-image.
#   "pro_shared" -> only shared frames, forced onto nano-banana-pro (max quality).
IMAGE_ROUTING_MODE = os.environ.get("IMAGE_ROUTING_MODE", "flux_all")
PREMIUM_IMAGE_MODEL = os.environ.get("PREMIUM_IMAGE_MODEL", "fal-ai/nano-banana/edit")
# Soft per-job spend guardrail: once a job's estimated fal.ai cost reaches this,
# remaining panels fall back to cheap SDXL so one comic can't runaway-spend.
# NOTE: keep this ABOVE the cost of a full-quality comic (≈ MAX_PANELS_PER_COMIC ×
# $0.039 + overhead) so it never downgrades a legitimate comic to SDXL — it is a
# runaway/abuse guard, not a quality knob. Lowering it trades quality, not just cost.
MAX_COST_PER_JOB = float(os.environ.get("MAX_COST_PER_JOB", "0.60"))

# Hard cap on panels per comic. The UI only offers up to 6 and the AI-decided
# planner also tops out at 6, so this purely closes the one runway leak: a direct
# API call requesting panel_count 7–10 (≈ $0.27–$0.39 on a single credit). Bounding
# it is quality-neutral (limits panel COUNT, never per-panel render quality) and is
# env-tunable so a future paid tier can raise it.
MAX_PANELS_PER_COMIC = int(os.environ.get("MAX_PANELS_PER_COMIC", "6"))

# --- CREDIT PRICING (panel-count tiers) ---
# Credits charged per comic scale with panel count so credits track real fal.ai
# cost (≈ $0.039/panel) without ever lowering render quality. Tiers are
# "maxpanels:credits" pairs; a comic is charged the first tier whose maxpanels it
# fits. AI-decided panel count (panel_count None/0) is charged CREDITS_AI_DEFAULT.
# All env-tunable so pricing can change without a code edit.
NEW_USER_CREDITS = int(os.environ.get("NEW_USER_CREDITS", "5"))
CREDITS_AI_DEFAULT = int(os.environ.get("CREDITS_AI_DEFAULT", "2"))


def _parse_credit_tiers(raw: str):
    tiers = []
    for part in (raw or "").split(","):
        part = part.strip()
        if ":" in part:
            mp, c = part.split(":", 1)
            try:
                tiers.append((int(mp), int(c)))
            except ValueError:
                continue
    return sorted(tiers) or [(2, 1), (4, 2), (6, 3)]


# Default: 1-2 panels = 1 credit, 3-4 = 2, 5-6 = 3.
CREDIT_PANEL_TIERS = _parse_credit_tiers(os.environ.get("CREDIT_PANEL_TIERS", "2:1,4:2,6:3"))

# --- BASE DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DATA_DIR: persistent-storage root. On a host with a mounted volume (e.g. Railway
# at /data) set DATA_DIR=/data so ALL SQLite DBs + generated outputs live on the
# volume and survive container restarts/redeploys. Unset (local dev) keeps the
# existing in-repo locations so nothing moves and existing data is untouched.
DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR:
    DB_DIR = os.path.join(DATA_DIR, "db")
    OUTPUTS_DIR = os.path.join(DATA_DIR, "outputs")
    LOGS_DIR = os.path.join(DATA_DIR, "logs")
else:
    DB_DIR = os.path.join(BASE_DIR, "core")
    OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")

# SQLite will not create missing parent dirs — ensure the DB dir exists up front.
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "character_memory.db")


# --- ENVIRONMENT & HARDWARE ---
HF_HOME = "D:\\AI_Models\\HuggingFace"
os.environ["HF_HOME"]               = HF_HOME
os.environ["HF_HUB_CACHE"]          = HF_HOME   # ensure both vars point to D drive
os.environ["HUGGINGFACE_HUB_CACHE"] = HF_HOME
HF_TOKEN = os.environ.get("HF_TOKEN", None)

# --- OLLAMA PATH (must be set before any ollama import) ---
OLLAMA_MODELS_PATH = "D:\\AI_Models\\Ollama"
os.environ["OLLAMA_MODELS"] = OLLAMA_MODELS_PATH

# --- LLM SETTINGS (Ollama) ---
LLM_MODEL      = "llama3"
OLLAMA_HOST    = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
LLM_KEEP_ALIVE = "15s"  # Keep alive briefly for retries, then drop from VRAM for SD

# --- STABLE DIFFUSION SETTINGS ---
SD_MODEL_ID = "Lykon/dreamshaper-8"
SD_INFERENCE_STEPS = 25
SD_GUIDANCE_SCALE = 7.5
SD_DEFAULT_SEED = 42
SD_WIDTH = 512
SD_HEIGHT = 512

# --- STYLE & MULTI-MODEL ROUTING ---
# All models cached in HF_HOME on D drive. load_model() downloads once if missing.
DEFAULT_STYLE = "anime"
MODEL_MAP = {
    # SD 1.5 models — all cached in D:\AI_Models\HuggingFace
    # Style aesthetics are prompt-driven; one model handles all styles cleanly.
    "anime":     "Lykon/dreamshaper-8",
    "manga":     "Lykon/dreamshaper-8",          # manga look via prompt tokens
    "manhwa":    "Lykon/dreamshaper-8",          # manhwa look via prompt tokens
    "realistic": "SG161222/Realistic_Vision_V5.1_noVAE",
    # SDXL — larger, needs more VRAM, no ControlNet/IP-Adapter support
    "cinematic": "stabilityai/stable-diffusion-xl-base-1.0",
}
SD_REFERENCE_STRENGTH = 0.45
SD_IP_ADAPTER_MODEL_ID = "h94/IP-Adapter"
SD_IP_ADAPTER_SUBFOLDER = "models"
SD_IP_ADAPTER_WEIGHT_NAME = "ip-adapter_sd15.bin"
SD_IP_ADAPTER_ALWAYS_ON = True
SD_IP_ADAPTER_WEIGHT = 0.80

SD_CONTROLNET_ENABLED = True
SD_CONTROLNET_MODEL_ID = "lllyasviel/control_v11p_sd15_openpose"
SD_CONTROLNET_CONDITIONING_SCALE = 0.70

# --- PROMPT SETTINGS ---
MASTER_STYLE_TAG = "masterpiece, highly detailed, dramatic cinematic lighting, vibrant colors, anime style, comic book panel"
PROMPT_NEGATIVE = (
    "nsfw, naked, nude, nipples, breasts, cleavage, suggestive, explicit, "
    "duplicate character, two people, extra limbs, deformed hands, "
    "bad anatomy, extra fingers, fused fingers, blurry, "
    "low quality, worst quality, watermark, text, signature, "
    "inconsistent outfit, gender swap, extra person"
)

# --- SYSTEM & RELIABILITY ---
# Concurrent comic jobs processed in parallel (generation is API-bound on fal.ai,
# not GPU-bound). 4 is plenty for a small beta; bump via env for open beta.
CONCURRENT_WORKERS = int(os.environ.get("CONCURRENT_WORKERS", "4"))
MAX_RETRIES = 2
ENABLE_CACHING = False
MIN_INPUT_LENGTH = 20
MAX_INPUT_LENGTH = 3000

# --- SUPABASE CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")

# --- WATERMARK SETTINGS ---
WATERMARK_TEXT = "Inkraft.ai"
