"""
prompt_builder.py
-----------------
Minimal, prompt-driven. No forced camera angles, no PANEL_LOCKS.
Prompt structure: camera, emotion, lighting, character, action/environment, style.
"""
import difflib
from config import settings

# Detailed style templates mapping prefix and lighting_override
STYLE_TEMPLATES = {
    "anime": {
        "prefix": "anime illustration, vibrant colors, clean lineart",
        "lighting_override": "vibrant lighting, colorful shadows"
    },
    "manga": {
        "prefix": "manga illustration, black and white, high contrast ink lines, screentone",
        "lighting_override": "stark shadows, high-contrast lighting"
    },
    "manhwa": {
        "prefix": "manhwa webtoon illustration, soft digital coloring, detailed background",
        "lighting_override": "soft studio lighting, gentle ambient glow"
    },
    "manhua": {
        "prefix": "manhua illustration, traditional chinese ink painting style, watercolor wash brushstrokes",
        "lighting_override": "natural soft lighting, misty atmosphere"
    },
    "cinematic": {
        "prefix": "cinematic film still, photorealistic, dramatic scene, highly detailed",
        "lighting_override": "dramatic cinematic lighting, volumetric raytracing, chiaroscuro"
    },
    "realistic": {
        "prefix": "realistic photograph, highly detailed, photorealistic, 8k resolution",
        "lighting_override": "natural sunlight, photorealistic reflections"
    }
}


class PromptBuilder:

    def __init__(self, style: str = None):
        # Style is injected at construction or overridden per call
        self.style = style or getattr(settings, "DEFAULT_STYLE", "anime")
        self.last_positive_prompt = None
        self.variation_index = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _gender_tag(self, character: dict) -> str:
        """Return gender enforcement tokens if the character has them."""
        return character.get("_gender_tag", "")

    def _gender_negative(self, character: dict) -> str:
        return character.get("_negative_gender", "")

    def _character_token(self, character: dict, is_focus: bool, memory_manager=None) -> str:
        """
        Build a compact character token.
        Priority: name + description + gender tag.
        """
        name  = str(character.get("name", "")).strip()
        
        sheet = None
        if memory_manager and hasattr(memory_manager, "get_design_sheet"):
            sheet = memory_manager.get_design_sheet(name)

        if sheet:
            desc = sheet.to_prompt_tokens()
        else:
            desc = str(character.get("description", "")).strip()

        gtag  = self._gender_tag(character)

        parts = [p for p in [name, desc, gtag] if p]
        token = ", ".join(parts)

        # Consistency anchor for non-first panels
        if is_focus and character.get("_is_continuation"):
            token += ", same face, same outfit, same hairstyle"

        return token

    def _style_token(self) -> str:
        """Legacy helper for fallback/compatibility."""
        style = self.style.lower()
        if style in STYLE_TEMPLATES:
            return STYLE_TEMPLATES[style]["prefix"]
        return f"{style} illustration"

    def _to_tokens(self, text_or_list) -> list[str]:
        """Convert a string or list of strings into clean comma-separated tokens."""
        if not text_or_list:
            return []
        if isinstance(text_or_list, list):
            items = text_or_list
        else:
            items = [text_or_list]
        
        tokens = []
        for item in items:
            if not item:
                continue
            for part in str(item).split(","):
                part_stripped = part.strip()
                if part_stripped:
                    tokens.append(part_stripped)
        return tokens

    def _deduplicate_tokens(self, tokens: list[str]) -> list[str]:
        """Deduplicate tokens while preserving original order."""
        seen = set()
        deduped = []
        for t in tokens:
            t_lower = t.lower()
            if t_lower not in seen:
                seen.add(t_lower)
                deduped.append(t)
        return deduped

    def _calculate_similarity(self, prompt1: str, prompt2: str) -> float:
        """Calculate similarity between two prompts using SequenceMatcher and Jaccard."""
        if not prompt1 or not prompt2:
            return 0.0
        p1 = prompt1.lower().strip()
        p2 = prompt2.lower().strip()
        
        # SequenceMatcher ratio
        seq_ratio = difflib.SequenceMatcher(None, p1, p2).ratio()
        
        # Jaccard word-level similarity
        w1 = set(p1.replace(",", " ").split())
        w2 = set(p2.replace(",", " ").split())
        jaccard = len(w1 & w2) / len(w1 | w2) if (w1 or w2) else 0.0
        
        return max(seq_ratio, jaccard)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        scene: dict,
        memory_manager,
        is_continuation: bool = False,
        style: str = None,
    ) -> tuple[str, str]:
        """
        Build (positive_prompt, negative_prompt) for a single panel.

        Strict Prompt Construction Layers:
          Layer 1: Camera tokens (positions 1–15)
          Layer 2: Emotion tokens (positions 16–35)
          Layer 3: Character tokens — hairstyle + outfit + gender (positions 36–60)
          Layer 4: Lighting tokens from storyboard (positions 61–70)
          Layer 5: Action and environment (positions 71–90)
          Layer 6: Style prefix tokens (positions 91–110)
        """
        active_style = style or self.style

        # Resolve style template
        style_lower = active_style.lower() if active_style else "anime"
        if style_lower in STYLE_TEMPLATES:
            template = STYLE_TEMPLATES[style_lower]
        else:
            template = {
                "prefix": f"{active_style} illustration",
                "lighting_override": "cinematic lighting"
            }

        # Initialize layer token lists
        l1_camera_tokens = []
        l2_emotion_tokens = []
        l3_lighting_tokens = []
        l4_character_tokens = []
        l5_action_env_tokens = []
        l6_style_tokens = []

        # ----- Layer 1: Camera tokens ----------------------------------
        camera_input = scene.get("camera") or scene.get("camera_angle") or scene.get("shot_type") or ""
        if camera_input:
            l1_camera_tokens.extend(self._to_tokens(camera_input))

        # ----- Layer 2: Emotion tokens ---------------------------------
        emotion_input = scene.get("emotion") or ""
        if emotion_input:
            l2_emotion_tokens.extend(self._to_tokens(emotion_input))
        else:
            l2_emotion_tokens.append("calm expression")

        # ----- Layer 3: Lighting tokens (mapped to Layer 4 visually) ----
        scene_lighting = scene.get("lighting") or scene.get("lighting_setup") or ""
        if scene_lighting:
            l3_lighting_tokens.extend(self._to_tokens(scene_lighting))
        if template.get("lighting_override"):
            l3_lighting_tokens.extend(self._to_tokens(template["lighting_override"]))

        # ----- Layer 4: Character tokens (mapped to Layer 3 visually) ---
        characters = scene.get("characters") or []
        focus_name = str(scene.get("focus_character", "")).lower()

        for char in characters:
            char_name = str(char.get("name", "")).lower()
            is_focus  = focus_name and focus_name in char_name

            # Pull cached description for consistency
            cached_desc = memory_manager.get_character(char.get("name", ""))
            if cached_desc:
                char = dict(char)
                char["description"] = cached_desc

            if is_continuation:
                char = dict(char)
                char["_is_continuation"] = True

            token = self._character_token(char, is_focus=is_focus, memory_manager=memory_manager)
            if token:
                l4_character_tokens.extend(self._to_tokens(token))

        # ----- Layer 5: Action & environment ---------------------------
        action_input = scene.get("action") or ""
        if action_input:
            l5_action_env_tokens.extend(self._to_tokens(action_input))
        
        env_input = scene.get("global_environment") or scene.get("environment") or ""
        if env_input:
            l5_action_env_tokens.extend(self._to_tokens(env_input))

        # ----- Layer 6: Style prefix templates -------------------------
        if template.get("prefix"):
            l6_style_tokens.extend(self._to_tokens(template["prefix"]))

        # Assemble the candidate positive prompt without composition variation first
        cand_l1 = l1_camera_tokens[:15]   # Camera (1-15)
        cand_l2 = l2_emotion_tokens[:20]  # Emotion (16-35)
        cand_l3 = l4_character_tokens[:25] # Character (36-60) - character tokens before lighting!
        cand_l4 = l3_lighting_tokens[:10]  # Lighting (61-70)
        cand_l5 = l5_action_env_tokens[:20] # Action & Env (71-90)
        cand_l6 = l6_style_tokens[:20]     # Style (91-110)

        cand_all = cand_l1 + cand_l2 + cand_l3 + cand_l4 + cand_l5 + cand_l6
        cand_all = self._deduplicate_tokens(cand_all)
        cand_all = cand_all[:110]
        candidate_prompt = ", ".join(cand_all)

        # Consecutive duplicate panel guard
        triggered = False
        if self.last_positive_prompt is not None:
            similarity = self._calculate_similarity(self.last_positive_prompt, candidate_prompt)
            if similarity > 0.70:
                triggered = True

        if triggered:
            VARIATION_TOKENS = ["reversed composition", "mirror framing", "opposite angle"]
            var_token = VARIATION_TOKENS[self.variation_index % len(VARIATION_TOKENS)]
            self.variation_index += 1
            
            # Inject variation at the start of Layer 1
            l1_camera_tokens.insert(0, var_token)
            
            # Re-assemble prompt with the variation included
            cand_l1 = l1_camera_tokens[:15]
            cand_all = cand_l1 + cand_l2 + cand_l3 + cand_l4 + cand_l5 + cand_l6
            cand_all = self._deduplicate_tokens(cand_all)
            cand_all = cand_all[:110]
            candidate_prompt = ", ".join(cand_all)

        # Save final prompt for future comparison
        self.last_positive_prompt = candidate_prompt

        # ----- Negative prompt construction ----------------------------
        neg_parts = [getattr(settings, "PROMPT_NEGATIVE", "")]
        for char in characters:
            neg = self._gender_negative(char)
            if neg:
                neg_parts.append(neg)
                
            # If a design sheet exists for this character name, append its negative tokens
            char_name = char.get("name", "")
            if memory_manager and hasattr(memory_manager, "get_design_sheet"):
                sheet = memory_manager.get_design_sheet(char_name)
                if sheet:
                    neg_parts.append(sheet.to_negative_tokens())

        neg_tokens = []
        for np in neg_parts:
            neg_tokens.extend(self._to_tokens(np))
        neg_tokens = self._deduplicate_tokens(neg_tokens)
        negative = ", ".join(neg_tokens)

        return candidate_prompt, negative

    def apply_reference_conditioning_prompt(
        self, positive_prompt: str, negative_prompt: str
    ) -> tuple[str, str]:
        """
        Tighten identity for panels 2+ that use an IP-Adapter reference image.
        Adds minimal consistency anchors without forcing composition.
        """
        if "same face" not in positive_prompt:
            positive_prompt += ", same face, same outfit, consistent character"
        
        # Keep deduplication and 110-token limit intact
        tokens = self._to_tokens(positive_prompt)
        deduped = self._deduplicate_tokens(tokens)
        positive_prompt = ", ".join(deduped[:110])
        
        return positive_prompt, negative_prompt
