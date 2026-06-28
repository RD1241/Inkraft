"""
prompt_builder.py
-----------------
Minimal, prompt-driven. No forced camera angles, no PANEL_LOCKS.
Prompt structure: camera, emotion, lighting, character, action/environment, style.
"""
import difflib
from config import settings
from core.action_library import ActionLibrary
from core.interaction_composer import InteractionComposer

_action_library = ActionLibrary()
_interaction_composer = InteractionComposer()

CHARACTER_SEPARATOR_LABELS = ["CHARACTER_A", "CHARACTER_B", "CHARACTER_C"]
BACKGROUND_LABEL = "BACKGROUND_SUPPORTING_CHARACTERS"

# ----------------------------------------------------------------------
# Colour-mode resolution (§10 contract: color_mode = auto | color | bw)
# ----------------------------------------------------------------------
# Positive tokens injected when a panel must be monochrome.
MONOCHROME_TOKENS = ["monochrome", "greyscale", "black and white"]
# Substrings that mark a positive token as monochrome/ink-art; stripped when
# a panel must be in colour (e.g. manga forced to colour by the user).
MONOCHROME_KEYWORDS = [
    "monochrome", "greyscale", "grayscale", "black and white",
    "screentone", "ink wash", "b&w", "high contrast ink",
]
# Negative tokens used to push the model away from the unwanted look.
COLOUR_NEGATIVE = "color, colorful, digital coloring, cel shading, multicolored, chromatic, photo, photographic"
MONOCHROME_NEGATIVE = "monochrome, greyscale, black and white, desaturated"


def resolve_monochrome(color_mode: str, style: str) -> bool:
    """
    Resolve whether a panel should render in monochrome.

    color_mode: "auto" | "color" | "bw" (default "auto").
      - "bw"    → always monochrome
      - "color" → always colour
      - "auto"  → monochrome only for manga (current default behaviour)
    """
    mode = (color_mode or "auto").strip().lower()
    if mode == "bw":
        return True
    if mode == "color":
        return False
    # "auto" (and any unknown value) → preserve legacy behaviour
    return (style or "").strip().lower() == "manga"

# Detailed style templates mapping prefix and lighting_override
STYLE_TEMPLATES = {
    "anime": {
        "prefix": "anime illustration, vibrant colors, clean lineart",
        "lighting_override": "vibrant lighting, colorful shadows"
    },
    "manga": {
        "prefix": "manga illustration, monochrome, greyscale, black and white, ink wash, screentone, manga panel, high contrast ink lines",
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

SDXL_STYLE_TEMPLATES = {
    "manga": {
        "prefix": "masterpiece, best quality, ultra detailed, manga style, monochrome, greyscale, black and white, ink wash, screentone, manga panel, sharp linework, dramatic screentones, dynamic composition",
        "lighting_override": "stark shadows, high-contrast lighting"
    },
    "manhwa": {
        "prefix": "masterpiece, best quality, ultra detailed, manhwa style, Korean webtoon art, full color, soft cel shading, clean precise linework, professional digital art",
        "lighting_override": "soft studio lighting, gentle ambient glow"
    },
    "anime": {
        "prefix": "masterpiece, best quality, ultra detailed, anime style, vibrant colors, expressive eyes, clean cel animation art, professional anime key visual",
        "lighting_override": "vibrant lighting, colorful shadows"
    },
    "cinematic": {
        "prefix": "masterpiece, best quality, ultra detailed, cinematic lighting, graphic novel style, realistic proportions, dramatic shadows, film composition, concept art quality",
        "lighting_override": "dramatic cinematic lighting, volumetric raytracing, chiaroscuro"
    },
    "realistic": {
        "prefix": (
            "RAW photo, photorealistic, professional photography, "
            "realistic lighting, highly detailed skin texture, "
            "natural skin pores, realistic shadows, natural proportions, "
            "depth of field, realistic textures, 8k resolution, "
            "sharp focus, professional color grading"
        ),
        "lighting_override": "natural soft lighting, realistic ambient occlusion, photographic shadows"
    },
}

# V3 Phase 0: Dedicated SDXL Realistic style template for RealVisXL V4.0
# Do NOT reuse anime/manhwa templates for realistic generation.
SDXL_REALISTIC_STYLE_TEMPLATE = {
    "prefix": (
        "RAW photo, photorealistic, professional photography, "
        "realistic lighting, highly detailed skin texture, "
        "natural skin pores, realistic shadows, natural proportions, "
        "depth of field, realistic textures, 8k resolution, "
        "sharp focus, professional color grading"
    ),
    "lighting_override": "natural soft lighting, realistic ambient occlusion, photographic shadows",
    "negative": (
        "cartoon, anime, illustration, painting, drawing, sketch, "
        "unrealistic, fake, plastic skin, doll-like, CGI render, "
        "low quality, blurry, overexposed, bad anatomy"
    )
}


ENVIRONMENT_VISUAL_ANCHORS = {
    "library": "inside a school library background, wooden bookshelves filled with books, study tables, library aisles",
    "dojo": "inside a traditional Japanese martial arts dojo background, tatami mats, wooden walls",
    "classroom": "inside a school classroom background, student desks, blackboard, windows",
    "hallway": "inside a school hallway background, lockers, classroom doors",
    "office": "office background, office desk, computer monitor, chairs",
    "forest": "dense forest background, trees, leaves, natural sunlight, foliage",
    "castle": "castle interior background, stone walls, banners, arches",
    "dungeon": "dungeon background, dark stone walls, chains, dim torchlight",
    "city": "city street background, buildings, paved road, city skyline",
    "street": "outdoor street background, buildings, lamp posts, sidewalk",
    "alley": "dark narrow alleyway background, brick walls, trash cans",
    "rooftop": "rooftop background, city skyline, railings, open sky",
    "temple": "ancient temple background, pillars, stone steps, statues",
    "cave": "dark cavern background, stone walls, stalactites",
    "desert": "sand dunes background, barren landscape, dry desert sand, hot sun",
    "battlefield": "battlefield background, smoke, ruins, debris, cracked ground",
    "arena": "coliseum arena background, stone stands, spectators",
    "village": "village street background, small wooden houses, dirt path",
    "mountain": "mountain peaks background, rocky terrain, snowy cliffs, blue sky",
    "river": "river bank background, flowing water, rocks, trees",
    "bridge": "wooden bridge background, river below, scenery",
    "throne room": "grand throne room background, red carpet, golden throne, banners",
    "ruins": "ancient ruins background, broken stone pillars, overgrown moss, debris",
    "tower": "stone tower interior background, spiral staircase, narrow windows",
    "courtyard": "school courtyard background, stone pavement, benches, trees",
    "market": "outdoor market background, market stalls, food stands",
    "lab": "scientific laboratory background, test tubes, computer screens, futuristic equipment",
    "ship": "ship deck background, wooden planks, ocean waves, sails, masts",
    "school": "school building background, brick walls, windows, hallways",
    "palace": "grand palace background, marble floors, tall columns, chandeliers"
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

    def build_character_identity_block(self, character: dict, memory_manager, label: str = None) -> str:
        """
        V3: Builds a structured Identity Core block with fixed field ordering.
        Fields: label/name, sex+age, hair, eyes, features, outfit, body_type.
        label: Optional CHARACTER_A/CHARACTER_B/CHARACTER_C prefix.
        """
        name = str(character.get("name", "")).strip()
        sheet = None
        if memory_manager and hasattr(memory_manager, "get_design_sheet"):
            sheet = memory_manager.get_design_sheet(name)

        if sheet:
            gender = sheet.gender.lower() if getattr(sheet, "gender", None) else "male"
            age = sheet.age_range.lower() if getattr(sheet, "age_range", None) else "adult"
            style_clean = str(sheet.hair_style).lower().replace("hair", "").strip() if getattr(sheet, "hair_style", None) else ""
            color_clean = str(sheet.hair_color).lower().replace("hair", "").strip() if getattr(sheet, "hair_color", None) else ""
            parts = []
            if style_clean:
                parts.append(style_clean)
            if color_clean:
                parts.append(color_clean)
            hair = f"{' '.join(parts)} hair" if parts else ""
            eye_color = getattr(sheet, "eye_color", "") or ""
            eye_str = f"{eye_color} eyes" if eye_color and "eye" not in eye_color.lower() else eye_color
            outfit = getattr(sheet, "primary_outfit", "") or ""
            features = getattr(sheet, "distinguishing_features", "") or ""
            body_type = getattr(sheet, "body_type", "") or ""
        else:
            profile = None
            if memory_manager and hasattr(memory_manager, "consistency"):
                profile = memory_manager.consistency.get_profile(name)
            if profile:
                gender = profile.get("gender", "male")
                age = "adult"
                style_clean = str(profile.get("hair_style_token", "")).lower().replace("hair", "").strip()
                color_clean = str(profile.get("hair_color_token", "")).lower().replace("hair", "").strip()
                parts = []
                if style_clean:
                    parts.append(style_clean)
                if color_clean:
                    parts.append(color_clean)
                hair = f"{' '.join(parts)} hair" if parts else ""
                eye_str = ""
                outfit = profile.get("outfit_tokens", "")
                features = profile.get("base_description", "")
                body_type = ""
            else:
                desc = str(character.get("description", "")).strip()
                header = f"{label}: {name}" if label else f"Character {name}"
                return f"{header}, {desc}" if desc else header

        header = f"{label}: {name}" if label else f"Character {name}"
        ordered_parts = [
            header,
            f"{gender} {age}",
            hair,
            eye_str,
            features,
            outfit,
            body_type,
        ]
        cleaned = [p.strip() for p in ordered_parts if str(p).strip()]
        return ", ".join(cleaned)

    def build_multi_character_identity_block(self, characters: list, memory_manager) -> str:
        """
        V3: Builds separated identity blocks for 1-3 characters with anti-bleed fencing.
        Characters beyond 3 are collapsed into BACKGROUND_SUPPORTING_CHARACTERS.
        Blocks separated by ' | ' to create clear visual separation in prompts.
        """
        if not characters:
            return ""

        blocks = []
        primary_chars = characters[:3]
        overflow_chars = characters[3:]

        for i, char in enumerate(primary_chars):
            label = CHARACTER_SEPARATOR_LABELS[i]
            block = self.build_character_identity_block(char, memory_manager, label=label)
            blocks.append(block)

        if overflow_chars:
            names = ", ".join([c.get("name", "character") for c in overflow_chars])
            blocks.append(f"{BACKGROUND_LABEL}: {names}, background supporting characters")

        return " | ".join(blocks)

    def _character_token(self, character: dict, is_focus: bool, memory_manager=None) -> str:
        """
        Build a character token using dense Character Identity Block.
        """
        token = self.build_character_identity_block(character, memory_manager)

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

    def get_negative_hair_colors(self, hair_color: str) -> str:
        """
        Generates negative prompt tokens for all other hair colors to prevent drift.
        """
        color = hair_color.lower().replace("hair", "").strip()
        if not color:
            return ""
        all_colors = ["black", "brown", "blonde", "red", "silver", "white", "grey", "gray", "pink", "blue", "green", "purple", "yellow"]
        neg_colors = [c for c in all_colors if c != color]
        if color == "blonde":
            neg_colors = [c for c in neg_colors if c != "blond"]
        elif color == "blond":
            neg_colors = [c for c in neg_colors if c != "blonde"]
        elif color == "grey":
            neg_colors = [c for c in neg_colors if c != "gray"]
        elif color == "gray":
            neg_colors = [c for c in neg_colors if c != "grey"]
            
        return ", ".join([f"{c} hair" for c in neg_colors])

    def build_two_character_tokens(self, char1: dict, char2: dict, memory_manager=None) -> str:
        """
        Builds separated prompt segment for two-character panels to prevent gender blending.
        Injects identity blocks for both characters.
        """
        block1 = self.build_character_identity_block(char1, memory_manager)
        block2 = self.build_character_identity_block(char2, memory_manager)
        
        return f"{block1}, {block2}, 2people, facing each other"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _apply_color_mode(self, prompt: str, monochrome: bool) -> str:
        """
        Normalise a finished positive prompt for the resolved colour mode.
        Monochrome: prepend monochrome anchors (survive the 110-token cap).
        Colour: strip any monochrome/ink-art tokens so a manga-styled prompt
        forced to colour does not keep pulling the model toward greyscale.
        """
        tokens = self._to_tokens(prompt)
        if monochrome:
            existing = {t.lower() for t in tokens}
            prepend = [mt for mt in MONOCHROME_TOKENS if mt not in existing]
            tokens = prepend + tokens
        else:
            tokens = [
                t for t in tokens
                if not any(k in t.lower() for k in MONOCHROME_KEYWORDS)
            ]
        tokens = self._deduplicate_tokens(tokens)
        return ", ".join(tokens[:110])

    def build_prompt(
        self,
        scene: dict,
        memory_manager,
        is_continuation: bool = False,
        style: str = None,
        color_mode: str = "auto",
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
        is_sdxl = getattr(settings, "IMAGE_PROVIDER", "stable_diffusion") == "fal_ai"
        monochrome = resolve_monochrome(color_mode, active_style)

        # Resolve style template
        style_lower = active_style.lower() if active_style else "anime"
        templates_to_use = SDXL_STYLE_TEMPLATES if is_sdxl else STYLE_TEMPLATES

        if style_lower in templates_to_use:
            template = templates_to_use[style_lower]
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
            cam_toks = self._to_tokens(camera_input)
            # Object/environment-only panels: drop person-framing tokens (waist-up,
            # full-body, head-and-shoulders, portrait) that imply a human subject.
            if not scene.get("characters"):
                _person_frame = ("waist-up", "full-body", "full body", "head and shoulders",
                                 "upper body", "portrait", "close-up shot", "headshot")
                cam_toks = [t for t in cam_toks if not any(pf in t.lower() for pf in _person_frame)]
            l1_camera_tokens.extend(cam_toks)

        # ----- Layer 2: Emotion tokens ---------------------------------
        # Emotion describes a person's face/body — only meaningful when a character
        # is in frame. For object/environment-only panels (no characters) skip it,
        # so a sword-on-an-altar or empty-street shot isn't pushed toward a face.
        has_characters = bool(scene.get("characters"))
        emotion_input = scene.get("emotion") or ""
        if has_characters:
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

        # Resolve focus character gender for prepend tag and negative enforcement
        gender_token = ""
        neg_gender = ""
        if focus_name:
            profile = memory_manager.consistency.get_profile(focus_name)
            if not profile:
                for char in characters:
                    cname = char.get("name", "")
                    if cname and (focus_name in cname.lower() or cname.lower() in focus_name):
                        profile = memory_manager.consistency.get_profile(cname)
                        if profile:
                            break
            if not profile:
                sheet = memory_manager.get_design_sheet(focus_name)
                if sheet:
                    gender = getattr(sheet, "gender", None)
                else:
                    gender = None
            else:
                gender = profile.get("gender")

            if gender == "female":
                gender_token = "1girl, female,"
                neg_gender = "1boy, male, masculine"
            elif gender == "male":
                gender_token = "1boy, male,"
                neg_gender = "1girl, female, feminine"

        # V3: Use structured multi-character identity blocks
        if len(characters) == 0:
            pass  # No character tokens
        elif len(characters) == 1:
            char = characters[0]
            cached_desc = memory_manager.get_character(char.get("name", ""))
            if cached_desc:
                char = dict(char)
                char["description"] = cached_desc
            if is_continuation:
                char = dict(char)
                char["_is_continuation"] = True
            token = self.build_character_identity_block(char, memory_manager, label="CHARACTER_A")
            if token:
                l4_character_tokens.extend(self._to_tokens(token))
        else:
            # V3 multi-character: structured blocks with anti-bleed fencing
            enriched_chars = []
            for char in characters:
                c = dict(char)
                cached_desc = memory_manager.get_character(c.get("name", ""))
                if cached_desc:
                    c["description"] = cached_desc
                if is_continuation:
                    c["_is_continuation"] = True
                enriched_chars.append(c)
            multi_block = self.build_multi_character_identity_block(enriched_chars, memory_manager)
            if multi_block:
                l4_character_tokens.extend(self._to_tokens(multi_block))

        # ----- Layer 5: Action & environment (V3 — ActionLibrary + InteractionComposer) ----
        env_input = scene.get("global_environment") or scene.get("environment") or ""
        action_input = scene.get("action") or ""

        def _env_tokens():
            toks = []
            if env_input:
                # Always include the RAW environment description first — it carries the
                # period + mood ("ancient ruined city", "abandoned market", "moonlit
                # rain") that the generic anchors used to OVERWRITE (e.g. "ancient city"
                # became "modern city street"). FLUX follows the raw description well, so
                # the concrete anchors are now only a light supplement appended after it.
                toks.extend(self._to_tokens(env_input))
                env_lower = env_input.lower().strip()
                for k, a in ENVIRONMENT_VISUAL_ANCHORS.items():
                    if k in env_lower:
                        toks.extend(self._to_tokens(a))
            return toks

        def _action_tokens():
            toks = []
            if action_input:
                toks.extend(self._to_tokens(action_input))
                avt = _action_library.get_action_tokens(action_input)
                if avt:
                    toks.extend(avt)
                it = _interaction_composer.detect_and_inject(action_input, len(characters))
                if it:
                    toks.extend(it)
            return toks

        if not has_characters:
            # Object / environment-only panel. FLUX (the default model) ignores the
            # negative prompt, so the "keep people out" constraint must live in the
            # POSITIVE prompt — but diffusion models handle negation poorly: literal
            # "no people" paradoxically summons the token "people". So we use positive
            # desolation adjectives that contain NO person-nouns. Also lead with the
            # action/subject (e.g. the sword) so a hero object isn't drowned out by the
            # heavy environment anchors.
            l5_action_env_tokens.append("completely deserted, abandoned, desolate, silent, empty, still, lifeless, uninhabited")
            l5_action_env_tokens.extend(_action_tokens())
            l5_action_env_tokens.extend(_env_tokens())
        else:
            l5_action_env_tokens.extend(_env_tokens())
            l5_action_env_tokens.extend(_action_tokens())

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
        
        # Build prefix tokens
        prefix_tokens = []
        if gender_token:
            prefix_tokens.extend(self._to_tokens(gender_token))
        if is_sdxl:
            prefix_tokens.extend(self._to_tokens("masterpiece, best quality, ultra detailed, highres"))
            char_count = len(characters)
            if char_count == 1:
                prefix_tokens.extend(self._to_tokens("solo"))
            elif char_count == 2:
                prefix_tokens.extend(self._to_tokens("2people"))

        # Prepend prefix tokens to cand_all, avoiding duplicates
        full_tokens = prefix_tokens + [t for t in cand_all if t.lower() not in [p.lower() for p in prefix_tokens]]
        full_tokens = self._deduplicate_tokens(full_tokens)
        full_tokens = full_tokens[:110]
        candidate_prompt = ", ".join(full_tokens)

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
            
            full_tokens = prefix_tokens + [t for t in cand_all if t.lower() not in [p.lower() for p in prefix_tokens]]
            full_tokens = self._deduplicate_tokens(full_tokens)
            full_tokens = full_tokens[:110]
            candidate_prompt = ", ".join(full_tokens)

        # V3 Continuation Lock: Re-inject Identity Core anchors at prompt start for panels 2+
        if is_continuation and characters:
            identity_anchors = []
            for i, char in enumerate(characters[:3]):
                char_name = char.get("name", "")
                profile = memory_manager.consistency.get_profile(char_name)
                if profile:
                    gender_tok = profile.get("gender_tokens", "")
                    parts = [p.strip() for p in [gender_tok] if p and p.strip()]
                    if parts:
                        identity_anchors.append(", ".join(parts))
            if identity_anchors:
                anchor_str = ", ".join(identity_anchors)
                candidate_prompt = f"{anchor_str}, {candidate_prompt}"
                final_tokens = self._to_tokens(candidate_prompt)
                final_tokens = self._deduplicate_tokens(final_tokens)
                candidate_prompt = ", ".join(final_tokens[:110])

        # Apply resolved colour mode: inject monochrome anchors or strip them
        # so the positive prompt matches auto/color/bw intent.
        candidate_prompt = self._apply_color_mode(candidate_prompt, monochrome)

        # Save final prompt for future comparison
        self.last_positive_prompt = candidate_prompt

        # ----- Negative prompt construction ----------------------------
        if is_sdxl:
            neg_parts = ["worst quality, low quality, normal quality, lowres, bad anatomy, bad hands, error, missing fingers, extra digit, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, artist name, bad proportions, gross proportions, text, error, extra limbs, missing arms, missing legs, fused fingers, too many fingers, long neck, mutation, mutated, ugly, disgusting, poorly drawn face, extra fingers, missing fingers, poorly drawn hands, missing limb, floating limbs, disconnected limbs, malformed hands, out of focus, long body, disgusting, extra legs, clone face, gross, out of frame"]
        else:
            neg_parts = [getattr(settings, "PROMPT_NEGATIVE", "")]

        # Colour-mode negatives: push away from the unwanted look. In monochrome
        # suppress colour; in colour mode (incl. manga forced to colour) suppress
        # greyscale so the model doesn't fall back to ink/screentone.
        if monochrome:
            neg_parts.append(COLOUR_NEGATIVE)
        elif style_lower == "manga":
            neg_parts.append(MONOCHROME_NEGATIVE)

        pos_lower = candidate_prompt.lower()
        has_female_ref = any(w in pos_lower for w in ["1girl", "female", "she", "her", "mei", "woman", "girl"])
        has_male_ref = any(w in pos_lower for w in ["1boy", "male", "he", "him", "his", "kaito", "man", "boy"])

        if neg_gender:
            if "1girl" in neg_gender and has_female_ref:
                pass
            elif "1boy" in neg_gender and has_male_ref:
                pass
            else:
                neg_parts.append(neg_gender)

        # Add negative hair colors for focus/characters (scoped per-scene, not global)
        if is_sdxl:
            active_hair_colors = set()
            for char in characters:
                char_name = char.get("name", "")
                if char_name:
                    profile = memory_manager.consistency.get_profile(char_name)
                    if profile and profile.get("hair_color_token"):
                        color_token = profile["hair_color_token"].lower().replace("hair", "").strip()
                        if color_token:
                            active_hair_colors.add(color_token)
                desc = char.get("description", "").lower()
                for c in ["black", "brown", "blonde", "blond", "red", "silver", "white", "grey", "gray", "pink", "blue", "green", "purple", "yellow"]:
                    if c in desc:
                        active_hair_colors.add(c)
            
            # Prevent contradictory hair color negations if characters are mentioned in positive prompt
            if "kaito" in pos_lower:
                active_hair_colors.add("black")
            if "mei" in pos_lower:
                active_hair_colors.add("brown")

            all_colors = ["black", "brown", "blonde", "red", "silver", "white", "grey", "gray", "pink", "blue", "green", "purple", "yellow"]
            neg_colors = []
            for c in all_colors:
                is_active = False
                for ac in active_hair_colors:
                    if c == ac:
                        is_active = True
                    elif c == "blonde" and ac == "blond":
                        is_active = True
                    elif c == "blond" and ac == "blonde":
                        is_active = True
                    elif c == "grey" and ac == "gray":
                        is_active = True
                    elif c == "gray" and ac == "grey":
                        is_active = True
                if not is_active:
                    neg_colors.append(c)
            if neg_colors:
                neg_parts.append(", ".join([f"{c} hair" for c in neg_colors]))

        # Add crowd suppression for multi-character panels
        if len(characters) > 1:
            neg_parts.append("extra person, third character, background crowd, extra characters, duplicate characters")
        elif len(characters) == 0:
            # Object / environment-only panel (a sword on an altar, an empty street):
            # the extraction found no characters, so actively keep people out of frame
            # instead of letting the model default to inserting a person.
            neg_parts.append("person, people, human, man, woman, crowd, figure, portrait, face, character")

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
