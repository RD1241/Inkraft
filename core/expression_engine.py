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
    }

    def get_expression_tokens(self, emotion: str) -> dict:
        """
        Get the exact sub-tokens for eyes, brows, mouth, and body for the given emotion.
        Falls back to 'neutral' silently if the emotion is unknown or empty,
        but first attempts to resolve common synonyms/fuzzy terms.
        """
        if not emotion:
            emotion = "neutral"
        
        emotion = emotion.strip().lower()
        if emotion not in self.EMOTIONS:
            # Synonyms and fuzzy matches mapping
            if any(term in emotion for term in ["melancholy", "sadness", "sorrow", "grief", "depressed", "downcast", "gloomy"]):
                emotion = "sad"
            elif any(term in emotion for term in ["surprise", "shock", "startl", "astonish", "stun"]):
                emotion = "shocked"
            elif any(term in emotion for term in ["tension", "tense", "worr", "anxi", "nerv", "scar", "fear", "fright", "panic", "cower", "terror"]):
                emotion = "fearful"
            elif any(term in emotion for term in ["cry", "sob", "weep", "tear"]):
                emotion = "crying"
            elif any(term in emotion for term in ["shy", "embarrass", "fluster", "blush"]):
                emotion = "embarrassed"
            elif any(term in emotion for term in ["intense", "resolut", "focus", "determin", "stern"]):
                emotion = "determined"
            elif any(term in emotion for term in ["happ", "cheer", "smil", "joy", "excit", "curio"]):
                emotion = "happy"
            elif any(term in emotion for term in ["angr", "furi", "rage", "annoy", "irat", "glar"]):
                emotion = "angry"
            elif any(term in emotion for term in ["confid", "smug", "smirk", "proud", "bold"]):
                emotion = "confident"
            elif any(term in emotion for term in ["calm", "relax", "peace"]):
                emotion = "neutral"
            else:
                emotion = "neutral"
            
        return self.EMOTIONS[emotion].copy()

    def build_emotion_prompt_segment(self, emotion: str) -> str:
        """
        Build an optimized comma-separated segment representing the emotion prompt tokens.
        Falls back to 'neutral' silently.
        """
        tokens = self.get_expression_tokens(emotion)
        parts = [
            tokens.get("eyes", ""),
            tokens.get("brows", ""),
            tokens.get("mouth", ""),
            tokens.get("body", "")
        ]
        return ", ".join(p for p in parts if p)
