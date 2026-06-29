"""
core/storyboard_director.py
Stage 2 — Component 2C
Description: Handles planning and orchestration of storyboard panels between raw LLM extraction and image generation, ensuring cinematic layout, narrative flow, dynamic panel count calculation, and robust schema validation with retry logic.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import httpx
import ollama
from config import settings
from providers.llm.chat_client import get_chat_client, using_groq


ACTION_CLASSIFIER = {
    "charge": {"camera": "low angle shot", "pose": "dynamic forward motion, running action pose", "composition": "dramatic perspective, motion lines"},
    "block": {"camera": "medium shot", "pose": "defensive stance, blocking with shield", "composition": "clashing impact sparks"},
    "collide": {"camera": "closeup shot", "pose": "close combat weapon collision", "composition": "steel sparks flying, shockwave rings"},
    "shockwave": {"camera": "wide environmental shot", "pose": "force push posture", "composition": "erupting debris, dust rings"},
    "run": {"camera": "medium wide shot", "pose": "running fast action pose", "composition": "motion blur background"},
    "attack": {"camera": "low angle action shot", "pose": "striking weapon attack pose", "composition": "spark highlights"},
    "slash": {"camera": "dutch angle shot", "pose": "sword slashing pose, sweeping motion", "composition": "glowing sword trail, speed lines"},
    "jump": {"camera": "low angle shot, looking up", "pose": "jumping high in the air pose", "composition": "dynamic motion lines, clouds background"},
    "fall": {"camera": "high angle shot, looking down", "pose": "falling down backwards pose", "composition": "motion blur, debris"},
    "explode": {"camera": "wide environmental shot", "pose": "recoil pose from blast", "composition": "fire explosion, smoke billows, glowing embers"},
    "strike": {"camera": "extreme close up", "pose": "delivering a powerful punch or weapon strike", "composition": "impact shockwave"},
    "draw sword": {"camera": "medium shot, close up on hand", "pose": "drawing sword from scabbard", "composition": "metallic glint reflection"},
    "cast spell": {"camera": "medium shot", "pose": "casting magic spell pose, hands outstretched", "composition": "glowing magic circles, energy particles"},
    "embrace": {"camera": "close up shot", "pose": "embracing, hugging tightly", "composition": "warm soft lighting, intimate depth of field"},
    "cry": {"camera": "extreme close up shot", "pose": "crying with head down, hands over face", "composition": "tear droplets, soft shadows"},
    "kneel": {"camera": "low angle shot", "pose": "kneeling down on one knee", "composition": "submissive posture, dramatic shadow"}
}

EMOTION_MAPPER = {
    r"cry|sob|weep|grief": "sad, crying expression with tears, closed eyes squeezing tears, shoulders slumped, head bowed",
    r"anger|rage|furious|betray|accuse": "angry, furious glaring expression, grinding teeth, intense glaring eyes, clenched fists",
    r"love|romance|lantern|hand|gently": "happy, gentle warm smile, blushing cheeks, soft gentle eyes, relaxed posture",
    r"fear|terror|flee|chase": "fearful, terrified shocked expression, wide dilated pupils, cowering posture"
}

# V3 Cinematic Storytelling: Named camera sequence templates by scene type
CINEMATIC_SEQUENCES = {
    "EMOTIONAL_ESCALATION": ["WIDE", "MEDIUM", "CLOSE_UP", "EXTREME_CLOSE_UP"],
    "ACTION_BURST":         ["WIDE", "LOW_ANGLE", "CLOSE_UP", "WIDE"],
    "DIALOGUE_RHYTHM":      ["OVER_SHOULDER", "CLOSE_UP", "MEDIUM_CLOSE", "WIDE"],
    "CONFRONTATION_ARC":    ["WIDE", "MEDIUM", "CLOSE_UP", "DUTCH_ANGLE"],
    "REVEAL_SEQUENCE":      ["HIGH_ANGLE", "WIDE", "CLOSE_UP", "MEDIUM"],
}

# Keywords to detect scene type for auto-selection of cinematic sequence
SEQUENCE_KEYWORDS = {
    "ACTION_BURST": [
        "sword", "clash", "attack", "fight", "battle", "charge", "slash",
        "punch", "kick", "combat", "strike", "explosion", "duel", "war"
    ],
    "DIALOGUE_RHYTHM": [
        "said", "spoke", "replied", "asked", "answered", "whispered",
        "shouted", "told", "conversation", "talk", "dialogue", "speak"
    ],
    "EMOTIONAL_ESCALATION": [
        "grief", "cry", "sob", "tears", "rage", "despair", "heartbroken",
        "devastated", "collapse", "weep", "mourn", "scream"
    ],
    "CONFRONTATION_ARC": [
        "confront", "accuse", "betray", "threaten", "challenge", "standoff",
        "face to face", "face off", "stare down", "face each other"
    ],
    "REVEAL_SEQUENCE": [
        "reveal", "discover", "uncover", "realize", "unveil", "secret",
        "hidden", "exposed", "found", "truth"
    ],
}


def detect_sequence_type(action_text: str, emotion: str, narrative_purpose: str) -> Optional[str]:
    """
    Detect the best cinematic sequence template for a scene based on
    action text, emotion, and narrative purpose keywords.
    Returns a CINEMATIC_SEQUENCES key or None if no strong match.
    """
    combined = " ".join([
        (action_text or "").lower(),
        (emotion or "").lower(),
        (narrative_purpose or "").lower()
    ])
    # Check each sequence type in priority order
    for seq_name, keywords in SEQUENCE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return seq_name
    return None

def classify_action(action_text: str) -> Optional[dict]:
    if not action_text:
        return None
    lower_text = action_text.lower()
    for keyword, value in ACTION_CLASSIFIER.items():
        if keyword in lower_text:
            return value
    return None

def classify_emotion(action_text: str) -> Optional[str]:
    if not action_text:
        return None
    lower_text = action_text.lower()
    for pattern, emotion_str in EMOTION_MAPPER.items():
        if re.search(pattern, lower_text):
            return emotion_str
    return None



def is_shared_frame_panel(focus_character: str, secondary_character: str, action: str) -> bool:
    """
    Checks if a panel represents a shared frame (both characters share the frame).
    Heuristic: Both characters are defined, and (focus_character is empty/None OR both are in the action text).
    """
    char_names = []
    if focus_character:
        char_names.append(focus_character)
    if secondary_character:
        char_names.append(secondary_character)
        
    if len(char_names) >= 2:
        action_lower = (action or "").lower()
        both_in_action = sum(1 for name in char_names if name.lower() in action_lower) >= 2
        if not focus_character or both_in_action:
            return True
    return False


@dataclass
class StoryboardPanel:
    scene_id: int
    panel_id: int
    narrative_purpose: str
    emotion: str
    camera_shot: str
    panel_size: str
    lighting: str
    focus_character: str
    action: str
    dialogue: List[Dict[str, Any]]
    transition_from_previous: str
    tension_level: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "panel_id": self.panel_id,
            "narrative_purpose": self.narrative_purpose,
            "emotion": self.emotion,
            "camera_shot": self.camera_shot,
            "panel_size": self.panel_size,
            "lighting": self.lighting,
            "focus_character": self.focus_character,
            "action": self.action,
            "dialogue": self.dialogue,
            "transition_from_previous": self.transition_from_previous,
            "tension_level": self.tension_level,
        }


@dataclass
class StoryboardPlan:
    global_environment: str
    total_panels: int
    layout_type: str
    panels: List[StoryboardPanel]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "global_environment": self.global_environment,
            "total_panels": self.total_panels,
            "layout_type": self.layout_type,
            "panels": [p.to_dict() for p in self.panels]
        }


class StoryboardDirector:
    """
    Planner sitting between LLM extraction and image generation.
    It takes the raw extracted scenes and creates a structured panel-by-panel
    cinematic comic plan, complete with narrative roles, shots, lighting, and transitions.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or getattr(settings, "LLM_MODEL", "llama3")
        # Ollama locally, or Groq cloud when LLM_PROVIDER=groq (same .chat() shape).
        self.client = get_chat_client()

    def _wait_for_ollama(self, timeout: int = 30) -> bool:
        """
        Poll the Ollama HTTP endpoint until it responds or timeout expires.
        When using a remote provider (Groq), there is no local server to wait for.
        """
        if using_groq():
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = httpx.get(f"{getattr(settings, 'OLLAMA_HOST', 'http://127.0.0.1:11434')}/api/tags", timeout=2)
                if r.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def _repair_json(self, text: str) -> str:
        """Fix llama3's split-array output."""
        return re.sub(r'\}\]\s*,\s*\[', '}, ', text)

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extract a valid storyboard JSON object from LLM output.
        Handles enclosing brackets depth parsing.
        """
        search_from = 0
        while True:
            start = text.find('{', search_from)
            if start == -1:
                return None

            depth = 0
            in_string = False
            escape = False
            end = -1
            for i, ch in enumerate(text[start:], start):
                if escape:
                    escape = False
                    continue
                if ch == '\\' and in_string:
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break

            if end == -1:
                return None

            candidate = text[start:end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            search_from = start + 1

    def _validate_plan_errors(self, plan_dict: dict, expected_count: int) -> List[str]:
        errors = []
        if not isinstance(plan_dict, dict):
            errors.append("Output is not a JSON object/dictionary.")
            return errors

        # Check total_panels and panels list
        total_panels = plan_dict.get("total_panels")
        panels = plan_dict.get("panels")

        if not isinstance(panels, list):
            errors.append("The 'panels' field is missing or not a list.")
            return errors

        if len(panels) != expected_count:
            errors.append(f"Expected exactly {expected_count} panels, but got {len(panels)} panels in 'panels' list.")

        if total_panels != len(panels):
            errors.append(f"Field 'total_panels' ({total_panels}) does not match actual length of panels list ({len(panels)}).")

        required_fields = [
            "scene_id", "panel_id", "narrative_purpose", "emotion", "camera_shot",
            "panel_size", "lighting", "focus_character", "action", "dialogue",
            "transition_from_previous", "tension_level"
        ]

        for idx, panel in enumerate(panels):
            if not isinstance(panel, dict):
                errors.append(f"Panel at index {idx} is not an object/dictionary.")
                continue

            # Check all required fields
            for field_name in required_fields:
                if field_name not in panel:
                    errors.append(f"Panel {idx + 1} is missing the '{field_name}' field.")

            # Check tension_level
            tension = panel.get("tension_level")
            if tension is not None:
                try:
                    tension_val = int(tension)
                    if not (1 <= tension_val <= 10):
                        errors.append(f"Panel {idx + 1} 'tension_level' is {tension_val}, which is not between 1 to 10.")
                except (ValueError, TypeError):
                    errors.append(f"Panel {idx + 1} 'tension_level' is not an integer.")
            else:
                errors.append(f"Panel {idx + 1} 'tension_level' is missing.")

            # Check dialogue format
            dialogue = panel.get("dialogue")
            if dialogue is not None:
                if not isinstance(dialogue, list):
                    errors.append(f"Panel {idx + 1} 'dialogue' is not a list.")
                else:
                    for d_idx, d in enumerate(dialogue):
                        if not isinstance(d, dict):
                            errors.append(f"Panel {idx + 1} dialogue item {d_idx + 1} is not an object/dictionary.")
                            continue
                        if "speaker" not in d or "type" not in d or "text" not in d:
                            errors.append(f"Panel {idx + 1} dialogue item {d_idx + 1} is missing speaker, type, or text fields.")

        return errors

    def validate_and_apply_overrides(self, plan: StoryboardPlan, scene_json: dict = None) -> StoryboardPlan:
        panels = plan.panels
        n = len(panels)
        if n == 0:
            return plan


        # 0. Environment lock across panels (Fix 2 & Improvement 2)
        # Extract environment from Panel 1's action description (or global_environment if not clear)
        first_panel = panels[0]
        locked_environment = ""
        action_text = first_panel.action
        first_phrase = ""
        parts = re.split(r'[,.]', action_text) if action_text else []
        if parts:
            first_phrase = parts[0].strip()
        
        # Check if the first phrase looks like an environment description
        if first_phrase and ((any(word in first_phrase.lower() for word in ["room", "street", "outside", "inside", "indoor", "outdoor", "background", "setting", "location", "place", "scene"]) 
            or first_phrase.lower().startswith(("in ", "at ", "inside ", "outside ", "on "))) and len(first_phrase.split()) <= 12):
            locked_environment = first_phrase
        else:
            locked_environment = plan.global_environment
            
        print(f"[Storyboard] Locked environment extracted: '{locked_environment}'")
        
        # Improvement 2: SHORT environment anchor
        locked_lower = locked_environment.lower() if locked_environment else ""
        if "room" in locked_lower or "indoor" in locked_lower or "table" in locked_lower:
            environment_anchor = "indoor room, interior,"
        elif "outdoor" in locked_lower or "street" in locked_lower or "field" in locked_lower:
            environment_anchor = "outdoor scene, exterior,"
        elif "forest" in locked_lower or "nature" in locked_lower:
            environment_anchor = "forest, nature, trees,"
        else:
            environment_anchor = ""

        # Prepend short environment anchor to lighting fields of EVERY panel
        if environment_anchor:
            for p in panels:
                if p.lighting and not p.lighting.lower().startswith(environment_anchor.lower()):
                    p.lighting = f"{environment_anchor} {p.lighting}"

        # Prepend locked_environment to action and lighting fields of Panels 2+
        for i in range(1, n):
            p = panels[i]
            if locked_environment:
                if p.action and not p.action.lower().startswith(locked_environment.lower()):
                    p.action = f"{locked_environment}, {p.action}"
                if p.lighting and not p.lighting.lower().startswith(locked_environment.lower()):
                    p.lighting = f"{locked_environment}, {p.lighting}"

        # 0.5 Dialogue distribution across panels (Fix 1)
        # Move Panel 1 dialogue to Panel 2 if total_panels >= 3
        if n >= 3 and panels[0].dialogue:
            p1 = panels[0]
            p2 = panels[1]
            p2.dialogue = p1.dialogue + p2.dialogue
            moved_text = " ".join([d.get("text", "") for d in p1.dialogue]).strip()
            print(f"[Storyboard] Dialogue '{moved_text[:30]}...' assigned to Panel 2 (tension={p2.tension_level}, rule=panel1_moved)")
            p1.dialogue = []

        # Find panels with identical dialogue text (case-insensitive, item by item)
        dialogues_by_text = {}
        for idx, panel in enumerate(panels):
            if not panel.dialogue:
                continue
            # Deduplicate dialogues within the same panel first
            unique_panel_dialogue = []
            seen_panel_texts = set()
            for d in panel.dialogue:
                txt = d.get("text", "").strip()
                txt_lower = txt.lower()
                if txt_lower not in seen_panel_texts:
                    seen_panel_texts.add(txt_lower)
                    unique_panel_dialogue.append(d)
            panel.dialogue = unique_panel_dialogue

            for d in panel.dialogue:
                txt = d.get("text", "").strip()
                if not txt:
                    continue
                txt_lower = txt.lower()
                if txt_lower not in dialogues_by_text:
                    dialogues_by_text[txt_lower] = []
                if panel not in dialogues_by_text[txt_lower]:
                    dialogues_by_text[txt_lower].append(panel)

        for txt_lower, duplicate_panels in dialogues_by_text.items():
            if len(duplicate_panels) > 1:
                # Keep dialogue only on the panel with the HIGHEST tension_level
                # If two panels have equal tension: keep on the LATER panel
                max_tension = max(p.tension_level for p in duplicate_panels)
                highest_tension_panels = [p for p in duplicate_panels if p.tension_level == max_tension]
                
                if len(highest_tension_panels) == 1:
                    best_panel = highest_tension_panels[0]
                    rule_used = "highest_tension"
                else:
                    best_panel = max(highest_tension_panels, key=lambda p: p.panel_id)
                    rule_used = "later_panel"
                
                original_text = ""
                for p in duplicate_panels:
                    for d in p.dialogue:
                        if d.get("text", "").strip().lower() == txt_lower:
                            original_text = d.get("text", "").strip()
                            break
                    if original_text:
                        break
                if not original_text:
                    original_text = txt_lower
                
                print(f"[Storyboard] Dialogue '{original_text[:30]}...' assigned to Panel {best_panel.panel_id} (tension={best_panel.tension_level}, rule={rule_used})")
                for p in duplicate_panels:
                    if p != best_panel:
                        p.dialogue = [d for d in p.dialogue if d.get("text", "").strip().lower() != txt_lower]

        # Enforce minimum tension floor of 7 for action layouts with sword/clash/blade keywords
        if plan.layout_type and plan.layout_type.lower() == "action":
            for p in panels:
                act_lower = (p.action or "").lower()
                if any(w in act_lower for w in ["sword", "clash", "blade"]):
                    if p.tension_level < 7:
                        print(f"[Storyboard] Action panel {p.panel_id} contains combat keywords. Setting tension_level from {p.tension_level} to 7.")
                        p.tension_level = 7

        # 1. First panel pacing validation
        if n >= 3:
            first_panel = panels[0]
            if first_panel.camera_shot == "EXTREME_CLOSE_UP":
                old_shot = first_panel.camera_shot
                first_panel.camera_shot = "WIDE"
                print(f"[Storyboard] Panel 1 camera overridden: {old_shot} -> WIDE (rule: first_panel_pacing)")

        # 2. Last panel character show validation (only for multi-panel grids)
        if n > 1:
            last_panel = panels[-1]
            invalid_last_shots = {"ESTABLISHING", "WIDE", "WIDE_SHORT", "HIGH_ANGLE"}
            if last_panel.camera_shot in invalid_last_shots:
                old_shot = last_panel.camera_shot
                last_panel.camera_shot = "MEDIUM_CLOSE"
                print(f"[Storyboard] Panel {last_panel.panel_id} camera overridden: {old_shot} -> MEDIUM_CLOSE (rule: last_panel_must_show_character)")

        # V3: Cinematic Sequence Auto-Selection
        # Detect scene type from the overall plan and apply named camera progressions
        if n >= 2:
            # Use first panel's action + emotion to detect sequence type
            first_action = panels[0].action or ""
            first_emotion = panels[0].emotion or ""
            first_narrative = panels[0].narrative_purpose or ""
            # Also scan all panels' actions for stronger signal
            all_actions = " ".join([(p.action or "") for p in panels])
            detected_seq = detect_sequence_type(all_actions, first_emotion, first_narrative)

            if detected_seq and detected_seq in CINEMATIC_SEQUENCES:
                seq_track = CINEMATIC_SEQUENCES[detected_seq]
                print(f"[Storyboard] V3 Cinematic Sequence detected: {detected_seq}")
                # Apply sequence track to panels, cycling if plan has more panels than track
                for i, panel in enumerate(panels):
                    desired_shot = seq_track[i % len(seq_track)]
                    # Only override if the current shot doesn't already match and
                    # the panel doesn't have a manually locked shot
                    if panel.camera_shot != desired_shot:
                        old = panel.camera_shot
                        panel.camera_shot = desired_shot
                        print(f"[Storyboard] Panel {panel.panel_id}: {old} -> {desired_shot} (sequence: {detected_seq})")

        # 3. Panel Variety Enforcer (Requirement A)
        if n > 1:
            layout_key = (plan.layout_type or "standard").lower()
            if "action" in layout_key:
                track = ["WIDE", "MEDIUM", "CLOSE_UP", "ACTION_DYNAMIC", "WIDE"]
            elif "dialog" in layout_key or "drama" in layout_key:
                track = ["WIDE", "MEDIUM", "CLOSE_UP", "MEDIUM_CLOSE", "WIDE"]
            else:
                track = ["WIDE", "MEDIUM", "CLOSE_UP", "MEDIUM_CLOSE", "WIDE"]

            for i in range(1, n):
                if panels[i].camera_shot == panels[i-1].camera_shot:
                    old_shot = panels[i].camera_shot
                    track_idx = i % len(track)
                    new_shot = track[track_idx]
                    if new_shot == panels[i-1].camera_shot:
                        new_shot = track[(track_idx + 1) % len(track)]
                    panels[i].camera_shot = new_shot
                    print(f"[Panel Variety Enforcer] Shifted Panel {panels[i].panel_id} camera_shot from {old_shot} to {new_shot} to prevent adjacent duplication")

        # 4. Tension arc validation and fixes (only for multi-panel grids)
        if n > 1:
            tensions = [p.tension_level for p in panels]
            all_same = len(set(tensions)) <= 1
            if all_same:
                if n == 3:
                    panels[0].tension_level = 3
                    panels[1].tension_level = 8
                    panels[2].tension_level = 5
                elif n == 4:
                    panels[0].tension_level = 3
                    panels[1].tension_level = 5
                    panels[2].tension_level = 8
                    panels[3].tension_level = 4
                else:
                    peak_idx = n - 2
                    for idx, p in enumerate(panels):
                        if idx < peak_idx:
                            p.tension_level = 3 + int((idx / peak_idx) * 5)
                        elif idx == peak_idx:
                            p.tension_level = 8
                        else:
                            p.tension_level = 4
                print(f"[Storyboard] Tension arc overridden due to flat tension inputs: {[p.tension_level for p in panels]}")

        # V3: Tension-Weighted Shot Refinement
        # High tension panels (>= 7) push toward tighter, more dramatic shots
        # Low tension panels (<= 3) push toward wider, more establishing shots
        HIGH_TENSION_SHOTS = {"CLOSE_UP", "EXTREME_CLOSE_UP", "ACTION_DYNAMIC", "DUTCH_ANGLE", "LOW_ANGLE"}
        LOW_TENSION_SHOTS = {"WIDE", "ESTABLISHING", "MEDIUM"}
        for panel in panels:
            if panel.tension_level >= 8 and panel.camera_shot not in HIGH_TENSION_SHOTS:
                # Escalate to a dramatic close shot
                old = panel.camera_shot
                if panel.camera_shot in ("MEDIUM", "MEDIUM_CLOSE"):
                    panel.camera_shot = "CLOSE_UP"
                elif panel.camera_shot in ("WIDE", "ESTABLISHING"):
                    panel.camera_shot = "ACTION_DYNAMIC"
                print(f"[Storyboard] Panel {panel.panel_id}: tension={panel.tension_level} escalated {old} -> {panel.camera_shot}")
            elif panel.tension_level <= 3 and panel.camera_shot not in LOW_TENSION_SHOTS:
                # De-escalate to a wider, calmer shot
                old = panel.camera_shot
                panel.camera_shot = "MEDIUM"
                print(f"[Storyboard] Panel {panel.panel_id}: tension={panel.tension_level} de-escalated {old} -> {panel.camera_shot}")

        # Block tight shots (CLOSE_UP, EXTREME_CLOSE_UP) only when both characters appear together in the frame
        for p in panels:
            if p.camera_shot in ("CLOSE_UP", "EXTREME_CLOSE_UP"):
                scene_characters = []
                if scene_json:
                    scenes = scene_json.get("scenes", [])
                    for s in scenes:
                        if s.get("scene_id") == p.scene_id:
                            scene_characters = s.get("characters", [])
                            break
                    if not scene_characters and scenes:
                        scene_characters = scenes[0].get("characters", [])
                
                char_names = [c.get("name") for c in scene_characters if c.get("name")]
                if len(char_names) >= 2:
                    focus = p.focus_character
                    secondary = ""
                    for name in char_names:
                        if name.lower() != (focus or "").strip().lower():
                            secondary = name
                            break
                    if is_shared_frame_panel(focus, secondary, p.action):
                        old_shot = p.camera_shot
                        p.camera_shot = "MEDIUM_CLOSE"
                        print(f"[Storyboard] Scoped override on Panel {p.panel_id}: {old_shot} -> MEDIUM_CLOSE (both characters in frame)")

        # Emotion floor for high-tension beats — applied LAST, after the tension arc
        # override + combat-keyword escalation have set each panel's FINAL tension. The
        # LLM frequently tags an intense moment "neutral"/"calm", rendering a flat face.
        # But the upgrade must be GENRE-AWARE: a romance climax also scores high tension,
        # and hardening it to "intense" (cold, unflinching eyes) is wrong. So infer from
        # the action — combat -> intense; emotional/romance -> a fitting soft emotion;
        # otherwise a generic dramatic "intense". [QA 2026-06-28]
        _combat_kw = ("fight", "clash", "strike", "attack", "sword", "blade", "punch",
                      "kick", "slash", "battle", "charge", "swing", "blow", "combat",
                      "shoot", "explos", "slam", "smash", "stab", "lunge", "duel")
        _tender_kw = ("love", "kiss", "embrace", "hug", "tender", "gentle", "blush",
                      "caress", "hold", "romance", "cherish", "whisper", "hand")
        _grief_kw = ("tear", "cry", "weep", "sob", "mourn", "grief", "sorrow")
        for p in panels:
            if p.tension_level >= 7 and str(p.emotion).strip().lower() in ("neutral", "calm", "none", ""):
                act = (p.action or "").lower()
                if any(k in act for k in _combat_kw):
                    p.emotion = "intense"
                elif any(k in act for k in _grief_kw):
                    p.emotion = "sad"
                elif any(k in act for k in _tender_kw):
                    p.emotion = "romantic_affection"
                else:
                    p.emotion = "intense"

        return plan

    def _build_storyboard_plan(self, plan_dict: dict, fallback_layout: str, scene_json: dict = None) -> StoryboardPlan:
        global_env = plan_dict.get("global_environment") or "cinematic scene"
        total_panels = plan_dict.get("total_panels") or len(plan_dict.get("panels", []))
        layout_type = plan_dict.get("layout_type") or fallback_layout

        panels_list = []
        for idx, p in enumerate(plan_dict.get("panels", [])):
            try:
                scene_id = int(p.get("scene_id", 1))
            except (ValueError, TypeError):
                scene_id = 1

            try:
                panel_id = int(p.get("panel_id", idx + 1))
            except (ValueError, TypeError):
                panel_id = idx + 1

            narrative_purpose = p.get("narrative_purpose") or "Advance the narrative beat."
            emotion = p.get("emotion") or "neutral"
            camera_shot = p.get("camera_shot") or "MEDIUM"
            if str(layout_type).lower() in ["drama", "dialogue"] and str(camera_shot).upper() == "ACTION_DYNAMIC":
                camera_shot = "MEDIUM_CLOSE"
            panel_size = p.get("panel_size") or "medium"
            lighting = p.get("lighting") or "cinematic"
            focus_character = p.get("focus_character") or ""
            action = p.get("action") or "The scene continues."

            dialogue_raw = p.get("dialogue") or []
            dialogue_list = []
            if isinstance(dialogue_raw, list):
                for d in dialogue_raw:
                    if isinstance(d, dict):
                        dialogue_list.append({
                            "speaker": d.get("speaker") or "Narrator",
                            "type": d.get("type") or "speech",
                            "text": d.get("text") or ""
                        })
                    elif isinstance(d, str) and d.strip():
                        dialogue_list.append({
                            "speaker": focus_character or "Narrator",
                            "type": "speech",
                            "text": d.strip()
                        })
            elif isinstance(dialogue_raw, dict):
                dialogue_list.append({
                    "speaker": dialogue_raw.get("speaker") or focus_character or "Narrator",
                    "type": dialogue_raw.get("type") or "speech",
                    "text": dialogue_raw.get("text") or ""
                })
            elif isinstance(dialogue_raw, str) and dialogue_raw.strip():
                dialogue_list.append({
                    "speaker": focus_character or "Narrator",
                    "type": "speech",
                    "text": dialogue_raw.strip()
                })

            transition = p.get("transition_from_previous") or ("None" if panel_id == 1 else "cut to next panel")

            try:
                tension = int(p.get("tension_level", 5))
                if not (1 <= tension <= 10):
                    tension = 5
            except (ValueError, TypeError):
                tension = 5

            panel_obj = StoryboardPanel(
                scene_id=scene_id,
                panel_id=panel_id,
                narrative_purpose=str(narrative_purpose),
                emotion=str(emotion),
                camera_shot=str(camera_shot),
                panel_size=str(panel_size),
                lighting=str(lighting),
                focus_character=str(focus_character),
                action=str(action),
                dialogue=dialogue_list,
                transition_from_previous=str(transition),
                tension_level=tension
            )
            panels_list.append(panel_obj)

        plan = StoryboardPlan(
            global_environment=str(global_env),
            total_panels=int(total_panels),
            layout_type=str(layout_type),
            panels=panels_list
        )
        return self.validate_and_apply_overrides(plan, scene_json)

    def _generate_fallback_plan(self, scene_json: dict, expected_count: int, layout_type: str) -> StoryboardPlan:
        global_env = scene_json.get("global_environment") or "cinematic scene"
        scenes = scene_json.get("scenes", [])

        # Pad or trim scenes list to match expected_count
        scenes_subset = []
        if scenes:
            if len(scenes) > expected_count:
                scenes_subset = scenes[:expected_count]
            elif len(scenes) < expected_count:
                scenes_subset = list(scenes)
                while len(scenes_subset) < expected_count:
                    last_scene = scenes_subset[-1] if scenes_subset else {}
                    new_scene = dict(last_scene) if last_scene else {
                        "scene_id": len(scenes_subset) + 1,
                        "environment": global_env,
                        "focus_character": "",
                        "characters": [],
                        "action": "The scene continues.",
                        "emotion": "calm",
                        "dialogue": []
                    }
                    if last_scene:
                        new_scene["scene_id"] = len(scenes_subset) + 1
                    scenes_subset.append(new_scene)
            else:
                scenes_subset = scenes
        else:
            for idx in range(expected_count):
                scenes_subset.append({
                    "scene_id": idx + 1,
                    "environment": global_env,
                    "focus_character": "",
                    "characters": [],
                    "action": "The scene continues.",
                    "emotion": "calm",
                    "dialogue": []
                })

        fallback_panels = []
        for idx, scene in enumerate(scenes_subset):
            panel_id = idx + 1
            scene_id = scene.get("scene_id", 1)
            action = scene.get("action") or "The scene continues."
            focus_character = scene.get("focus_character") or ""
            dialogue = scene.get("dialogue") or []

            dialogue_list = []
            if isinstance(dialogue, list):
                for d in dialogue:
                    if isinstance(d, dict):
                        dialogue_list.append({
                            "speaker": d.get("speaker") or "Narrator",
                            "type": d.get("type") or "speech",
                            "text": d.get("text") or ""
                        })

            # Call action and emotion classifiers
            action_map = classify_action(action)
            detected_emotion = classify_emotion(action) or "neutral"
            
            camera_shot = "MEDIUM"
            enriched_action = action
            if action_map:
                # Map camera
                raw_cam = action_map["camera"].upper().replace(" SHOT", "").strip()
                if "CLOSEUP" in raw_cam:
                    camera_shot = "CLOSE_UP"
                elif "EXTREME_CLOSE_UP" in raw_cam:
                    camera_shot = "EXTREME_CLOSE_UP"
                elif "WIDE" in raw_cam:
                    camera_shot = "WIDE"
                elif "LOW ANGLE" in raw_cam or "LOW_ANGLE" in raw_cam:
                    camera_shot = "LOW_ANGLE"
                elif "HIGH ANGLE" in raw_cam or "HIGH_ANGLE" in raw_cam:
                    camera_shot = "HIGH_ANGLE"
                elif "DUTCH ANGLE" in raw_cam or "DUTCH_ANGLE" in raw_cam:
                    camera_shot = "DUTCH_ANGLE"
                elif "ACTION" in raw_cam:
                    camera_shot = "ACTION_DYNAMIC"
                else:
                    camera_shot = raw_cam
                
                # Enrich action with pose and composition
                enriched_action = f"{action}, pose: {action_map['pose']}, composition: {action_map['composition']}"

            # Use procedural defaults: emotion: neutral, camera: MEDIUM, tension: 5
            panel = StoryboardPanel(
                scene_id=scene_id,
                panel_id=panel_id,
                narrative_purpose=f"Procedural fallback panel to showcase the scene beat: {action[:50]}...",
                emotion=detected_emotion,
                camera_shot=camera_shot,
                panel_size="medium",
                lighting="cinematic",
                focus_character=focus_character,
                action=enriched_action,
                dialogue=dialogue_list,
                transition_from_previous="None" if panel_id == 1 else "cut to next panel",
                tension_level=5
            )
            fallback_panels.append(panel)

        plan = StoryboardPlan(
            global_environment=global_env,
            total_panels=expected_count,
            layout_type=layout_type,
            panels=fallback_panels
        )
        return self.validate_and_apply_overrides(plan, scene_json)

    def plan(
        self,
        scene_json: dict,
        panel_count: Optional[int] = None,
        layout_type: Optional[str] = None
    ) -> StoryboardPlan:
        """
        Orchestrate panel planning by calling Ollama LLM, validating responses,
        attempting automatic corrections, and falling back gracefully on failure.
        """
        # 1. Determine target panel count and layout type
        target_panel_count = 3  # default fallback

        if panel_count is not None:
            target_panel_count = panel_count
        elif layout_type is not None:
            layout_lower = layout_type.lower()
            if "action" in layout_lower:
                target_panel_count = 4
            elif "drama" in layout_lower:
                target_panel_count = 3
            elif "dialog" in layout_lower or "talk" in layout_lower:
                target_panel_count = 2
            else:
                target_panel_count = 3
        else:
            # Both preferences are None: calculate based on text length
            word_count = 0
            if scene_json and "source_text" in scene_json:
                word_count = len(str(scene_json["source_text"]).split())
            elif scene_json:
                text_parts = []
                for s in scene_json.get("scenes", []):
                    text_parts.append(str(s.get("action", "")))
                    for d in s.get("dialogue", []):
                        text_parts.append(str(d.get("text", "")))
                word_count = len(" ".join(text_parts).split())

            if word_count < 100:
                target_panel_count = 3
            elif word_count < 250:
                target_panel_count = 4
            else:
                target_panel_count = 6

        target_panel_count = min(max(target_panel_count, 1), getattr(settings, "MAX_PANELS_PER_COMIC", 6))
        target_layout = layout_type or "standard"

        # 2. Wait for Ollama to be available
        if not self._wait_for_ollama(timeout=10):
            print("[StoryboardDirector] Ollama not reachable — proceeding to fallback plan.")
            return self._generate_fallback_plan(scene_json, target_panel_count, target_layout)

        # 3. Construct system prompt
        single_page_instruction = ""
        if target_panel_count == 1:
            single_page_instruction = """
IMPORTANT SINGLE-PAGE MODE INSTRUCTION:
You are planning ONE single cinematic panel that captures the entire emotional essence of this scene. Choose the single most powerful moment. This is a full-page webtoon-style image. Choose a camera angle that feels cinematic and intentional (such as MEDIUM_CLOSE, CLOSE_UP, or WIDE).
"""

        system_prompt = f"""You are an expert Comic Storyboard Director.
Your task is to take the extracted scenes from a novel (provided in JSON format) and plan a detailed, panel-by-panel comic layout.
You must output a single, valid JSON object containing exactly the fields requested, with no markdown formatting, no explanations, and no trailing characters.{single_page_instruction}

The target number of panels is {target_panel_count}.
The layout style requested is "{target_layout}".

Your output must strictly follow this JSON schema:
{{
  "global_environment": "<environment in 4-10 words; you MUST keep the era/setting words from the story (ancient, ruined, medieval, futuristic, snowy, underwater, etc.) and the specific place — e.g. 'ancient ruined marketplace at night', NOT a generic 'rain-soaked streets'>",
  "total_panels": {target_panel_count},
  "layout_type": "{target_layout}",
  "panels": [
    {{
      "scene_id": <integer, corresponding scene_id from input>,
      "panel_id": <integer, sequential from 1 to {target_panel_count}>,
      "narrative_purpose": "<brief explanation of what this panel achieves narrative-wise>",
      "emotion": "<dominant emotion, e.g. neutral, surprised, intense, calm, angry, sad>",
      "camera_shot": "<WIDE, MEDIUM, CLOSE_UP, or EXTREME_CLOSE_UP>",
      "panel_size": "<small, medium, large, or wide>",
      "lighting": "<lighting style, e.g. dramatic, soft, high-key, cinematic, dark>",
      "focus_character": "<name of character under focus, or empty>",
      "action": "<rich, cinematic visual description of THIS panel: the character's action/pose AND the concrete setting/atmosphere visible in frame — weather, time of day, lighting, background objects and mood — drawn faithfully from the source text (e.g. 'the knight kneels in the rain before the crying girl amid broken carts and smoldering ruins, moonlight catching his dented armor'). Preserve the source's vivid details; do NOT flatten them to a generic summary>",
      "dialogue": [
        {{
          "speaker": "<character name or Narrator>",
          "type": "speech|narration",
          "text": "<dialogue spoken or narrated in this panel>"
        }}
      ],
      "transition_from_previous": "<visual flow description, or 'None' if first panel>",
      "tension_level": <integer from 1 to 10>
    }}
  ]
}}

Rules:
1. You must output exactly {target_panel_count} panels in the "panels" list.
2. The field "tension_level" must be an integer between 1 and 10.
3. Every single field listed above must be present for every panel.
4. Output ONLY the JSON. No conversational filler, no ```json tags, no explanation.
5. IMPORTANT: The final panel must always show a character's face or upper body clearly (unless in single-panel/single-page mode). Never use ESTABLISHING or WIDE shots for the last panel when generating multiple panels. The last panel should feel like a closing emotional beat.
6. Vary lighting across panels. Do not use the same lighting for every panel. Mix: dramatic side lighting, silhouette, soft ambient, harsh overhead, warm/cool contrast.
7. Each panel should have a different background element visible. Even if in the same location, vary: close wall vs open sky, foreground object vs empty space, inside vs outside view.
8. All panels must take place in the same location unless the story explicitly describes a location change. Do not change the setting between panels.
"""

        # Serialize scene_json for the user prompt
        serialized_input = json.dumps(scene_json, indent=2)
        user_prompt = f"Please plan a storyboard with {target_panel_count} panels from this input data:\n\n{serialized_input}"

        parsed_plan = None
        errors = []

        # --- ATTEMPT 1 ---
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={
                    "temperature": 0.3,
                    "num_ctx": 8192,
                    "num_predict": 4000,
                    "keep_alive": getattr(settings, "LLM_KEEP_ALIVE", "15s")
                }
            )
            content = response["message"]["content"]
            clean_content = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
            clean_content = self._repair_json(clean_content)
            parsed_plan = self._extract_json(clean_content)

            if parsed_plan:
                errors = self._validate_plan_errors(parsed_plan, target_panel_count)
                if not errors:
                    return self._build_storyboard_plan(parsed_plan, target_layout, scene_json)
                else:
                    print(f"[StoryboardDirector] Attempt 1 validation errors: {errors}")
            else:
                errors = ["Failed to extract/parse JSON from output."]
                print("[StoryboardDirector] Attempt 1 failed to parse JSON.")

        except Exception as exc:
            errors = [f"Exception occurred in Attempt 1: {exc}"]
            print(f"[StoryboardDirector] Exception on Attempt 1: {exc}")

        # --- ATTEMPT 2 (Correction / Retry) ---
        print("[StoryboardDirector] Initiating Attempt 2 (Correction/Retry)...")
        correction_prompt = f"""Your previous response was malformed or failed validation.
Errors encountered:
{chr(10).join('- ' + err for err in errors)}

Please correct these issues and output a perfect, valid JSON matching the schema and rules.
Ensure exactly {target_panel_count} panels are returned in the "panels" list.
Tension levels must be 1 to 10.
Output ONLY the valid JSON object. No other text.
"""
        try:
            history = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            if 'content' in locals() and content:
                history.append({"role": "assistant", "content": content})
            history.append({"role": "user", "content": correction_prompt})

            response = self.client.chat(
                model=self.model_name,
                messages=history,
                options={
                    "temperature": 0.2,
                    "num_ctx": 8192,
                    "num_predict": 4000,
                    "keep_alive": getattr(settings, "LLM_KEEP_ALIVE", "15s")
                }
            )
            content_2 = response["message"]["content"]
            clean_content_2 = re.sub(r"```(?:json)?\s*", "", content_2).replace("```", "").strip()
            clean_content_2 = self._repair_json(clean_content_2)
            parsed_plan_2 = self._extract_json(clean_content_2)

            if parsed_plan_2:
                errors_2 = self._validate_plan_errors(parsed_plan_2, target_panel_count)
                if not errors_2:
                    return self._build_storyboard_plan(parsed_plan_2, target_layout, scene_json)
                else:
                    print(f"[StoryboardDirector] Attempt 2 validation errors: {errors_2}")
            else:
                print("[StoryboardDirector] Attempt 2 failed to parse JSON.")

        except Exception as exc:
            print(f"[StoryboardDirector] Exception on Attempt 2: {exc}")

        # --- PROCEDURAL FALLBACK DEFAULTS ---
        print("[StoryboardDirector] Both attempts failed. Triggering robust procedural fallback plan.")
        return self._generate_fallback_plan(scene_json, target_panel_count, target_layout)
