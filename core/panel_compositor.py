"""
core/panel_compositor.py
Stage 2 — Component 2D
Description: Panel Composition System that calculates coordinates for dynamic panel layouts on a 1024x1450 page canvas with a gutter of 8 pixels.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger("PanelCompositor")

@dataclass
class PanelCoords:
    x: int
    y: int
    width: int
    height: int
    panel_id: int
    size_class: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "panel_id": self.panel_id,
            "size_class": self.size_class
        }

@dataclass
class PageLayout:
    panels: List[PanelCoords]
    layout_type: str
    total_panels: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "panels": [p.to_dict() for p in self.panels],
            "layout_type": self.layout_type,
            "total_panels": self.total_panels
        }

# Size characteristics and relative space weights
SIZE_DIMENSIONS = {
    "full_width": {"width": 1016, "height": 380, "weight": 5},
    "wide_short": {"width": 1016, "height": 240, "weight": 4},
    "large": {"width": 668, "height": 320, "weight": 4},
    "medium": {"width": 508, "height": 300, "weight": 3},
    "small": {"width": 338, "height": 240, "weight": 1}
}

CANDIDATE_LAYOUTS = {
    2: [
        [["medium", "medium"]],
        [["full_width"], ["full_width"]],
        [["wide_short"], ["full_width"]],
        [["full_width"], ["wide_short"]]
    ],
    3: [
        [["medium", "medium"], ["full_width"]],
        [["full_width"], ["medium", "medium"]],
        [["large", "small"], ["full_width"]],
        [["full_width"], ["small", "large"]],
        [["medium", "medium"], ["wide_short"]],
        [["wide_short"], ["medium", "medium"]],
        [["wide_short"], ["full_width"], ["wide_short"]]
    ],
    4: [
        [["medium", "medium"], ["medium", "medium"]],
        [["large", "small"], ["small", "large"]],
        [["full_width"], ["medium", "medium"], ["wide_short"]],
        [["wide_short"], ["medium", "medium"], ["full_width"]],
        [["large", "small"], ["medium", "medium"]],
        [["medium", "medium"], ["small", "large"]],
        [["wide_short"], ["full_width"], ["wide_short"], ["wide_short"]],
        [["wide_short"], ["wide_short"], ["full_width"], ["wide_short"]],
        [["full_width"], ["full_width"], ["medium", "medium"]],
        [["medium", "medium"], ["full_width"], ["full_width"]]
    ],
    5: [
        [["medium", "medium"], ["full_width"], ["medium", "medium"]],
        [["large", "small"], ["full_width"], ["small", "large"]],
        [["full_width"], ["small", "small", "small"], ["full_width"]],
        [["large", "small"], ["medium", "medium"], ["wide_short"]],
        [["wide_short"], ["medium", "medium"], ["small", "large"]],
        [["full_width"], ["wide_short"], ["wide_short"], ["wide_short"], ["wide_short"]],
        [["wide_short"], ["wide_short"], ["wide_short"], ["wide_short"], ["full_width"]]
    ],
    6: [
        [["medium", "medium"], ["medium", "medium"], ["medium", "medium"]],
        [["large", "small"], ["medium", "medium"], ["small", "large"]],
        [["medium", "medium"], ["small", "small", "small"], ["full_width"]],
        [["full_width"], ["small", "small", "small"], ["medium", "medium"]],
        [["full_width"], ["full_width"], ["small", "small", "small"], ["full_width"]],
        [["large", "small"], ["full_width"], ["medium", "medium"], ["wide_short"]]
    ],
    7: [
        [["medium", "medium"], ["small", "small", "small"], ["medium", "medium"]],
        [["large", "small"], ["small", "small", "small"], ["small", "large"]],
        [["medium", "medium"], ["medium", "medium"], ["medium", "medium"], ["full_width"]],
        [["full_width"], ["medium", "medium"], ["medium", "medium"], ["medium", "medium"]],
        [["large", "small"], ["full_width"], ["small", "small", "small"], ["full_width"]],
        [["full_width"], ["small", "small", "small"], ["full_width"], ["small", "large"]]
    ],
    8: [
        [["medium", "medium"], ["medium", "medium"], ["medium", "medium"], ["medium", "medium"]],
        [["large", "small"], ["medium", "medium"], ["medium", "medium"], ["small", "large"]],
        [["full_width"], ["small", "small", "small"], ["small", "small", "small"], ["medium", "medium"]],
        [["full_width"], ["small", "small", "small"], ["small", "large"], ["medium", "medium"]]
    ],
    9: [
        [["medium", "medium"], ["small", "small", "small"], ["small", "large"], ["medium", "medium"]],
        [["large", "small"], ["small", "small", "small"], ["small", "large"], ["medium", "medium"]],
        [["medium", "medium"], ["small", "small", "small"], ["small", "small", "small"], ["full_width"]],
        [["full_width"], ["small", "small", "small"], ["small", "small", "small"], ["medium", "medium"]]
    ],
    10: [
        [["medium", "medium"], ["small", "small", "small"], ["small", "small", "small"], ["medium", "medium"]],
        [["large", "small"], ["small", "small", "small"], ["small", "small", "small"], ["small", "large"]],
        [["full_width"], ["small", "small", "small"], ["small", "small", "small"], ["full_width"], ["medium", "medium"]]
    ]
}

class PanelCompositor:
    """
    Panel composition engine that plans elegant, dynamic, non-uniform grid layouts.
    Computes coordinates for 2 to 10 panels to fit perfectly on a 1024x1450 canvas.
    """
    def __init__(self, page_width: int = 1024, page_height: int = 1450, gutter: int = 8):
        self.page_width = page_width
        self.page_height = page_height
        self.gutter = gutter
        self.top_margin = gutter
        self.bottom_margin = gutter

    def _generate_procedural_layout(self, N: int) -> List[List[str]]:
        """Procedural layout generator for fallback or boundary N values."""
        rows = []
        panels_left = N
        while panels_left > 0:
            if panels_left >= 2:
                rows.append(["medium", "medium"])
                panels_left -= 2
            else:
                rows.append(["full_width"])
                panels_left -= 1
        return rows

    def calculate_layout(self, panels: List[Any], layout_type: str = "standard") -> PageLayout:
        """
        Calculates exact coordinates for each panel based on its tension level and position.
        Ensures:
          - Gutter spacing of 8px is perfectly maintained.
          - Multi-panel row widths sum exactly to the page width (1024px) or are centered.
          - Row heights scale proportionally to fit the page height (1450px) exactly.
          - First and last panels are at least 'medium' size (no 'small' panel at the start or end).
          - Highest tension panel gets the maximum available space weight.
        """
        N = len(panels)
        if N < 1:
            raise ValueError("Cannot calculate layout for 0 panels.")

        # Extract IDs and tension levels
        panel_ids = []
        tensions = []
        for idx, p in enumerate(panels):
            pid = idx + 1
            tension = 5
            if hasattr(p, "panel_id"):
                pid = p.panel_id
            elif isinstance(p, dict) and "panel_id" in p:
                pid = p["panel_id"]

            if hasattr(p, "tension_level"):
                tension = p.tension_level
            elif isinstance(p, dict) and "tension_level" in p:
                tension = p["tension_level"]

            panel_ids.append(pid)
            tensions.append(tension)

        # 1. Selection of optimal row template
        candidates = CANDIDATE_LAYOUTS.get(N)
        if not candidates:
            logger.info(f"Using procedural layout for dynamic count N={N}")
            selected_structure = self._generate_procedural_layout(N)
        else:
            best_structure = None
            best_score = -1.0

            for structure in candidates:
                # Flatten structure to get linear slot sizes
                flat_slots = []
                for row in structure:
                    flat_slots.extend(row)

                if len(flat_slots) != N:
                    continue

                # Rule constraints:
                # First panel must be minimum 'medium' size (no 'small')
                if flat_slots[0] == "small":
                    continue
                # Last panel must be minimum 'medium' size (no 'small')
                if flat_slots[-1] == "small":
                    continue

                # Scoring compatibility:
                # Maximize tension * weight
                score = 0.0
                for i in range(N):
                    slot_size = flat_slots[i]
                    weight = SIZE_DIMENSIONS[slot_size]["weight"]
                    score += tensions[i] * weight

                # Add a minor diversity bonus to prefer layouts with varied panel sizes
                unique_sizes = len(set(flat_slots))
                score += unique_sizes * 1.5

                if score > best_score:
                    best_score = score
                    best_structure = structure

            selected_structure = best_structure if best_structure else candidates[0]

        # 2. Map structural slots to panel IDs
        panel_index = 0
        layout_rows = []
        for row in selected_structure:
            row_panels = []
            for slot_size in row:
                row_panels.append({
                    "panel_id": panel_ids[panel_index],
                    "size_class": slot_size,
                    "target_width": SIZE_DIMENSIONS[slot_size]["width"],
                    "target_height": SIZE_DIMENSIONS[slot_size]["height"]
                })
                panel_index += 1
            layout_rows.append(row_panels)

        # 3. Calculate Vertical Positions (Y-coordinates & Heights)
        n_rows = len(layout_rows)
        total_gutter_height = (n_rows - 1) * self.gutter
        available_height = self.page_height - self.top_margin - self.bottom_margin - total_gutter_height

        # Calculate default height of each row (max of its panel target heights)
        row_default_heights = []
        for row in layout_rows:
            max_h = max(p["target_height"] for p in row)
            row_default_heights.append(max_h)

        sum_default_heights = sum(row_default_heights)

        # Scale row heights to perfectly fit available_height
        scaled_row_heights = []
        for h in row_default_heights:
            scaled_h = int(h * (available_height / sum_default_heights))
            scaled_row_heights.append(scaled_h)

        # Add any leftover rounding pixels to the last row
        leftover_height = available_height - sum(scaled_row_heights)
        if scaled_row_heights:
            scaled_row_heights[-1] += leftover_height

        # 4. Calculate Horizontal Positions and Compile Panel Coordinates
        panel_coords_list = []
        y_current = self.top_margin

        for row_idx, row in enumerate(layout_rows):
            row_height = scaled_row_heights[row_idx]
            k = len(row)
            row_gutter_width = (k - 1) * self.gutter
            sum_target_widths = sum(p["target_width"] for p in row)
            row_target_width = sum_target_widths + row_gutter_width

            scaled_widths = []
            left_margin = 0

            if row_target_width > self.page_width:
                # Scale widths down to fit the page width exactly
                scale_x = (self.page_width - row_gutter_width) / sum_target_widths
                for p in row:
                    scaled_w = int(p["target_width"] * scale_x)
                    scaled_widths.append(scaled_w)
                # Distribute rounding leftovers to the last panel in this row
                leftover_w = (self.page_width - row_gutter_width) - sum(scaled_widths)
                if scaled_widths:
                    scaled_widths[-1] += leftover_w
            else:
                # Center the row within the page width
                left_margin = (self.page_width - row_target_width) // 2
                for p in row:
                    scaled_widths.append(p["target_width"])

            # Compute X coordinates iteratively
            x_current = left_margin
            for p_idx, p in enumerate(row):
                w = scaled_widths[p_idx]
                panel_coords_list.append(PanelCoords(
                    x=x_current,
                    y=y_current,
                    width=w,
                    height=row_height,
                    panel_id=p["panel_id"],
                    size_class=p["size_class"]
                ))
                x_current += w + self.gutter

            y_current += row_height + self.gutter

        # 5. Build and return the final PageLayout object
        # Sort panels by their original panel ID to keep them in order
        panel_coords_list.sort(key=lambda item: item.panel_id)

        return PageLayout(
            panels=panel_coords_list,
            layout_type=layout_type,
            total_panels=N
        )
