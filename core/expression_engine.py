"""
expression_engine.py
Stage 2 — Component 2A
Expression Engine mapping emotions to specific Stable Diffusion prompt sub-tokens.
"""

class ExpressionEngine:
    # 10 mapped emotions: angry, sad, shocked, determined, happy, fearful, crying, embarrassed, confident, neutral
    EMOTIONS = {
        "angry": {
            "eyes": "narrowed eyes, intense glare",
            "brows": "furrowed brows, angry eyebrows",
            "mouth": "frowning mouth, gritted teeth",
            "body": "tense posture, clenched fists",
        },
        "sad": {
            "eyes": "visibly downcast teary eyes, glistening with tears",
            "brows": "clearly raised inner brows, unmistakably sorrowful",
            "mouth": "visibly trembling lips, downturned mouth quivering",
            "body": "noticeably slumped shoulders, collapsed posture",
        },
        "shocked": {
            "eyes": "wide eyes, dilated pupils, wide-eyed stare",
            "brows": "raised eyebrows, high arched brows",
            "mouth": "gasping mouth, slightly open mouth, agape",
            "body": "rigid posture, recoiling slightly",
        },
        "determined": {
            "eyes": "focused gaze, sharp eyes",
            "brows": "firmly set eyebrows, knit brows",
            "mouth": "firm straight lips, set jaw",
            "body": "confident posture, standing tall",
        },
        "happy": {
            "eyes": "smiling eyes, crinkled eyes, bright eyes",
            "brows": "relaxed eyebrows",
            "mouth": "wide smile, grinning mouth, showing teeth",
            "body": "relaxed posture, open gestures",
        },
        "fearful": {
            "eyes": "visibly wide trembling eyes, clearly frightened pupils",
            "brows": "obviously raised panicked brows, fear lines visible",
            "mouth": "clearly frozen open expression, silent terror",
            "body": "noticeably hunched cowering, arms drawn in tightly",
        },
        "crying": {
            "eyes": "streaming tears clearly visible, squinted crying eyes",
            "brows": "anguished raised brows, obvious pain expression",
            "mouth": "openly sobbing mouth, chin clearly trembling",
            "body": "visibly collapsed inward, hunched over in grief",
        },
        "embarrassed": {
            "eyes": "clearly averted sideways glance, obviously looking away",
            "brows": "visibly lowered shy brows, flustered expression",
            "mouth": "clearly bitten lip, visible blush on cheeks",
            "body": "noticeably turned away, arms crossed shyly",
        },
        "confident": {
            "eyes": "smirking eyes, direct eye contact, sharp gaze",
            "brows": "slightly raised eyebrow, relaxed brows",
            "mouth": "smirk, confident smile, smirk on face",
            "body": "proud stance, hands on hips, strong posture",
        },
        "neutral": {
            "eyes": "calm eyes, steady gaze",
            "brows": "neutral eyebrows",
            "mouth": "closed mouth, neutral lips",
            "body": "relaxed natural posture",
        },
        "determination": {
            "eyes": "piercing focused gaze, sharp unwavering eyes",
            "brows": "firmly knit brows, set brow ridge",
            "mouth": "jaw set, lips pressed tight, clenched teeth",
            "head": "chin lowered slightly, head tilted forward",
            "body": "leaning forward posture, fists at sides, taut shoulders",
        },
        "rage": {
            "eyes": "blazing furious eyes, bulging veins near eyes, intense glare",
            "brows": "deeply furrowed angry brows, rage lines",
            "mouth": "bared teeth, screaming open mouth, rage expression",
            "head": "head pushed slightly forward aggressively",
            "body": "aggressive forward posture, rigid tense muscles, clenched fists raised",
        },
        "despair": {
            "eyes": "hollow vacant eyes, dark under-eyes, empty stare",
            "brows": "collapsed inner brows, heavy brow droop",
            "mouth": "quivering open mouth, barely moving lips",
            "head": "head hanging low, chin to chest",
            "body": "completely hunched inward, weight bearing down, collapsed posture",
        },
        "shock_intense": {
            "eyes": "wildly blown wide eyes, fully visible sclera, pupils contracted",
            "brows": "shot up maximally raised brows, forehead lines deep",
            "mouth": "jaw dropped fully open, speechless frozen expression",
            "head": "head jerked back in shock, recoiling motion",
            "body": "frozen rigid body, arms thrown out, staggered stance",
        },
        "relief": {
            "eyes": "eyes softly closing then reopening, relaxed gaze, slight moisture",
            "brows": "smooth relaxed brows, tension released",
            "mouth": "exhaling open lips, quiet soft smile forming, subtle breath visible",
            "head": "head tilted back slightly in release",
            "body": "shoulders dropping, body loosening, subtle forward slump of relief",
        },
        "suspicion": {
            "eyes": "narrowed sideways glance, one eye slightly more squinted, watchful gaze",
            "brows": "one raised eyebrow, asymmetric brow expression",
            "mouth": "tight closed lips, slight smirk at corner",
            "head": "head turned slightly away, angled look",
            "body": "body turned partially away, arms crossed, weight shifted back",
        },
        "confusion": {
            "eyes": "tilted head eyes, furrowed uncertain glance, blinking look",
            "brows": "one raised and one lowered brow, asymmetric confused brows",
            "mouth": "slightly open mouth, visible small frown",
            "head": "head tilted sideways, questioning angle",
            "body": "hands raised slightly in a questioning gesture, weight shifted to one side",
        },
        "grief": {
            "eyes": "red rimmed streaming tears, squinted grief-stricken eyes, swollen eyelids",
            "brows": "raised inner brows, deep pain lines on forehead",
            "mouth": "wailing open mouth, chin clearly trembling, sobbing expression",
            "head": "head bowed, chin to chest, turned slightly inward",
            "body": "bent double over grief, head buried in hands, trembling shoulders",
        },
        "romantic_affection": {
            "eyes": "soft warm half-lidded gaze, loving eyes, gentle sparkle",
            "brows": "gently raised inner brows, soft tender expression",
            "mouth": "soft warm smile, gently parted lips, blushing cheeks",
            "head": "head leaning in slightly, intimate closeness",
            "body": "leaning toward the other person, open relaxed body language, hands reaching",
        },
        "embarrassment_enhanced": {
            "eyes": "tightly averted eyes, clearly looking anywhere but forward, visible tears of embarrassment",
            "brows": "furrowed shy brows, flustered deep blush lines",
            "mouth": "biting lower lip hard, jaw dropped in mortification",
            "head": "face buried in hands or turned completely away",
            "body": "arms wrapped tightly around self, whole body turned away, crouching slightly",
        },
    }

    SDXL_EMOTIONS = {
        "angry": "angry, furrowed brow, scowl, teeth clenched",
        "sad": "sad, teary eyes, downcast eyes, trembling lip, teary eyes, glossy eyes, sad smile, downturned mouth, melancholy expression, emotional, heartbroken",
        "shocked": "wide eyes, parted lips, pale face, shaking, disbelief expression, stunned",
        "happy": "smile, happy, bright eyes, cheerful",
        "determined": "cold eyes, piercing gaze, serious expression, tense jaw, unflinching stare",
        "fearful": "scared, fearful, wide eyes, cowering",
        "crying": "crying, tears, sobbing, red eyes",
        "embarrassed": "embarrassed, blush, flushed face",
        "confident": "confident, smirk, smile",
        "neutral": "neutral expression, calm look",
        "determination": "cold eyes, piercing unwavering gaze, jaw set, taut shoulders, leaning forward determined",
        "rage": "blazing furious eyes, bared teeth, screaming rage expression, clenched fists, veins visible, aggressive stance",
        "despair": "hollow empty eyes, dark circles, head hanging low, completely collapsed posture, quivering lips",
        "shock_intense": "eyes wide open sclera fully visible, jaw dropped, frozen shocked expression, staggered recoiling",
        "relief": "exhaling expression, shoulders dropping, soft relieved smile, eyes softly closing",
        "suspicion": "narrowed sideways glance, one raised eyebrow, tight lips, arms crossed, body angled away",
        "confusion": "head tilted sideways, one raised brow, slightly open mouth, questioning hands raised",
        "grief": "streaming tears, swollen red eyes, wailing expression, bent over in grief, trembling",
        "romantic_affection": "soft loving half-lidded gaze, warm blush, gentle smile, leaning in, tender body language",
        "embarrassment_enhanced": "deep blush, face buried in hands, whole body turned away, mortified expression",
    }

    def __init__(self, provider: str = None):
        from config import settings
        self.provider = provider or getattr(settings, "IMAGE_PROVIDER", "stable_diffusion")

    def _resolve_emotion_synonym(self, emotion: str) -> str:
        if not emotion:
            return "neutral"
        
        emotion = emotion.strip().lower()
        if emotion in self.EMOTIONS:
            return emotion
            
        # --- V3 precise mappings (checked FIRST to prevent broad-match interception) ---
        if any(term in emotion for term in ["rage", "infuriat", "fuming", "seething", "livid", "wrathful"]):
            return "rage"
        elif any(term in emotion for term in ["grief", "anguish", "mourn", "bereav", "wail", "lament"]):
            return "grief"
        elif any(term in emotion for term in ["despair", "hopeless", "devastat", "heartbroken", "crushed"]):
            return "despair"
        elif any(term in emotion for term in ["stunned", "speechless", "astound", "dumbfound", "disbelief"]):
            return "shock_intense"
        elif any(term in emotion for term in ["smitten", "lovestruck", "romantic", "affection", "longing", "adore", "lov", "tender", "yearn"]):
            return "romantic_affection"
        elif any(term in emotion for term in ["mortif", "humiliat", "ashamed"]):
            return "embarrassment_enhanced"
        elif any(term in emotion for term in ["relief", "reliev", "exhale"]):
            return "relief"
        elif any(term in emotion for term in ["suspic", "distrust", "wary", "skeptic"]):
            return "suspicion"
        elif any(term in emotion for term in ["confus", "puzzl", "perplex", "bewild", "baffl"]):
            return "confusion"
        elif any(term in emotion for term in ["determinat", "steely", "unwaver"]):
            return "determination"
        # Dramatic *tension* / *intensity* (standoffs, action beats) is wariness and
        # focus, NOT personal terror. Resolve these to "determined" (serious,
        # unflinching, on-guard) BEFORE the legacy fear broad-match below — note
        # "intense" contains the substring "tense", so it must be caught here or it
        # would wrongly fall through to "fearful" (scared, cowering). [QA 2026-06-28]
        elif any(term in emotion for term in ["tense", "tension", "intense", "wary",
                                              "guarded", "alert", "on edge", "on-edge",
                                              "standoff", "menac", "vigilant", "suspens",
                                              "serious", "grim", "stoic", "dramatic",
                                              "cold", "resolv", "resolute"]):
            return "determined"
        elif any(term in emotion for term in ["cautio", "hesitan", "uneasy", "uncertain",
                                              "doubt", "reluctan"]):
            return "suspicion"
        # Action/peril stress words used to fall through to "neutral" (a calm face on a
        # desperate escape). Map them to intense/determined (focused under pressure) so a
        # hero sprinting from an explosion doesn't look serene — and without the
        # "cowering" of the fearful bucket. [QA 2026-06-29]
        elif any(term in emotion for term in ["urgen", "desperat", "frantic", "hurried",
                                              "rushed", "panic-strick", "adrenaline"]):
            return "determined"
        elif any(term in emotion for term in ["triumph", "victorious", "elated", "exultant"]):
            return "confident"
        elif any(term in emotion for term in ["exhaust", "weary", "drained", "spent",
                                              "fatigue", "worn out"]):
            return "despair"
        elif any(term in emotion for term in ["threat", "hostile", "aggressi",
                                              "snarl", "vicious"]):
            return "angry"

        # --- Legacy broad-match synonyms (original 10 emotions) ---
        elif any(term in emotion for term in ["melancholy", "sadness", "sorrow", "depressed", "downcast", "gloomy"]):
            return "sad"
        elif any(term in emotion for term in ["surprise", "shock", "startl", "astonish", "stun"]):
            return "shocked"
        elif any(term in emotion for term in ["worr", "anxi", "nerv", "scar", "afraid", "fear", "fright", "panic", "cower", "terror", "dread", "horror"]):
            return "fearful"
        elif any(term in emotion for term in ["cry", "sob", "weep", "tear"]):
            return "crying"
        elif any(term in emotion for term in ["shy", "embarrass", "fluster", "blush", "awkward", "sheepish", "bashful"]):
            return "embarrassed"
        elif any(term in emotion for term in ["intense", "resolut", "focus", "determin", "stern"]):
            return "determined"
        elif any(term in emotion for term in ["happ", "cheer", "smil", "joy", "excit", "curio", "laugh", "giggl", "chuckl", "amus", "grin", "delight", "playful", "glee"]):
            return "happy"
        elif any(term in emotion for term in ["angr", "furi", "annoy", "irat", "glar"]):
            return "angry"
        elif any(term in emotion for term in ["confid", "smug", "smirk", "proud", "bold"]):
            return "confident"
        elif any(term in emotion for term in ["stunned", "speechless", "astound", "dumbfound", "disbelief"]):
            return "shock_intense"
        elif any(term in emotion for term in ["relief", "reliev", "exhale"]):
            return "relief"
        elif any(term in emotion for term in ["suspic", "distrust", "wary", "skeptic", "doubt"]):
            return "suspicion"
        elif any(term in emotion for term in ["confus", "puzzl", "perplex", "bewild", "baffl"]):
            return "confusion"
        elif any(term in emotion for term in ["grief", "anguish", "mourn", "bereav", "wail", "lament"]):
            return "grief"
        elif any(term in emotion for term in ["smitten", "lovestruck", "romantic", "affection", "tender", "longing", "adore"]):
            return "romantic_affection"
        elif any(term in emotion for term in ["mortif", "humiliat", "ashamed"]):
            return "embarrassment_enhanced"
        return "neutral"

    def get_expression_tokens(self, emotion: str) -> dict:
        """
        Get the exact sub-tokens for eyes, brows, mouth, and body for the given emotion.
        Falls back to 'neutral' silently if the emotion is unknown or empty,
        but first attempts to resolve common synonyms/fuzzy terms.
        """
        resolved = self._resolve_emotion_synonym(emotion)
        return self.EMOTIONS[resolved].copy()

    def build_emotion_prompt_segment(self, emotion: str) -> str:
        """
        Build an optimized comma-separated segment representing the emotion prompt tokens.
        Falls back to 'neutral' silently.
        """
        if self.provider == "fal_ai":
            resolved = self._resolve_emotion_synonym(emotion)
            return self.SDXL_EMOTIONS.get(resolved, self.SDXL_EMOTIONS["neutral"])

        tokens = self.get_expression_tokens(emotion)
        parts = [
            tokens.get("eyes", ""),
            tokens.get("brows", ""),
            tokens.get("mouth", ""),
            tokens.get("head", ""),
            tokens.get("body", "")
        ]
        return ", ".join(p for p in parts if p)
