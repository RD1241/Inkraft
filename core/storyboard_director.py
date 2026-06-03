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
        self.client = ollama.Client(host=getattr(settings, "OLLAMA_HOST", "http://127.0.0.1:11434"))

    def _wait_for_ollama(self, timeout: int = 30) -> bool:
        """
        Poll the Ollama HTTP endpoint until it responds or timeout expires.
        """
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

    def _build_storyboard_plan(self, plan_dict: dict, fallback_layout: str) -> StoryboardPlan:
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

        return StoryboardPlan(
            global_environment=str(global_env),
            total_panels=int(total_panels),
            layout_type=str(layout_type),
            panels=panels_list
        )

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

            # Use procedural defaults: emotion: neutral, camera: MEDIUM, tension: 5
            panel = StoryboardPanel(
                scene_id=scene_id,
                panel_id=panel_id,
                narrative_purpose=f"Procedural fallback panel to showcase the scene beat: {action[:50]}...",
                emotion="neutral",
                camera_shot="MEDIUM",
                panel_size="medium",
                lighting="cinematic",
                focus_character=focus_character,
                action=action,
                dialogue=dialogue_list,
                transition_from_previous="None" if panel_id == 1 else "cut to next panel",
                tension_level=5
            )
            fallback_panels.append(panel)

        return StoryboardPlan(
            global_environment=global_env,
            total_panels=expected_count,
            layout_type=layout_type,
            panels=fallback_panels
        )

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

        target_panel_count = min(max(target_panel_count, 1), 10)
        target_layout = layout_type or "standard"

        # 2. Wait for Ollama to be available
        if not self._wait_for_ollama(timeout=10):
            print("[StoryboardDirector] Ollama not reachable — proceeding to fallback plan.")
            return self._generate_fallback_plan(scene_json, target_panel_count, target_layout)

        # 3. Construct system prompt
        system_prompt = f"""You are an expert Comic Storyboard Director.
Your task is to take the extracted scenes from a novel (provided in JSON format) and plan a detailed, panel-by-panel comic layout.
You must output a single, valid JSON object containing exactly the fields requested, with no markdown formatting, no explanations, and no trailing characters.

The target number of panels is {target_panel_count}.
The layout style requested is "{target_layout}".

Your output must strictly follow this JSON schema:
{{
  "global_environment": "<brief environment description, max 8 words>",
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
      "action": "<detailed visual description of the action / pose in this panel>",
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
                    return self._build_storyboard_plan(parsed_plan, target_layout)
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
                    return self._build_storyboard_plan(parsed_plan_2, target_layout)
                else:
                    print(f"[StoryboardDirector] Attempt 2 validation errors: {errors_2}")
            else:
                print("[StoryboardDirector] Attempt 2 failed to parse JSON.")

        except Exception as exc:
            print(f"[StoryboardDirector] Exception on Attempt 2: {exc}")

        # --- PROCEDURAL FALLBACK DEFAULTS ---
        print("[StoryboardDirector] Both attempts failed. Triggering robust procedural fallback plan.")
        return self._generate_fallback_plan(scene_json, target_panel_count, target_layout)
