"""
model_bakeoff.py — PAID model comparison (spends fal.ai credits).

Generates the SAME real-pipeline prompt across several candidate models so the
images are directly comparable. Uses tools/trace_pipeline.compute_panels() so the
prompt is EXACTLY what the live app would send (founder's rule: test the real
prompt, not a hand-written one).

Outputs go to test_outputs/bakeoff/<run>/<style>__<tag>.png plus a prompt.txt and
a costs.json. View the PNGs to judge quality, then wire the winner into
providers/image/fal_ai.py STYLE_MODEL_MAP.

Usage:
  venv/Scripts/python tools/model_bakeoff.py --style cinematic \
      --text "..." --models sdxl_dreamshaper,flux_schnell,flux_dev

Cost (approx per image): fast-sdxl $0.0025, flux/schnell $0.003, flux/dev $0.025,
flux-pro $0.05, nano-banana/edit $0.039. The script prints a running total — keep
an eye on the $4 budget.
"""
import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("LLM_PROVIDER", "groq")

import httpx
from config import settings
from tools.trace_pipeline import compute_panels

# tag -> (endpoint, model_name, approx_cost, supports_negative)
MODELS = {
    "sdxl_animagine":   ("fal-ai/fast-sdxl", "cagliostrolab/animagine-xl-3.1", 0.0025, True),
    "sdxl_dreamshaper": ("fal-ai/fast-sdxl", "Lykon/dreamshaper-xl-v2-turbo",  0.0025, True),
    "sdxl_realvis":     ("fal-ai/fast-sdxl", "SG161222/RealVisXL_V4.0",        0.0025, True),
    "flux_schnell":     ("fal-ai/flux/schnell", None, 0.003, False),
    "flux_dev":         ("fal-ai/flux/dev",     None, 0.025, False),
    "flux_pro":         ("fal-ai/flux-pro/v1.1", None, 0.05, False),
}

RUNNING_COST = 0.0


def gen(tag, prompt, neg, out_path, width, height):
    """Generate one image with the given model tag. Returns (ok, cost)."""
    global RUNNING_COST
    import fal_client
    endpoint, model_name, cost, supports_neg = MODELS[tag]
    args = {"prompt": prompt, "image_size": {"width": width, "height": height}, "num_images": 1}
    if endpoint.startswith("fal-ai/fast-sdxl"):
        args["num_inference_steps"] = 25
        if model_name:
            args["model_name"] = model_name
        if supports_neg and neg:
            args["negative_prompt"] = neg
    elif "schnell" in endpoint:
        args["num_inference_steps"] = 4
    # flux/dev + flux-pro: defaults are fine
    t0 = time.time()
    try:
        handler = fal_client.submit(endpoint, args)
        req_id = handler.request_id
        poll_start = time.time()
        result = None
        while time.time() - poll_start < 240:
            st = fal_client.status(endpoint, req_id)
            if isinstance(st, fal_client.Completed):
                result = fal_client.result(endpoint, req_id)
                break
            time.sleep(2)
        if not result or not result.get("images"):
            print(f"  [{tag}] FAILED — no image returned")
            return False, 0.0
        url = result["images"][0]["url"]
        r = httpx.get(url, timeout=60)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        RUNNING_COST += cost
        print(f"  [{tag}] OK  {time.time()-t0:4.0f}s  ~${cost:.4f}  -> {os.path.basename(out_path)}  (run total ~${RUNNING_COST:.3f})")
        return True, cost
    except Exception as e:
        print(f"  [{tag}] ERROR: {e}")
        return False, 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--models", required=True, help="comma list of tags from MODELS")
    ap.add_argument("--panel", type=int, default=1, help="which panel's prompt (1-based)")
    ap.add_argument("--color", default="auto")
    ap.add_argument("--run", default="run1", help="subfolder name")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1280)
    args = ap.parse_args()

    tags = [t.strip() for t in args.models.split(",") if t.strip()]
    for t in tags:
        if t not in MODELS:
            print(f"Unknown model tag {t}. Valid: {list(MODELS)}")
            sys.exit(1)

    _, panels = compute_panels(args.text, args.style, panel_count=3, color_mode=args.color)
    p = panels[min(args.panel - 1, len(panels) - 1)]
    prompt, neg = p["pos"], p["neg"]

    out_dir = os.path.join("test_outputs", "bakeoff", args.run)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{args.style}__prompt.txt"), "w", encoding="utf-8") as f:
        f.write(f"STYLE: {args.style}\nPANEL: {args.panel}  focus={p['focus']} secondary={p['secondary']} "
                f"emotion={p['emotion']} shot={p['camera_shot']}\n\nPOSITIVE:\n{prompt}\n\nNEGATIVE:\n{neg}\n")

    print(f"\n=== BAKE-OFF  style={args.style}  panel {args.panel} ({p['camera_shot']}, {p['emotion']}) ===")
    print(f"PROMPT: {prompt[:160]}...")
    print(f"models: {tags}\n")

    costs = {}
    for tag in tags:
        out_path = os.path.join(out_dir, f"{args.style}__{tag}.png")
        ok, cost = gen(tag, prompt, neg, out_path, args.width, args.height)
        costs[tag] = {"ok": ok, "cost": cost}

    with open(os.path.join(out_dir, f"{args.style}__costs.json"), "w") as f:
        json.dump({"style": args.style, "running_cost": RUNNING_COST, "models": costs}, f, indent=2)
    print(f"\n=== {args.style} done. style cost ~${sum(c['cost'] for c in costs.values()):.4f}  "
          f"session running ~${RUNNING_COST:.3f} ===")


if __name__ == "__main__":
    main()
