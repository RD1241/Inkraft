"""
camera_director.py
Stage 2 — Component 2B
Camera Director mapping camera angles and layout-type default shots to SD prompt tokens.
"""

class CameraDirector:
    # 11 camera shot types mapped to exact SD tokens
    SHOT_MAP = {
        "EXTREME_CLOSE_UP": "extreme close-up shot, extreme close-up, macro shot, detailed facial features",
        "CLOSE_UP": "close-up shot, close-up, portrait, head and shoulders shot",
        "MEDIUM_CLOSE": "medium close-up shot, upper body shot, portrait",
        "MEDIUM": "medium shot, waist-up shot",
        "WIDE": "wide shot, full-body shot, wide-angle shot, environmental shot",
        "ESTABLISHING": "establishing shot, wide-angle view, scenic view, background focus",
        "OVER_SHOULDER": "over-the-shoulder shot, shoulder in foreground",
        "LOW_ANGLE": "low angle shot, looking up view, heroic perspective",
        "HIGH_ANGLE": "high angle shot, looking down view, overhead perspective",
        "DUTCH_ANGLE": "dutch angle shot, tilted frame, diagonal composition, dramatic angle",
        "ACTION_DYNAMIC": "action-packed dynamic shot, action pose, dynamic composition, motion blur",
    }

    # Default sequence of shots for various layout styles/types
    LAYOUT_SHOTS = {
        "grid": ["MEDIUM", "CLOSE_UP", "MEDIUM_CLOSE", "MEDIUM"],
        "splash": ["ESTABLISHING"],
        "action": ["ACTION_DYNAMIC", "LOW_ANGLE", "MEDIUM", "DUTCH_ANGLE"],
        "establishing": ["ESTABLISHING", "WIDE"],
        "focus": ["CLOSE_UP", "EXTREME_CLOSE_UP", "MEDIUM_CLOSE"],
        "dialogue": ["OVER_SHOULDER", "CLOSE_UP", "MEDIUM_CLOSE"],
        "cinematic": ["WIDE", "HIGH_ANGLE", "LOW_ANGLE", "DUTCH_ANGLE"],
        "horizontal": ["WIDE", "MEDIUM", "CLOSE_UP"],
        "vertical": ["HIGH_ANGLE", "LOW_ANGLE", "MEDIUM"],
    }

    def get_shot_tokens(self, shot_type: str) -> str:
        """
        Get the exact SD prompt tokens for the given shot type.
        Falls back to 'MEDIUM''s tokens silently if the shot type is unknown or empty.
        """
        if not shot_type:
            return self.SHOT_MAP["MEDIUM"]
            
        shot_type_upper = shot_type.strip().upper()
        if shot_type_upper not in self.SHOT_MAP:
            return self.SHOT_MAP["MEDIUM"]
            
        return self.SHOT_MAP[shot_type_upper]

    def get_layout_type_default_shots(self, layout_type: str) -> list[str]:
        """
        Get the list of default camera shots for a layout type.
        Falls back to ['MEDIUM'] silently if unknown or empty.
        """
        if not layout_type:
            return ["MEDIUM"]
            
        layout_type_lower = layout_type.strip().lower()
        if layout_type_lower not in self.LAYOUT_SHOTS:
            return ["MEDIUM"]
            
        return self.LAYOUT_SHOTS[layout_type_lower].copy()
