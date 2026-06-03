import os
import sys
import json
import shutil
from PIL import Image

# Add paths so we can import from core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.panel_compositor import PanelCompositor, PageLayout, PanelCoords
from core.comic_renderer import ComicRenderer

def test_panel_compositor_all_counts():
    print("=== Testing PanelCompositor Layouts for N=2 to N=10 ===")
    compositor = PanelCompositor()
    
    for n in range(2, 11):
        print(f"\nTesting N = {n} panels...")
        # Create mock panels with random tensions (make one very high tension)
        panels = []
        for i in range(n):
            tension = 3
            if i == n // 2:
                tension = 10 # highest tension in the middle
            panels.append({"panel_id": i + 1, "tension_level": tension})
            
        layout = compositor.calculate_layout(panels, layout_type="action")
        
        # General assertions
        assert isinstance(layout, PageLayout), "Must return a PageLayout object"
        assert len(layout.panels) == n, f"Must return exactly {n} panels"
        assert layout.total_panels == n
        assert layout.layout_type == "action"
        
        # Print layout coordinates and sizes
        print(f"Layout type: {layout.layout_type}")
        print("Panel details:")
        for p in layout.panels:
            print(f"  Panel {p.panel_id}: size_class={p.size_class}, x={p.x}, y={p.y}, w={p.width}, h={p.height}")
            
            # Boundary assertions
            assert p.width > 0, "Width must be positive"
            assert p.height > 0, "Height must be positive"
            assert p.x >= 0, f"X coordinate must be >= 0: got {p.x}"
            assert p.y >= 0, f"Y coordinate must be >= 0: got {p.y}"
            assert p.x + p.width <= 1024, f"Right edge must be <= 1024: got {p.x + p.width}"
            assert p.y + p.height <= 1450, f"Bottom edge must be <= 1450: got {p.y + p.height}"

        # Rule assertions:
        # First panel size class must not be small
        assert layout.panels[0].size_class != "small", "First panel must not be 'small'"
        # Last panel size class must not be small
        assert layout.panels[-1].size_class != "small", "Last panel must not be 'small'"
        
        # Verify that the high tension panel gets a large size class if possible
        # Check if the panel with tension 10 has a larger size class than a standard small panel
        mid_idx = n // 2
        high_tension_panel = layout.panels[mid_idx]
        print(f"High tension panel (tension=10) size_class: {high_tension_panel.size_class}")
        if 3 <= n < 9:
            # For N>=3, we expect it to be larger than small if layouts allow it
            assert high_tension_panel.size_class in ["medium", "large", "full_width", "wide_short"], \
                f"High tension panel should get priority layout space, got {high_tension_panel.size_class}"

    print("\n[PASS] All N panel counts successfully compiled and verified against layout rules!")


def test_renderer_with_custom_layout():
    print("\n=== Testing ComicRenderer Custom Layout & Fallback ===")
    renderer = ComicRenderer()
    
    # Create temp directory for testing outputs
    temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_test")
    os.makedirs(temp_dir, exist_ok=True)
    
    # 1. Create mock panel images
    image_paths = []
    for i in range(3):
        img_path = os.path.join(temp_dir, f"scene_{i + 1}.png")
        # Draw some mock colored panels
        img = Image.new("RGB", (512, 512), color=((i*80)%255, (i*120)%255, (i*160)%255))
        img.save(img_path)
        image_paths.append(img_path)
        
    output_path = os.path.join(temp_dir, "final_page.png")
    
    # Test A: Fallback mode (No metadata.json present in temp_dir)
    print("\n--- Test A: Fallback (No metadata.json) ---")
    res_fallback = renderer.create_comic_page(image_paths, output_path)
    assert res_fallback is not None, "Fallback rendering must succeed"
    assert os.path.exists(output_path), "Output image file must be created"
    
    # Test B: Successful Custom Layout rendering (With metadata.json present)
    print("\n--- Test B: Custom Layout (With metadata.json) ---")
    metadata_path = os.path.join(temp_dir, "metadata.json")
    mock_metadata = {
        "layout_type": "drama",
        "scenes": [
            {"panel_id": 1, "tension_level": 3, "dialogue": []},
            {"panel_id": 2, "tension_level": 9, "dialogue": []}, # high tension in middle
            {"panel_id": 3, "tension_level": 4, "dialogue": []}
        ]
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(mock_metadata, f, indent=4)
        
    res_custom = renderer.create_comic_page(image_paths, output_path)
    assert res_custom is not None, "Custom layout rendering must succeed"
    assert os.path.exists(output_path), "Output image file must be created"
    
    # Verify the created image has correct dimensions
    final_img = Image.open(output_path)
    print(f"Created page dimensions: {final_img.size}")
    assert final_img.width == 1024, f"Final width must be 1024, got {final_img.width}"
    assert final_img.height == 1450, f"Final height must be 1450, got {final_img.height}"
    
    # Cleanup temp directory
    try:
        shutil.rmtree(temp_dir)
        print("\nCleaned up temp test directory.")
    except Exception as e:
        print(f"Warning: Cleanup failed: {e}")
        
    print("\n[PASS] ComicRenderer Custom Layout and Fallback tests passed successfully!")

if __name__ == "__main__":
    test_panel_compositor_all_counts()
    test_renderer_with_custom_layout()
    print("\nALL DYNAMIC PANEL COMPOSITION TESTS PASSED!")
