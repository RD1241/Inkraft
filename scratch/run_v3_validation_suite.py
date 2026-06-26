"""
run_v3_validation_suite.py
Phase 6 - V3 Quality Validation Suite.
Checks all V3 component installations and generates a validation report
comparing Before V3 vs After V3 quality metrics.
"""
import os
import sys
import json
import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

OUTPUT_DIR = os.path.join(project_root, "outputs", "v3_validation")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "interaction_tests"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "before_after"), exist_ok=True)

# ── Baseline scores from pre-V3 benchmark ──────────────────────────────────
BEFORE_V3_SCORES = {
    "overall_quality": 8.2,
    "consistency": 8.75,
    "art_quality": 8.1,
    "character_consistency": 8.75,
    "expression_accuracy": 7.5,
    "interaction_accuracy": 6.8,
    "action_quality": 7.2,
    "environment_quality": 8.3,
    "commercial_quality": 8.0,
}

# ── V3 target scores ────────────────────────────────────────────────────────
V3_TARGETS = {
    "overall_quality": 8.8,
    "consistency": 9.0,
    "expression_accuracy": 8.5,
    "interaction_accuracy": 8.5,
    "action_quality": 8.5,
}

# ── Validation test scenarios ───────────────────────────────────────────────
V3_TEST_SCENARIOS = [
    {
        "id": "holding_hands",
        "name": "Holding Hands Scene (Kael & Elena)",
        "type": "interaction",
        "story": (
            "Kael gently takes Elena's hand as they stand on the cliff overlooking "
            "the kingdom. Their fingers interlock as she leans against him quietly."
        ),
        "characters": ["Kael", "Elena"],
        "style": "manhwa",
        "dimension": "physical_interaction",
        "expected_v3_tokens": ["interlocked fingers", "visible hand contact"],
    },
    {
        "id": "sword_clash",
        "name": "Sword Clash Scene (Kael vs Commander)",
        "type": "action",
        "story": (
            "Kael charges across the battlefield. The enemy commander blocks him. "
            "Their swords clash with a deafening ring, metal sparks flying between them. "
            "A shockwave erupts from the impact point."
        ),
        "characters": ["Kael", "Enemy Commander"],
        "style": "manhwa",
        "dimension": "action_quality",
        "expected_v3_tokens": ["crossed swords", "metal sparks", "dynamic combat stance"],
    },
    {
        "id": "three_char_dialogue",
        "name": "Three Character Dialogue (Kael, Elena, King Aldric)",
        "type": "dialogue",
        "story": (
            "In the throne room, Kael stands before King Aldric and Elena. "
            "The king speaks gravely about the coming war. Elena watches Kael's "
            "face carefully for his reaction to the king's words."
        ),
        "characters": ["Kael", "Elena", "King Aldric"],
        "style": "cinematic",
        "dimension": "multi_character",
        "expected_v3_tokens": ["CHARACTER_A", "CHARACTER_B", "CHARACTER_C"],
    },
    {
        "id": "emotional_confrontation",
        "name": "Emotional Confrontation (Rage + Grief)",
        "type": "emotional",
        "story": (
            "Kael's rage erupts as he sees Elena lying wounded on the ground. "
            "His grief-stricken face transforms into infuriated determination. "
            "He screams at the enemy commander, tears streaming down his face."
        ),
        "characters": ["Kael"],
        "style": "manhwa",
        "dimension": "expression_quality",
        "expected_v3_tokens": ["blazing furious eyes", "bared teeth", "streaming tears"],
    },
]

SCORING_CRITERIA = {
    "art_quality": "Overall visual quality and style fidelity (1-10)",
    "character_consistency": "Face, hair, outfit match across panels (1-10)",
    "expression_accuracy": "Emotional expression matches story intent (1-10)",
    "interaction_accuracy": "Physical interactions between characters visible (1-10)",
    "action_quality": "Action readability and dynamic composition (1-10)",
    "environment_quality": "Background and setting quality (1-10)",
    "commercial_quality": "Would this look professional in a published comic (1-10)",
}


def check_v3_components():
    """Verify all V3 components are correctly installed."""
    print("\nChecking V3 component installation...")
    status = {}

    # ActionLibrary V2
    try:
        from core.action_library import ActionLibrary
        lib = ActionLibrary()
        charge = lib.get_action_tokens("Kael charges across the battlefield")
        empty = lib.get_action_tokens("They sat and talked quietly")
        sword = lib.get_action_tokens("Their swords clash with sparks")
        ok = len(charge) > 0 and len(empty) == 0 and len(sword) > 0
        status["action_library_v2"] = {
            "installed": True, "pass": ok,
            "charge_tokens": charge,
            "dialogue_fallback_is_empty": len(empty) == 0,
            "sword_tokens": sword,
        }
        print(f"  [{'OK' if ok else 'FAIL'}] ActionLibrary V2 — {len(lib._keyword_map)} keywords")
    except Exception as e:
        status["action_library_v2"] = {"installed": False, "error": str(e)}
        print(f"  [FAIL] ActionLibrary V2: {e}")

    # InteractionComposer V1
    try:
        from core.interaction_composer import InteractionComposer
        ic = InteractionComposer()
        hold = ic.detect_and_inject("Their fingers interlock as they hold hands", 2)
        punch = ic.detect_and_inject("She punches him in the face", 2)
        solo = ic.detect_and_inject("She holds hands with herself", 1)
        ok = len(hold) > 0 and len(punch) > 0 and len(solo) == 0
        status["interaction_composer_v1"] = {
            "installed": True, "pass": ok,
            "hold_tokens": hold,
            "punch_tokens": punch,
            "single_char_guard": len(solo) == 0,
        }
        print(f"  [{'OK' if ok else 'FAIL'}] InteractionComposer V1 — {len(ic._keyword_map)} keywords")
    except Exception as e:
        status["interaction_composer_v1"] = {"installed": False, "error": str(e)}
        print(f"  [FAIL] InteractionComposer V1: {e}")

    # ExpressionEngine V3
    try:
        from core.expression_engine import ExpressionEngine
        ee = ExpressionEngine("fal_ai")
        grief = ee.build_emotion_prompt_segment("grief")
        rage = ee.build_emotion_prompt_segment("infuriated")
        romantic = ee.build_emotion_prompt_segment("smitten")
        despair = ee.build_emotion_prompt_segment("despair")
        n = len(ee.EMOTIONS)
        ok = n >= 20 and bool(grief and rage and romantic and despair)
        # Verify routing
        rage_resolves_to_rage = ee._resolve_emotion_synonym("infuriated") == "rage"
        grief_resolves_to_grief = ee._resolve_emotion_synonym("grief") == "grief"
        status["expression_engine_v3"] = {
            "installed": True, "pass": ok,
            "emotion_count": n,
            "infuriated_resolves_to": ee._resolve_emotion_synonym("infuriated"),
            "grief_resolves_to": ee._resolve_emotion_synonym("grief"),
            "routing_correct": rage_resolves_to_rage and grief_resolves_to_grief,
        }
        routing_ok = "OK" if (rage_resolves_to_rage and grief_resolves_to_grief) else "FAIL BAD ROUTING"
        print(f"  [{'OK' if ok else 'FAIL'}] ExpressionEngine V3 — {n} emotions, routing {routing_ok}")
    except Exception as e:
        status["expression_engine_v3"] = {"installed": False, "error": str(e)}
        print(f"  [FAIL] ExpressionEngine V3: {e}")

    # PromptBuilder V3 Identity Block
    try:
        from core.prompt_builder import PromptBuilder, CHARACTER_SEPARATOR_LABELS, BACKGROUND_LABEL
        pb = PromptBuilder("manhwa")
        ok = len(CHARACTER_SEPARATOR_LABELS) == 3 and BACKGROUND_LABEL == "BACKGROUND_SUPPORTING_CHARACTERS"
        has_multi = hasattr(pb, "build_multi_character_identity_block")
        status["prompt_builder_v3"] = {
            "installed": True, "pass": ok and has_multi,
            "labels": CHARACTER_SEPARATOR_LABELS,
            "background_label": BACKGROUND_LABEL,
            "has_multi_char_method": has_multi,
        }
        print(f"  [{'OK' if (ok and has_multi) else 'FAIL'}] PromptBuilder V3 — labels={CHARACTER_SEPARATOR_LABELS}")
    except Exception as e:
        status["prompt_builder_v3"] = {"installed": False, "error": str(e)}
        print(f"  [FAIL] PromptBuilder V3: {e}")

    # StoryboardDirector V3 (Cinematic Storytelling)
    try:
        from core.storyboard_director import StoryboardDirector, CINEMATIC_SEQUENCES
        ok = len(CINEMATIC_SEQUENCES) >= 5
        status["storyboard_director_v3"] = {
            "installed": True, "pass": ok,
            "sequence_count": len(CINEMATIC_SEQUENCES),
            "sequences": list(CINEMATIC_SEQUENCES.keys()),
        }
        print(f"  [{'OK' if ok else 'FAIL'}] StoryboardDirector V3 — {len(CINEMATIC_SEQUENCES)} cinematic sequences")
    except ImportError:
        status["storyboard_director_v3"] = {"installed": False, "error": "CINEMATIC_SEQUENCES not yet added (Sub-Agent E pending)"}
        print(f"  [PENDING] StoryboardDirector V3 — Sub-Agent E not yet run")
    except Exception as e:
        status["storyboard_director_v3"] = {"installed": False, "error": str(e)}
        print(f"  [FAIL] StoryboardDirector V3: {e}")

    return status


def print_summary(status):
    installed = sum(1 for v in status.values() if v.get("installed"))
    passing = sum(1 for v in status.values() if v.get("pass"))
    total = len(status)
    print(f"\n{'=' * 40}")
    print(f"Components: {installed}/{total} installed  |  {passing}/{total} passing")
    if passing == total:
        print("[ALL PASS] ALL V3 COMPONENTS READY")
    else:
        failing = [k for k, v in status.items() if not v.get("pass")]
        print(f"[WARN] Not ready: {', '.join(failing)}")
    print(f"{'=' * 40}")


def run_validation_suite():
    print("=" * 60)
    print("PHASE 6 — Prompt Engineering V3 Validation Suite")
    print(f"Timestamp: {datetime.datetime.now().isoformat()}")
    print("=" * 60)

    status = check_v3_components()
    print_summary(status)

    installed = sum(1 for v in status.values() if v.get("installed"))
    passing = sum(1 for v in status.values() if v.get("pass"))

    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "sprint": "Prompt Engineering V3 + RealVisXL Benchmark Sprint",
        "component_status": status,
        "components_installed": installed,
        "components_passing": passing,
        "before_v3_baseline": BEFORE_V3_SCORES,
        "v3_targets": V3_TARGETS,
        "test_scenarios": V3_TEST_SCENARIOS,
        "scoring_criteria": SCORING_CRITERIA,
        "output_dir": OUTPUT_DIR,
        "after_v3_scores": None,   # Filled after manual testing
        "verdict": None,           # "APPROVED" or "NEEDS_MORE_WORK"
        "instructions": [
            "1. Ensure all 5 components show [OK] — run Sub-Agent E first if StoryboardDirector V3 is pending",
            "2. Start the backend: cd d:/Project_I/NovelToComic && venv/Scripts/uvicorn api.main:app --reload",
            "3. Generate a comic for each test scenario story via the UI or API",
            "4. Save output images to outputs/v3_validation/interaction_tests/<scenario_id>/",
            "5. Score each output 1-10 on all 7 criteria in scoring_criteria",
            "6. Update after_v3_scores in this report and set verdict",
            "7. Compare against before_v3_baseline and v3_targets",
        ],
    }

    path = os.path.join(OUTPUT_DIR, "v3_validation_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved: {path}")
    print("\nBEFORE V3 BASELINE:")
    for k, v in BEFORE_V3_SCORES.items():
        target = V3_TARGETS.get(k)
        target_str = f"  (target: {target})" if target else ""
        print(f"  {k}: {v}{target_str}")
    print("=" * 60)
    return report


if __name__ == "__main__":
    run_validation_suite()
