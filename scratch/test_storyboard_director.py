"""
scratch/test_storyboard_director.py
Test script to verify the functionality of StoryboardDirector.
"""

import sys
import os

# Add parent directory to sys.path so we can import config and core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.storyboard_director import StoryboardDirector, StoryboardPlan, StoryboardPanel


def main():
    print("Testing StoryboardDirector initialization...")
    director = StoryboardDirector()
    print("StoryboardDirector initialized successfully!")

    # Test case 1: Test dynamic panel count logic (both preferences None)
    print("\n--- Test Case 1: Dynamic panel count logic ---")
    
    # 1. Short text (< 100 words)
    short_scene = {
        "global_environment": "castle garden",
        "scenes": [
            {
                "scene_id": 1,
                "environment": "castle garden",
                "focus_character": "Arthur",
                "action": "Arthur stands quietly under the oak tree, looking at the flower.",
                "dialogue": []
            }
        ]
    }
    
    # 2. Medium text (100-250 words)
    medium_scene = {
        "global_environment": "castle garden",
        "scenes": [
            {
                "scene_id": 1,
                "environment": "castle garden",
                "focus_character": "Arthur",
                "action": "Arthur stands quietly under the oak tree, looking at the flower. " * 15,
                "dialogue": [{"speaker": "Arthur", "type": "speech", "text": "What a beautiful day." * 10}]
            }
        ]
    }
    
    # 3. Long text (>= 250 words)
    long_scene = {
        "global_environment": "castle garden",
        "scenes": [
            {
                "scene_id": 1,
                "environment": "castle garden",
                "focus_character": "Arthur",
                "action": "Arthur stands quietly under the oak tree, looking at the flower. " * 30,
                "dialogue": [{"speaker": "Arthur", "type": "speech", "text": "What a beautiful day." * 25}]
            }
        ]
    }
    
    plan_short = director.plan(short_scene, panel_count=None, layout_type=None)
    print(f"Short text panel count: expected 3, got {plan_short.total_panels}")
    assert plan_short.total_panels == 3, f"Expected 3, got {plan_short.total_panels}"
    
    plan_medium = director.plan(medium_scene, panel_count=None, layout_type=None)
    print(f"Medium text panel count: expected 4, got {plan_medium.total_panels}")
    assert plan_medium.total_panels == 4, f"Expected 4, got {plan_medium.total_panels}"
    
    plan_long = director.plan(long_scene, panel_count=None, layout_type=None)
    print(f"Long text panel count: expected 6, got {plan_long.total_panels}")
    assert plan_long.total_panels == 6, f"Expected 6, got {plan_long.total_panels}"

    # Test case 2: Fallback values verify (emotion: neutral, camera: MEDIUM, tension: 5)
    print("\n--- Test Case 2: Fallback panel properties ---")
    fallback_plan = director._generate_fallback_plan(short_scene, expected_count=3, layout_type="standard")
    
    print(f"Fallback plan panels count: {len(fallback_plan.panels)}")
    assert len(fallback_plan.panels) == 3
    
    for idx, panel in enumerate(fallback_plan.panels):
        print(f"Panel {panel.panel_id}: camera={panel.camera_shot}, emotion={panel.emotion}, tension={panel.tension_level}")
        assert panel.camera_shot == "MEDIUM", f"Expected camera MEDIUM, got {panel.camera_shot}"
        assert panel.emotion == "neutral", f"Expected emotion neutral, got {panel.emotion}"
        assert panel.tension_level == 5, f"Expected tension 5, got {panel.tension_level}"
        
    print("\nAll unit tests passed successfully!")


if __name__ == "__main__":
    main()
