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
#   "nano_all"   -> every panel with a named character uses the reference-conditioned
#                   premium model (PREMIUM_IMAGE_MODEL). Best quality + consistency; SDXL
#                   is only the automatic fallback. (default)
#   "hybrid"     -> only shared-frame (multi-character) panels use the premium model;
#                   single-character panels stay on cheap SDXL.
#   "pro_shared" -> only shared frames, forced onto nano-banana-pro (max quality).
IMAGE_ROUTING_MODE = os.environ.get("IMAGE_ROUTING_MODE", "nano_all")
PREMIUM_IMAGE_MODEL = os.environ.get("PREMIUM_IMAGE_MODEL", "fal-ai/nano-banana/edit")
# Soft per-job spend guardrail: once a job's estimated fal.ai cost reaches this,
# remaining panels fall back to cheap SDXL so one comic can't runaway-spend.
MAX_COST_PER_JOB = float(os.environ.get("MAX_COST_PER_JOB", "0.60"))

# --- BASE DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
DB_PATH = os.path.join(BASE_DIR, "core", "character_memory.db")


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
