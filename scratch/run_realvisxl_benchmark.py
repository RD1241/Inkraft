"""
run_realvisxl_benchmark.py
Phase 0 - RealVisXL V4.0 vs fal-ai/realistic-vision benchmark.
Generates identical scenes using both models and saves results for manual comparison.
"""
import os
import sys
import json
import time
import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from config import settings
except Exception:
    settings = None

try:
    import fal_client
    FAL_AVAILABLE = True
except ImportError:
    FAL_AVAILABLE = False
    print("[WARN] fal_client not installed. Running in report-only mode.")

OUTPUT_DIR = os.path.join(project_root, "outputs", "v3_validation", "benchmark_realistic")
os.makedirs(os.path.join(OUTPUT_DIR, "current_model"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "realvisxl"), exist_ok=True)

# V3 Dedicated SDXL Realistic Style Template (Phase 0 requirement)
SDXL_REALISTIC_POSITIVE = (
    "RAW photo, photorealistic, professional photography, "
    "realistic lighting, highly detailed skin texture, "
    "natural skin pores, realistic shadows, natural proportions, "
    "depth of field, realistic textures, 8k resolution, "
    "sharp focus, professional color grading"
)
SDXL_REALISTIC_NEGATIVE = (
    "cartoon, anime, illustration, painting, drawing, sketch, "
    "unrealistic, fake, plastic skin, doll-like, CGI render, "
    "low quality, blurry, overexposed, bad anatomy, "
    "deformed, distorted, watermark, signature"
)

BENCHMARK_SCENES = [
    {
        "id": "portrait",
        "name": "Portrait Scene",
        "prompt": (
            "close-up portrait shot, CHARACTER_A: Kael, male adult, long silver hair, "
            "blue eyes, scar on left cheek, dark warrior cloak, athletic build, "
            "determined expression, piercing gaze, dramatic side lighting, shallow depth of field"
        ),
    },
    {
        "id": "dialogue",
        "name": "Dialogue Scene",
        "prompt": (
            "medium shot, over-the-shoulder, two characters facing each other, "
            "CHARACTER_A: Kael male adult silver hair blue eyes dark cloak | "
            "CHARACTER_B: King Aldric elderly white beard golden crown royal robes, "
            "grand throne room interior, torchlight, serious conversation"
        ),
    },
    {
        "id": "action",
        "name": "Action Scene",
        "prompt": (
            "dynamic low angle action shot, two fighters, crossed swords impact point, "
            "metal sparks, motion blur, dramatic foreshortening, "
            "CHARACTER_A: warrior silver hair dark cloak | CHARACTER_B: enemy commander black armor, "
            "battlefield background, dramatic combat lighting"
        ),
    },
    {
        "id": "emotional",
        "name": "Emotional Scene",
        "prompt": (
            "extreme close-up, hollow vacant eyes, dark under-eyes, head hanging low, "
            "streaming tears, red rimmed eyes, trembling lips, grief-stricken expression, "
            "CHARACTER_A: young woman long auburn hair green eyes torn dress, dim candlelight"
        ),
    },
    {
        "id": "environmental",
        "name": "Environmental Scene",
        "prompt": (
            "wide establishing shot, epic fantasy castle on cliff at sunset, "
            "dramatic clouds, golden hour light, deep atmospheric haze, "
            "ancient stone architecture, sweeping landscape, volumetric light rays"
        ),
    },
    {
        "id": "two_character",
        "name": "Two Character Scene",
        "prompt": (
            "medium shot, two characters standing together side by side, "
            "CHARACTER_A: Kael male adult silver hair blue eyes warrior cloak | "
            "CHARACTER_B: Elena female adult long auburn hair green eyes silver dress, "
            "warm candlelight interior, soft bokeh, emotional closeness"
        ),
    },
]


def get_fal_key():
    key = ""
    if settings:
        key = getattr(settings, "FAL_KEY", "") or ""
    return key or os.environ.get("FAL_KEY", "")


def generate_image(endpoint, model_name, scene, output_subdir, prefix):
    """Generate using a fal endpoint. Returns (path, elapsed_s, cost_usd)."""
    if not FAL_AVAILABLE:
        return None, 0.0, 0.0
    key = get_fal_key()
    if not key:
        print(f"  [SKIP] No FAL_KEY. Skipping {scene['name']} on {endpoint}")
        return None, 0.0, 0.0
    os.environ["FAL_KEY"] = key

    positive = f"masterpiece, best quality, {SDXL_REALISTIC_POSITIVE}, {scene['prompt']}"
    args = {
        "prompt": positive,
        "negative_prompt": SDXL_REALISTIC_NEGATIVE,
        "image_size": "portrait_4_3",
        "num_inference_steps": 30,
        "guidance_scale": 7.5,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    if model_name:
        args["model_name"] = model_name

    start = time.time()
    try:
        result = fal_client.subscribe(endpoint, arguments=args, with_logs=False)
        elapsed = time.time() - start
        if result and result.get("images"):
            url = result["images"][0]["url"]
            import urllib.request
            fname = f"{prefix}_{scene['id']}.png"
            fpath = os.path.join(OUTPUT_DIR, output_subdir, fname)
            urllib.request.urlretrieve(url, fpath)
            cost = 0.039 if "realistic-vision" in endpoint else 0.0025
            print(f"  [{endpoint}] {scene['name']} -> {fname} ({elapsed:.1f}s, ${cost})")
            return fpath, elapsed, cost
    except Exception as e:
        print(f"  [ERROR] {endpoint} / {scene['name']}: {e}")
    cost = 0.039 if "realistic-vision" in endpoint else 0.0025
    return None, time.time() - start, cost


def run_benchmark():
    print("=" * 60)
    print("PHASE 0 - RealVisXL V4.0 Benchmark")
    print("Current:   fal-ai/realistic-vision ($0.039/image)")
    print("Candidate: SG161222/RealVisXL_V4.0 via fal-ai/fast-sdxl (~$0.0025/image)")
    print("=" * 60)

    results = []
    total_curr = 0.0
    total_rxl = 0.0

    for scene in BENCHMARK_SCENES:
        print(f"\n--- {scene['name']} ---")
        curr_path, curr_t, curr_cost = generate_image(
            "fal-ai/realistic-vision", None, scene, "current_model", "current"
        )
        rxl_path, rxl_t, rxl_cost = generate_image(
            "fal-ai/fast-sdxl", "SG161222/RealVisXL_V4.0", scene, "realvisxl", "realvisxl"
        )
        total_curr += curr_cost
        total_rxl += rxl_cost
        results.append({
            "scene_id": scene["id"],
            "scene_name": scene["name"],
            "current_model": {
                "model": "fal-ai/realistic-vision",
                "path": curr_path,
                "time_s": round(curr_t, 2),
                "cost_usd": curr_cost,
            },
            "realvisxl": {
                "model": "SG161222/RealVisXL_V4.0 via fal-ai/fast-sdxl",
                "path": rxl_path,
                "time_s": round(rxl_t, 2),
                "cost_usd": rxl_cost,
            },
            "manual_scores": {
                "note": "Score 1-10 for each criterion after visual inspection",
                "criteria": [
                    "facial_quality", "character_consistency", "environment_quality",
                    "lighting_quality", "storytelling_quality", "commercial_quality"
                ],
                "current_model_scores": {},
                "realvisxl_scores": {},
            },
        })

    savings = round((1 - total_rxl / max(total_curr, 0.001)) * 100, 1)
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "benchmark": "Phase 0 - RealVisXL V4.0 vs realistic-vision",
        "total_scenes": len(BENCHMARK_SCENES),
        "cost_summary": {
            "current_model_total_usd": round(total_curr, 4),
            "realvisxl_total_usd": round(total_rxl, 4),
            "projected_savings_pct": savings,
        },
        "sdxl_realistic_template_used": SDXL_REALISTIC_POSITIVE[:80] + "...",
        "results": results,
        "output_dir": OUTPUT_DIR,
        "replacement_approved": None,  # Fill after manual review
        "scoring_guide": {
            "approved_if": "RealVisXL average score >= current model average score across all criteria",
            "rejected_if": "RealVisXL average score < current model average score"
        }
    }

    report_path = os.path.join(OUTPUT_DIR, "benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'=' * 60}")
    print("BENCHMARK COMPLETE")
    print(f"Cost: current=${total_curr:.4f} | RealVisXL=${total_rxl:.4f} | Savings={savings}%")
    print(f"Report: {report_path}")
    print(f"Images: {OUTPUT_DIR}")
    print(f"{'=' * 60}")
    return report


if __name__ == "__main__":
    run_benchmark()
