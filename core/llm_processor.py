import json
import re
import time
import httpx
import ollama
from config import settings
from core.scene_interpreter import classify_scene, compute_panel_count
from providers.llm.chat_client import get_chat_client, using_groq

# Module-level chat client — Ollama locally, or Groq cloud when LLM_PROVIDER=groq.
# Both expose the same .chat(model, messages, options) -> {"message": {"content": ...}} shape.
_ollama_client = get_chat_client()


_ollama_offline_cache = None

def _wait_for_ollama(timeout: int = 30) -> bool:
    """
    Poll the Ollama HTTP endpoint until it responds or timeout expires.
    Returns True if ready, False if timed out.
    When using a remote provider (Groq), there is no local server to wait for.
    """
    if using_groq():
        return True

    global _ollama_offline_cache
    if _ollama_offline_cache is not None:
        return _ollama_offline_cache

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{settings.OLLAMA_HOST}/api/tags", timeout=2)
            if r.status_code == 200:
                _ollama_offline_cache = True
                return True
        except Exception:
            pass
        time.sleep(1)
    _ollama_offline_cache = False
    return False


class LLMProcessor:
    """
    Extracts scenes from novel text via local Ollama LLM.

    The LLM is ONLY asked to extract facts (environment, characters, action,
    emotion, dialogue). It does NOT decide shot types, panel roles, or
    cinematic structure — those are user / interpreter concerns.
    """

    ENVIRONMENT_KEYWORDS = (
        "cafe", "coffee shop", "restaurant", "kitchen", "bedroom", "living room",
        "office", "park", "garden", "library", "classroom", "train station",
        "forest", "castle", "dungeon", "city", "street", "alley", "rooftop",
        "temple", "cave", "desert", "battlefield", "arena", "village",
        "mountain", "river", "bridge", "throne room", "ruins", "tower",
        "courtyard", "market", "lab", "ship", "school", "palace",
        "industrial district", "facility", "walkway", "steel beam",
    )

    @staticmethod
    def detect_character_gender(character_name: str, story_text: str) -> str:
        """
        Detects gender of a character based on name lists or pronouns in story_text.
        High-confidence check against common gendered names is performed first.
        If name list is inconclusive, checks an 8-word window around character name.
        If the character name appears 0 times, falls back to full-text pronoun counting.
        """
        if not story_text:
            story_text = ""
        if not character_name:
            return "male"

        story_text_lower = story_text.lower()
        char_name_lower = character_name.lower()

        # Comprehensive lists of common female/male names to bypass noisy pronoun proximity
        common_female_names = {
            "mei", "sakura", "hinata", "rin", "miku", "asuka", "rei", "yuki", "haruka", 
            "aoi", "yui", "kaguya", "chika", "mikasa", "historia", "annie", "sasha",
            "elena", "lyra", "sara", "luna", "aria", "maya", "zara", "nova", "iris", 
            "vera", "mia", "sofia", "anna", "emma", "lily", "rose", "violet", "aurora", 
            "diana", "alice", "claire", "grace", "jade", "kate", "laura", "nina", 
            "olivia", "ruby", "stella", "lucy", "erza", "juvia", "mirajane", "wendy", 
            "mabel", "mary", "elizabeth", "sarah", "jennifer", "linda", "patricia", 
            "susan", "jessica", "karen", "nancy", "lisa", "betty", "margaret", "sandra"
        }
        
        common_male_names = {
            "kaito", "hiro", "kenji", "takashi", "yuto", "ren", "haruto", "sota",
            "john", "robert", "michael", "william", "david", "richard", "joseph",
            "thomas", "charles", "christopher", "daniel", "matthew", "anthony",
            "mark", "donald", "steven", "paul", "andrew", "joshua", "kenneth",
            "kevin", "brian", "george", "edward", "ronald", "timothy", "jason"
        }

        name_words = set(char_name_lower.split())
        
        # 1. High-confidence name list check takes absolute precedence
        if name_words.intersection(common_female_names):
            gender = "female"
            source = "name_list"
            print(f"[CharacterDetection] {character_name}: method = name_list")
            print(f"[CharacterDetection] {character_name}: detected gender = {gender} (source: {source})")
            return gender
        elif name_words.intersection(common_male_names):
            gender = "male"
            source = "name_list"
            print(f"[CharacterDetection] {character_name}: method = name_list")
            print(f"[CharacterDetection] {character_name}: detected gender = {gender} (source: {source})")
            return gender

        female_pronouns = {"she", "her", "herself", "hers"}
        male_pronouns = {"he", "him", "himself", "his"}

        # Tokenize story text into words
        words = re.findall(r"\b\w+\b", story_text_lower)
        char_tokens = re.findall(r"\b\w+\b", char_name_lower)

        female_count = 0
        male_count = 0
        method_used = "default"

        # Count occurrences of the character name in story_text
        name_occurrences = 0
        if char_tokens:
            first_token = char_tokens[0]
            for idx, word in enumerate(words):
                if word == first_token:
                    match_ok = True
                    for offset, token in enumerate(char_tokens):
                        if idx + offset >= len(words) or words[idx + offset] != token:
                            match_ok = False
                            break
                    if match_ok:
                        name_occurrences += 1

        if name_occurrences > 0 and char_tokens:
            # We use proximity window
            method_used = "proximity_window"
            first_token = char_tokens[0]
            for idx, word in enumerate(words):
                if word == first_token:
                    match_ok = True
                    for offset, token in enumerate(char_tokens):
                        if idx + offset >= len(words) or words[idx + offset] != token:
                            match_ok = False
                            break
                    if match_ok:
                        # 8-word window before and after the matched name index
                        start = max(0, idx - 8)
                        end = min(len(words), idx + len(char_tokens) + 8)
                        window_words = words[start:end]
                        for w in window_words:
                            if w in female_pronouns:
                                female_count += 1
                            elif w in male_pronouns:
                                male_count += 1
        else:
            # Name appears 0 times or name is empty - fall back to full-text pronoun count
            method_used = "full_text_fallback"
            for w in words:
                if w in female_pronouns:
                    female_count += 1
                elif w in male_pronouns:
                    male_count += 1

        # Determine gender based on counts
        if female_count > male_count:
            gender = "female"
            source = "pronouns"
        elif male_count > female_count:
            gender = "male"
            source = "pronouns"
        else:
            gender = "male"
            source = "default"

        # Log according to user instructions:
        # [CharacterDetection] {name}: method = proximity_window | full_text_fallback
        # [CharacterDetection] {name}: detected gender = {gender} (source: pronouns|name_list|default)
        print(f"[CharacterDetection] {character_name}: method = {method_used}")
        print(f"[CharacterDetection] {character_name}: detected gender = {gender} (source: {source})")
        return gender

    def __init__(self, model_name=None):
        self.model_name = model_name or settings.LLM_MODEL
        self.system_prompt = """You are a comic storyboard extractor. Read the novel text and output ONLY valid JSON. No markdown, no explanation.

Extract scenes into this exact structure:
{"global_environment": "<where overall story happens, max 8 words>", "scenes": [{"scene_id": 1, "environment": "<location>", "focus_character": "<main char name>", "characters": [{"name": "<name>", "character_role": "main_character|secondary_character|enemy_character", "description": "<max 10 words, include male/female>"}], "action": "<what physically happens>", "emotion": "<mood>", "dialogue": [{"speaker": "<name or Narrator>", "type": "speech|narration", "text": "<words>"}]}]}

Rules:
- Use as many scenes as the text has beats (do not force exactly 4).
- Keep descriptions under 10 words. Include gender: male/female.
- Guards/soldiers = secondary_character. Enemies/monsters = enemy_character. Hero = main_character.
- ALL scenes MUST be inside the single top-level "scenes" array. Never split scenes into multiple arrays or objects.
- Output ONLY the single JSON object. Nothing before or after it. No trailing commas."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _repair_json(self, text: str) -> str:
        """
        Fix llama3's most common malformed output: it sometimes splits the
        scenes array into multiple separate arrays separated by commas:

            "scenes": [{obj1}], [{obj2}]   ← BROKEN (two arrays)

        This repairs it to:

            "scenes": [{obj1}, {obj2}]     ← VALID (one array)

        The regex targets the exact boundary pattern: `}], [{`
        (end of a JSON object, close bracket, comma, open bracket, new object)
        and replaces it with `}, {` which simply continues the same array.
        """
        repaired = re.sub(r'\}\]\s*,\s*\[', '}, ', text)
        return repaired

    def _shorten(self, text: str, max_words: int = 8) -> str:
        words = re.findall(r"[A-Za-z0-9'-]+", str(text or ""))
        return " ".join(words[:max_words]).lower()

    def _extract_json(self, text: str) -> dict | None:
        """
        Extract a valid storyboard JSON object from LLM output.

        Handles two failure modes common with smaller Ollama models:

        1. Normal case — single well-formed JSON object somewhere in the text.

        2. Split-array bug — the LLM outputs the first scene inside the main
           object and the remaining scenes as a dangling array, e.g.:
               {"global_environment": "...", "scenes": [{scene_1}]},
               [{scene_2}, {scene_3}]
           We detect the trailing '[ ... ]' that follows the first object and
           splice those extra scenes back in before parsing.
        """
        search_from = 0

        while True:
            # ── Step 1: find the start of the next '{' candidate ──────────
            start = text.find('{', search_from)
            if start == -1:
                return None

            # ── Step 2: bracket-depth scan to find matching '}' ───────────
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
                return None  # unmatched brace — no hope

            candidate = text[start:end + 1]

            # ── Step 3: try to fix the split-array bug before parsing ─────
            #
            # Pattern:  <candidate>  ,  [ {scene}, {scene} ... ]
            # The bit after the closing '}' may look like:  , [{...}, ...]
            # We scan for it and, if found, merge into the candidate.
            candidate_fixed = self._try_merge_split_scenes(candidate, text[end + 1:])

            # ── Step 4: parse — prefer merged version, fall back to raw ──
            for blob in (candidate_fixed, candidate):
                if blob is None:
                    continue
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    pass

            # Neither worked; skip past this '{' and keep searching
            search_from = start + 1

    # ------------------------------------------------------------------

    def _try_merge_split_scenes(self, first_obj: str, remainder: str) -> str | None:
        """
        Detect the split-array LLM bug and repair it.

        The LLM sometimes emits:
            {"global_environment":"...","scenes":[{scene1}]},\n[{scene2},{scene3}]

        We look for a '[' in *remainder* (skipping whitespace / commas)
        and, if found, extract all scene objects from that array and inject
        them into the "scenes" list of *first_obj* before parsing.

        Returns the repaired JSON string, or None if the pattern isn't found.
        """
        # Skip whitespace and commas immediately after the closing '}'
        stripped = remainder.lstrip(', \t\r\n')
        if not stripped.startswith('['):
            return None  # no dangling array — nothing to do

        # Find the matching ']' for this array
        depth = 0
        in_string = False
        escape = False
        arr_end = -1
        for i, ch in enumerate(stripped):
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
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    arr_end = i
                    break

        if arr_end == -1:
            return None  # array is truncated — can't recover

        extra_array_str = stripped[:arr_end + 1]
        try:
            extra_scenes = json.loads(extra_array_str)
        except json.JSONDecodeError:
            return None  # dangling array itself is malformed

        if not isinstance(extra_scenes, list):
            return None

        # Parse the first object and splice in the extra scenes
        try:
            obj = json.loads(first_obj)
        except json.JSONDecodeError:
            return None

        existing = obj.get("scenes", [])
        if not isinstance(existing, list):
            existing = []
        obj["scenes"] = existing + extra_scenes

        print(f"[LLM] Split-array bug detected and repaired: merged {len(extra_scenes)} extra scene(s).")
        return json.dumps(obj)

    def _extract_global_environment(self, text: str, parsed: dict) -> str:
        for scene in parsed.get("scenes", []):
            env = str(scene.get("environment", "")).strip()
            if env and env.lower() not in ("none", "unknown", ""):
                return env
        text_lower = text.lower()
        for keyword in self.ENVIRONMENT_KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", text_lower):
                return keyword
        return "cinematic scene"

    def _apply_gender_bias_fix(self, character: dict) -> dict:
        """
        Reduce model female-bias by explicitly tagging gender in description.
        """
        desc = str(character.get("description", "")).lower()
        desc_words = set(re.findall(r"\b\w+\b", desc))
        if "female" in desc_words or "woman" in desc_words or "girl" in desc_words:
            character["_gender_tag"] = "female character"
            character["_negative_gender"] = ""
        elif "male" in desc_words or "man" in desc_words or "boy" in desc_words:
            character["_gender_tag"] = "male character, masculine features"
            character["_negative_gender"] = "feminine face, female anatomy"
        return character

    def _normalize_characters(self, scene: dict, source_text: str = ""):
        """Clean up character list, enrich generic descriptions, and apply gender bias fix."""
        blacklist = {
            "he", "she", "it", "they", "them", "him", "her", "his", "hers", "their", "theirs",
            "someone", "everyone", "nobody", "noone", "anybody", "somebody", "character",
            "people", "man", "woman", "boy", "girl", "knight", "commander", "enemy", "the",
            "and", "but", "then", "this", "when", "after", "for", "with", "a", "an", "of"
        }
        
        # 1. Recover characters mentioned in action, dialogue, or focus_character that are missing
        existing_names = {str(c.get("name", "")).strip().lower() for c in scene.get("characters", []) or []}
        
        # Extract character names from story text (2+ occurrences)
        cap_words = re.findall(r'\b([A-Z][a-z]{2,})\b', source_text)
        from collections import Counter
        word_counts = Counter(cap_words)
        all_story_chars = [
            w for w in dict.fromkeys(cap_words)
            if w.lower() not in blacklist and word_counts[w] >= 2
        ]
        
        # Ensure focus character is present in characters list
        focus_char = str(scene.get("focus_character", "")).strip()
        if focus_char and focus_char.lower() not in blacklist:
            if focus_char.lower() not in existing_names:
                gender = self.detect_character_gender(focus_char, source_text)
                scene.setdefault("characters", []).append({
                    "name": focus_char,
                    "character_role": "main_character",
                    "description": f"{focus_char.lower()} character, {gender}"
                })
                existing_names.add(focus_char.lower())
                
        # Ensure dialogue speakers are present in characters list
        for dlg in scene.get("dialogue", []) or []:
            speaker = str(dlg.get("speaker", "")).strip()
            if speaker and speaker.lower() not in ("narrator", "none", "") and speaker.lower() not in blacklist:
                if speaker.lower() not in existing_names:
                    gender = self.detect_character_gender(speaker, source_text)
                    scene.setdefault("characters", []).append({
                        "name": speaker,
                        "character_role": "secondary_character",
                        "description": f"{speaker.lower()} character, {gender}"
                    })
                    existing_names.add(speaker.lower())
                    
        # Ensure characters mentioned in scene action are present in characters list
        action_text = str(scene.get("action", "")).lower()
        for char_name in all_story_chars:
            if char_name.lower() in action_text:
                if char_name.lower() not in existing_names:
                    gender = self.detect_character_gender(char_name, source_text)
                    scene.setdefault("characters", []).append({
                        "name": char_name,
                        "character_role": "secondary_character",
                        "description": f"{char_name.lower()} character, {gender}"
                    })
                    existing_names.add(char_name.lower())

        fallback_appearances = [
            # Character 1: main character
            {
                "female": "female, short black hair, school uniform",
                "male": "male, short black hair, school uniform"
            },
            # Character 2: secondary character
            {
                "female": "female, long brown hair, ponytail, casual outfit",
                "male": "male, messy brown hair, casual outfit"
            },
            # Character 3: third character
            {
                "female": "female, blonde hair, twin tails, red sweater",
                "male": "male, spiky blonde hair, jacket"
            }
        ]

        seen = set()
        normalized = []
        for j, char in enumerate(scene.get("characters", []) or []):
            char = dict(char)
            name = str(char.get("name", "")).strip()
            key = name.lower()
            if key in blacklist or key in seen:
                continue
            seen.add(key)
            
            # Enrich description if generic or lacks visual detail
            desc = str(char.get("description", "")).strip()
            desc_lower = desc.lower()
            is_generic = False
            if not desc_lower or desc_lower in ("character", key, f"{key} character", "unknown"):
                is_generic = True
            elif not any(w in desc_lower for w in ("hair", "eye", "wear", "outfit", "uniform", "shirt", "pant", "jacket", "suit", "dress", "cloth", "skirt", "robe", "cloak")):
                is_generic = True
                
            if is_generic:
                gender = self.detect_character_gender(name, source_text)
                app_idx = min(j, len(fallback_appearances) - 1)
                visual_desc = fallback_appearances[app_idx].get(gender, f"{gender} character")
                char["description"] = f"{key} character, {visual_desc}"
                
            char = self._apply_gender_bias_fix(char)
            normalized.append(char)
        scene["characters"] = normalized

    def _normalize_storyboard(self, parsed: dict, source_text: str, panel_count: int = None, layout_type: str = None) -> dict:
        """
        Lightweight post-processing:
        - Lock the global environment
        - Clean characters
        - Trim or pad scene count to what the user / layout / narrative demands
        """
        scenes = parsed.get("scenes") or []

        # Determine how many panels we actually need
        if panel_count is not None:
            target_count = min(max(panel_count, 2), 10)
        elif layout_type is not None:
            layout_lower = layout_type.lower()
            if "action" in layout_lower:
                target_count = 4
            elif "drama" in layout_lower:
                target_count = 3
            elif "dialog" in layout_lower or "talk" in layout_lower:
                target_count = 2
            else:
                target_count = compute_panel_count(source_text, scenes)
        else:
            target_count = compute_panel_count(source_text, scenes)

        # Enforce exact scene count
        if len(scenes) > target_count:
            scenes = scenes[:target_count]
        elif len(scenes) < target_count:
            while len(scenes) < target_count:
                new_scene = dict(scenes[-1]) if scenes else {
                    "scene_id": len(scenes) + 1,
                    "environment": "cinematic scene",
                    "focus_character": "",
                    "characters": [],
                    "action": "The scene continues.",
                    "emotion": "calm",
                    "dialogue": []
                }
                if scenes:
                    new_scene["scene_id"] = len(scenes) + 1
                scenes.append(new_scene)

        parsed["scenes"] = scenes

        # Lock environment across all panels from first scene
        global_env = self._extract_global_environment(source_text, parsed)
        global_env = self._shorten(global_env, 8)
        parsed["global_environment"] = global_env

        for index, scene in enumerate(scenes, start=1):
            scene["scene_id"] = index
            # Lock environment to prevent drift
            scene["environment"] = global_env
            scene["global_environment"] = global_env
            # Clean characters
            self._normalize_characters(scene, source_text=source_text)
            # Inject flags from scene interpreter
            flags = classify_scene(
                str(scene.get("action", "")) + " " + source_text
            )
            scene["is_action"] = flags["is_action"]
            scene["is_dialogue"] = flags["is_dialogue"]
            scene["is_calm"] = flags["is_calm"]

        return parsed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _rule_based_extraction(self, text: str, panel_count: int = None, layout_type: str = None) -> dict:
        """
        Rule-based scene extraction fallback used when Ollama is unreachable.
        Splits text into sentence groups, builds structured scene dicts using
        classify_scene(), and runs full _normalize_storyboard().
        """
        print("[LLM] Using rule-based extraction fallback (Ollama offline).")

        # Split on sentence boundaries, group into beats
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]

        # Determine target panel count
        if panel_count is not None:
            target = min(max(panel_count, 2), 10)
        elif layout_type == "action":
            target = 4
        elif layout_type == "drama":
            target = 3
        elif layout_type in ("dialogue", "dialog"):
            target = 2
        else:
            target = min(max(len(sentences), 2), 5)

        # Group sentences into scene chunks
        chunk_size = max(1, len(sentences) // target)
        chunks = []
        for i in range(target):
            start = i * chunk_size
            end = start + chunk_size if i < target - 1 else len(sentences)
            chunk_text = " ".join(sentences[start:end])
            chunks.append(chunk_text)
        if not chunks:
            chunks = [text]

        # Extract rough character names using capitalized words heuristic.
        # FIX: require a candidate to appear 2+ times in the text so that
        # sentence-starting words like "Across", "Meanwhile", "After"
        # (which appear exactly once) are never accepted as character names.
        cap_words = re.findall(r'\b([A-Z][a-z]{2,})\b', text)
        blacklist = {
            # pronouns / generic references
            "he", "she", "it", "they", "them", "him", "her", "his", "hers", "their", "theirs",
            "someone", "everyone", "nobody", "noone", "anybody", "somebody", "character",
            "people", "man", "woman", "boy", "girl", "knight", "commander", "enemy",
            # common conjunctions / prepositions / articles
            "the", "and", "but", "then", "this", "when", "after", "for", "with", "a", "an", "of",
            # common sentence-starting adverbs / prepositions that get capitalised
            "across", "above", "before", "below", "behind", "beside", "between",
            "beyond", "during", "inside", "outside", "around", "against",
            "meanwhile", "suddenly", "finally", "already", "later", "now",
            "slowly", "quickly", "quietly", "together", "however", "though",
            "although", "while", "until", "unless", "despite", "without",
        }
        # Count occurrences of each candidate in the full text.
        # Only accept names that appear 2+ times — real character names recur;
        # one-off sentence-start words do not.
        from collections import Counter
        word_counts = Counter(cap_words)
        char_names = list(dict.fromkeys(
            w for w in cap_words
            if w.lower() not in blacklist and word_counts[w] >= 2
        ))[:3]
        # If frequency filter eliminates everything, fall back to single-occurrence
        # words (still blacklist-filtered) so we always get at least one name.
        if not char_names:
            char_names = list(dict.fromkeys(
                w for w in cap_words if w.lower() not in blacklist
            ))[:3]
        if not char_names:
            char_names = ["Character"]

        # Build the characters list with generic-but-distinct visual descriptions
        characters = []
        fallback_appearances = [
            # Character 1: main character
            {
                "female": "female, short black hair, school uniform",
                "male": "male, short black hair, school uniform"
            },
            # Character 2: secondary character
            {
                "female": "female, long brown hair, ponytail, casual outfit",
                "male": "male, messy brown hair, casual outfit"
            },
            # Character 3: third character
            {
                "female": "female, blonde hair, twin tails, red sweater",
                "male": "male, spiky blonde hair, jacket"
            }
        ]

        for j, name in enumerate(char_names):
            role = "main_character" if j == 0 else "secondary_character"
            gender = self.detect_character_gender(name, text)
            
            # Retrieve generic-but-distinct visual appearance based on index & detected gender
            app_idx = min(j, len(fallback_appearances) - 1)
            visual_desc = fallback_appearances[app_idx].get(gender, f"{gender} character")
            
            characters.append({
                "name": name,
                "character_role": role,
                "description": f"{name.lower()} character, {visual_desc}"
            })

        # Detect environment
        global_env = self._extract_global_environment(text, {"scenes": []})

        # Extract dialogue lines from text: match double quotes, single quotes, or colon-based speech
        dialogue_raw = re.findall(r'"([^"]{3,200})"', text)
        if not dialogue_raw:
            # Try single quotes
            dialogue_raw = re.findall(r"'([^']{3,200})'", text)
        if not dialogue_raw:
            # Try matching text after "said:", "said quietly:", "says:", "replied:", "asked:" etc.
            speech_matches = re.findall(r'(?:said|says|replied|asked|screamed|whispered|spoke|told)(?:\s+\w+){0,3}\s*:\s*([A-Z][^.!?]+)', text)
            if speech_matches:
                dialogue_raw = [m.strip() for m in speech_matches]

        # Build scene list
        scenes = []
        for i, chunk in enumerate(chunks):
            flags = classify_scene(chunk)
            # Pick dialogue for this scene if available
            dlg_list = []
            if dialogue_raw:
                dlg_text = dialogue_raw[i % len(dialogue_raw)]
                dlg_list = [{
                    "speaker": char_names[0] if char_names else "Character",
                    "type": "speech",
                    "text": dlg_text
                }]
            else:
                dlg_list = LLMProcessor.extract_narrative_dialogue(chunk, char_names[0] if char_names else "Character")

            emotion = "determined" if flags["is_action"] else ("sad" if "cry" in chunk.lower() else "neutral")
            scenes.append({
                "scene_id": i + 1,
                "environment": global_env,
                "global_environment": global_env,
                "focus_character": char_names[0] if char_names else "Character",
                "characters": characters,
                "action": chunk[:120],
                "emotion": emotion,
                "dialogue": dlg_list,
                "is_action": flags["is_action"],
                "is_dialogue": flags["is_dialogue"],
                "is_calm": flags["is_calm"],
            })

        parsed = {
            "global_environment": global_env,
            "scenes": scenes
        }
        return self._normalize_storyboard(parsed, text, panel_count=panel_count, layout_type=layout_type)

    @staticmethod
    def extract_narrative_dialogue(text: str, focus_character: str) -> list[dict]:
        dialogue_list = []
        text_lower = text.lower()
        
        # 1. Check for "asks why"
        match = re.search(r"(\b\w+\b)\s+asks\s+why", text, re.IGNORECASE)
        if match:
            speaker = match.group(1)
            if speaker.lower() in ["she", "he", "it", "they"]:
                speaker = focus_character or "Character"
            dialogue_list.append({
                "speaker": speaker,
                "type": "speech",
                "text": "Why did you do this?"
            })
            
        # 2. Check for "apologizes" or "apologize"
        match = re.search(r"(\b\w+\b)\s+apologizes?", text, re.IGNORECASE)
        if match:
            speaker = match.group(1)
            if speaker.lower() in ["she", "he", "it", "they"]:
                speaker = focus_character or "Character"
            dialogue_list.append({
                "speaker": speaker,
                "type": "speech",
                "text": "I'm sorry."
            })
            
        # 3. Check for "accuse/accuses each other of betrayal" or "accuse/accuses ... of betrayal"
        if "betrayal" in text_lower or "betray" in text_lower:
            match_each = re.search(r"accuse(?:s)?\s+each\s+other", text_lower)
            if match_each:
                dialogue_list.append({
                    "speaker": focus_character or "Character",
                    "type": "speech",
                    "text": "You betrayed the kingdom!"
                })
            else:
                match_accuse = re.search(r"(\b\w+\b)\s+accuse(?:s)?\s+(\b\w+\b)", text, re.IGNORECASE)
                if match_accuse:
                     speaker = match_accuse.group(1)
                     target = match_accuse.group(2)
                     if speaker.lower() in ["she", "he", "it", "they"]:
                         speaker = focus_character or "Character"
                     dialogue_list.append({
                         "speaker": speaker,
                         "type": "speech",
                         "text": f"You betrayed the kingdom, {target}!"
                     })
        return dialogue_list

    def process_text(self, text: str, panel_count: int = None, layout_type: str = None) -> dict:
        # Wait for Ollama to be reachable before first attempt
        if not _wait_for_ollama(timeout=30):
            print("[LLM] Ollama not reachable after 30s — using rule-based fallback.")
            return self._rule_based_extraction(text, panel_count=panel_count, layout_type=layout_type)

        for attempt in range(3):
            content = None
            try:
                response = _ollama_client.chat(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user",   "content": text},
                    ],
                    options={
                        "temperature": 0.3,
                        "num_ctx":     6144,   # llama3 supports 8192; 6144 gives ~5k tokens for output
                        "num_predict": 3000,   # cap runaway generation
                        "keep_alive":  settings.LLM_KEEP_ALIVE,
                    },
                )
                content = response["message"]["content"]

                # Strip markdown fences
                clean = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()

                # Repair llama3's broken split-array output BEFORE parsing
                clean = self._repair_json(clean)

                # Use bracket-depth extraction — immune to trailing text after '}'
                parsed = self._extract_json(clean)
                if parsed and parsed.get("scenes"):
                    parsed = self._normalize_storyboard(parsed, text, panel_count=panel_count, layout_type=layout_type)
                    return parsed

                print(f"[LLM] Invalid JSON or empty scenes on attempt {attempt + 1}. Raw output snippet:\n{clean[:500]}")

            except Exception as exc:
                print(f"[LLM] Error on attempt {attempt + 1}: {exc}")
                if attempt == 2:
                    print(f"[LLM] Raw output: {content}")
                import time
                time.sleep(2)

        # All 3 Ollama attempts failed — use rule-based fallback instead of returning empty
        print("[LLM] All 3 Ollama attempts failed — using rule-based fallback.")
        return self._rule_based_extraction(text, panel_count=panel_count, layout_type=layout_type)

