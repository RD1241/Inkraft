"""
trace_pipeline.py — FREE pipeline tracer (no fal.ai spend).

Mirrors services/comic_service.process_job_worker up to (but NOT including) the
image-generation call, and prints the EXACT prompt + routing decision the app
would use for every panel. This is the founder's core diagnostic: "the model is
rarely the problem — the PROMPT/extraction is. Trace the real prompt before
blaming a model."

Usage:
    venv/Scripts/python tools/trace_pipeline.py --style manga --panels 3 \
        --text "Kael charged forward, his blade catching the moonlight..."

    # or read the scene from a file
    venv/Scripts/python tools/trace_pipeline.py --style cinematic --panels 4 \
        --file scratch/scene.txt --user <uuid>     # --user loads the Vault

Nothing here calls fal.ai. It only runs Groq extraction + storyboard + prompt
build, which are free.
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from core.prompt_builder import PromptBuilder, resolve_monochrome
from core.storyboard_director import is_shared_frame_panel


def _routing_decision(style, focus, secondary, action):
    """Replicate fal_ai.generate_image's tiered-routing branch (no spend)."""
    style_key = (style or "anime").lower()
    routing_mode = getattr(settings, "IMAGE_ROUTING_MODE", "nano_all")
    premium_model = getattr(settings, "PREMIUM_IMAGE_MODEL", "fal-ai/nano-banana/edit")
    if routing_mode == "pro_shared":
        premium_model = "fal-ai/nano-banana-pro/edit"
    photoreal_style = style_key in ("cinematic", "realistic")
    is_shared = is_shared_frame_panel(focus, secondary, action)
    if routing_mode in ("flux_all", "sdxl_only", "text_to_image") or photoreal_style:
        use_premium = False
    elif routing_mode in ("hybrid", "pro_shared"):
        use_premium = is_shared
    else:  # nano_all
        use_premium = bool(focus or secondary)
    if use_premium:
        endpoint = premium_model
    else:
        from providers.image.fal_ai import STYLE_MODEL_MAP
        cfg = STYLE_MODEL_MAP.get(style_key, STYLE_MODEL_MAP["anime"])
        endpoint = f"{cfg['endpoint']} ({cfg.get('model_name','')})"
    return {
        "routing_mode": routing_mode,
        "is_shared_frame": is_shared,
        "use_premium": use_premium,
        "endpoint": endpoint,
    }


def compute_panels(text, style, panel_count, layout_type=None, color_mode="auto", user_id=None):
    """Run the real free pipeline (extract->storyboard->vault->prompt) and return
    structured per-panel data WITHOUT generating any image. Returns
    (global_env, [panel_dict, ...]) where each panel_dict has pos/neg/route/etc.
    This is the single source of truth shared by the trace printer and the
    model bake-off harness."""
    from services.comic_service import comic_service
    from providers.factory import get_llm_provider
    cs = comic_service
    cs.memory_manager.clear_memory()
    cs.memory_manager.load_character_design_sheets(user_id, request_sheets=None)
    llm = get_llm_provider()

    scene_data = llm.process_text(text, panel_count=panel_count, layout_type=layout_type)
    plan = cs.storyboard_director.plan(scene_data, panel_count=panel_count, layout_type=layout_type)
    global_env = plan.global_environment

    def chars_for(panel):
        for s in scene_data.get("scenes", []):
            if s.get("scene_id") == panel.scene_id:
                return list(s.get("characters", []))
        if scene_data.get("scenes"):
            return list(scene_data["scenes"][0].get("characters", []))
        return []

    # Vault override pass
    for panel in plan.panels:
        cs.memory_manager.process_scene_characters({
            "scene_id": panel.scene_id, "panel_id": panel.panel_id,
            "focus_character": panel.focus_character, "action": panel.action,
            "dialogue": panel.dialogue,
            "camera": cs.camera_director.get_shot_tokens(panel.camera_shot),
            "emotion": cs.expression_engine.build_emotion_prompt_segment(panel.emotion),
            "lighting": panel.lighting, "environment": global_env,
            "global_environment": global_env, "characters": chars_for(panel),
        }, story_text=text)

    out = []
    first_pos = ""
    for i, panel in enumerate(plan.panels):
        characters_list = chars_for(panel)
        secondary_char = ""
        if panel.focus_character and characters_list:
            fl = panel.focus_character.strip().lower()
            for c in characters_list:
                cn = c.get("name", "")
                if cn and cn.strip().lower() != fl:
                    secondary_char = cn
                    break
        if not secondary_char and len(characters_list) >= 2:
            secondary_char = characters_list[1].get("name", "")
        if panel.camera_shot in ("CLOSE_UP", "EXTREME_CLOSE_UP") and panel.focus_character:
            fl = panel.focus_character.strip().lower()
            filt = [c for c in characters_list if c.get("name", "").strip().lower() == fl]
            if filt:
                characters_list = filt
                secondary_char = ""
        panel_scene = {
            "scene_id": panel.scene_id, "panel_id": panel.panel_id,
            "focus_character": panel.focus_character, "action": panel.action,
            "dialogue": panel.dialogue,
            "camera": cs.camera_director.get_shot_tokens(panel.camera_shot),
            "emotion": cs.expression_engine.build_emotion_prompt_segment(panel.emotion),
            "lighting": panel.lighting, "environment": global_env,
            "global_environment": global_env, "characters": characters_list,
        }
        pb = PromptBuilder(style=style)
        if i > 0 and first_pos:
            pb.last_positive_prompt = first_pos
        pos, neg = pb.build_prompt(panel_scene, cs.memory_manager,
                                   is_continuation=(i > 0), style=style, color_mode=color_mode)
        if i == 0:
            first_pos = pos
        out.append({
            "panel_id": panel.panel_id, "scene_id": panel.scene_id,
            "camera_shot": panel.camera_shot, "emotion": panel.emotion,
            "tension": panel.tension_level, "focus": panel.focus_character,
            "secondary": secondary_char, "action": panel.action,
            "dialogue": panel.dialogue, "lighting": panel.lighting,
            "pos": pos, "neg": neg,
            "route": _routing_decision(style, panel.focus_character, secondary_char, panel.action),
        })
    return global_env, out


def trace(text, style, panel_count, layout_type=None, color_mode="auto", user_id=None):
    from services.comic_service import comic_service
    cs = comic_service
    cs.memory_manager.clear_memory()
    cs.memory_manager.load_character_design_sheets(user_id, request_sheets=None)

    llm = __import__("providers.factory", fromlist=["get_llm_provider"]).get_llm_provider()

    print("=" * 78)
    print(f"INPUT  style={style}  panels={panel_count}  layout={layout_type}  color={color_mode}")
    print(f"  monochrome resolved -> {resolve_monochrome(color_mode, style)}")
    print("-" * 78)
    print("STORY:")
    print(f"  {text}")
    print("=" * 78)

    # --- Step 1: extraction (free, Groq) ---
    scene_data = llm.process_text(text, panel_count=panel_count, layout_type=layout_type)
    scenes = scene_data.get("scenes", [])
    print(f"\n[1] LLM EXTRACTION — {len(scenes)} scene(s)")
    for s in scenes:
        chars = s.get("characters", [])
        cdesc = "; ".join(f"{c.get('name')}=({c.get('description','')})" for c in chars)
        print(f"  scene {s.get('scene_id')}: focus={s.get('focus_character','')!r}")
        print(f"     action: {s.get('action','')}")
        print(f"     chars : {cdesc}")
        if s.get("dialogue"):
            print(f"     dialog: {s.get('dialogue')}")

    # --- Step 1.5: storyboard (free, Groq) ---
    plan = cs.storyboard_director.plan(scene_data, panel_count=panel_count, layout_type=layout_type)
    print(f"\n[2] STORYBOARD — global_env={plan.global_environment!r}  total_panels={plan.total_panels}  layout={plan.layout_type}")

    # --- Pre-process character vault overrides (free) ---
    global_env = plan.global_environment
    for panel in plan.panels:
        characters_list = []
        for s in scene_data.get("scenes", []):
            if s.get("scene_id") == panel.scene_id:
                characters_list = s.get("characters", [])
                break
        panel_scene = {
            "scene_id": panel.scene_id, "panel_id": panel.panel_id,
            "focus_character": panel.focus_character, "action": panel.action,
            "dialogue": panel.dialogue,
            "camera": cs.camera_director.get_shot_tokens(panel.camera_shot),
            "emotion": cs.expression_engine.build_emotion_prompt_segment(panel.emotion),
            "lighting": panel.lighting, "environment": global_env,
            "global_environment": global_env, "characters": characters_list,
        }
        cs.memory_manager.process_scene_characters(panel_scene, story_text=text)

    # --- Per-panel prompt build + routing (free) ---
    print(f"\n[3] PER-PANEL PROMPTS + ROUTING")
    first_pos = ""
    for i, panel in enumerate(plan.panels):
        characters_list = []
        for s in scene_data.get("scenes", []):
            if s.get("scene_id") == panel.scene_id:
                characters_list = s.get("characters", [])
                break
        if not characters_list and scene_data.get("scenes"):
            characters_list = scene_data["scenes"][0].get("characters", [])

        secondary_char = ""
        if panel.focus_character and characters_list:
            fl = panel.focus_character.strip().lower()
            for c in characters_list:
                cn = c.get("name", "")
                if cn and cn.strip().lower() != fl:
                    secondary_char = cn
                    break
        if not secondary_char and len(characters_list) >= 2:
            secondary_char = characters_list[1].get("name", "")

        if panel.camera_shot in ("CLOSE_UP", "EXTREME_CLOSE_UP") and panel.focus_character:
            fl = panel.focus_character.strip().lower()
            filt = [c for c in characters_list if c.get("name", "").strip().lower() == fl]
            if filt:
                characters_list = filt
                secondary_char = ""

        panel_scene = {
            "scene_id": panel.scene_id, "panel_id": panel.panel_id,
            "focus_character": panel.focus_character, "action": panel.action,
            "dialogue": panel.dialogue,
            "camera": cs.camera_director.get_shot_tokens(panel.camera_shot),
            "emotion": cs.expression_engine.build_emotion_prompt_segment(panel.emotion),
            "lighting": panel.lighting, "environment": global_env,
            "global_environment": global_env, "characters": characters_list,
        }
        pb = PromptBuilder(style=style)
        if i > 0 and first_pos:
            pb.last_positive_prompt = first_pos
        pos, neg = pb.build_prompt(panel_scene, cs.memory_manager,
                                   is_continuation=(i > 0), style=style, color_mode=color_mode)
        if i == 0:
            first_pos = pos
        route = _routing_decision(style, panel.focus_character, secondary_char, panel.action)
        print("-" * 78)
        print(f"  PANEL {panel.panel_id}  shot={panel.camera_shot}  emotion={panel.emotion}  "
              f"tension={panel.tension_level}")
        print(f"    focus={panel.focus_character!r}  secondary={secondary_char!r}")
        print(f"    ROUTING: mode={route['routing_mode']}  shared={route['is_shared_frame']}  "
              f"premium={route['use_premium']}")
        print(f"    -> ENDPOINT: {route['endpoint']}")
        print(f"    POSITIVE ({len(pos.split(','))} tokens):")
        print(f"      {pos}")
        print(f"    NEGATIVE:")
        print(f"      {neg[:400]}{'...' if len(neg) > 400 else ''}")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="manga")
    ap.add_argument("--panels", type=int, default=3)
    ap.add_argument("--layout", default=None)
    ap.add_argument("--color", default="auto")
    ap.add_argument("--user", default=None, help="user_id to load the Vault")
    ap.add_argument("--text", default=None)
    ap.add_argument("--file", default=None)
    args = ap.parse_args()

    text = args.text
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read().strip()
    if not text:
        print("Provide --text or --file")
        sys.exit(1)

    trace(text, args.style, args.panels, layout_type=args.layout,
          color_mode=args.color, user_id=args.user)


if __name__ == "__main__":
    main()
