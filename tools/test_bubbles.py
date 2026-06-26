import os
import sys
import shutil

# Bootstrap to allow running from NovelToComic root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.comic_renderer import ComicRenderer

def test_bubbles():
    print("Running speech bubble legibility test...")
    renderer = ComicRenderer()
    
    # 1. Define paths to existing panels
    color_panel_src = r"D:\Project_I\NovelToComic\outputs\20260626_160537\scene_1.png"
    mono_panel_src = r"D:\Project_I\NovelToComic\test_outputs\nano_banana_test\panel_1.png"
    
    # Create test output directory
    test_dir = r"D:\Project_I\NovelToComic\test_outputs\bubble_verification"
    os.makedirs(test_dir, exist_ok=True)
    
    # Define targets
    color_before = os.path.join(test_dir, "color_before.png")
    color_after = os.path.join(test_dir, "color_after.png")
    mono_before = os.path.join(test_dir, "mono_before.png")
    mono_after = os.path.join(test_dir, "mono_after.png")
    
    # Copy before panels for reference
    shutil.copy(color_panel_src, color_before)
    shutil.copy(mono_panel_src, mono_before)
    print("Copied before images.")
    
    # 2. Define dialogues of varying lengths
    dialogues = [
        {"speaker": "Kaito", "type": "speech", "text": "Short dialogue!"},
        {"speaker": "Mei", "type": "speech", "text": "This is a medium dialogue bubble to test normal wrapping rules on typical panels."},
        {"speaker": "Kaito", "type": "speech", "text": "This is an extremely long dialogue bubble designed to test the boundary limits of text-wrapping, font scaling, bubble clamping, and general rendering legibility. It needs to fit perfectly without overlapping or clipping through any speech bubble borders, even when rendered on smaller viewports."},
        {"speaker": "Narrator", "type": "narration", "text": "A standard narration box at the top to check readability and contrast."}
    ]
    
    # 3. Render color style (anime)
    print("Rendering on color panel...")
    renderer.draw_speech_bubble(
        image_path=color_before,
        dialogues=dialogues,
        output_path=color_after,
        panel_index=1,
        style="anime",
        layout_type="standard",
        tension_level=5,
        action_description="Kaito and Mei discussing",
        total_panels=1
    )
    
    # 4. Render manga style (monochrome)
    print("Rendering on mono panel...")
    renderer._rendered_dialogues.clear()
    renderer.draw_speech_bubble(
        image_path=mono_before,
        dialogues=dialogues,
        output_path=mono_after,
        panel_index=2,
        style="manga",
        layout_type="standard",
        tension_level=5,
        action_description="A swordsman stands on the rooftop",
        total_panels=1
    )
    
    print(f"Rendered color output saved to: {color_after}")
    print(f"Rendered mono output saved to: {mono_after}")
    print("Done!")

if __name__ == "__main__":
    test_bubbles()
