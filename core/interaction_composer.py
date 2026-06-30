"""
interaction_composer.py
Stage 3 — Phase 4 (Interaction Composer V1)
Detects and injects physical interaction prompt tokens for multi-character comic panels.
Prevents vague physical contact descriptions by mapping narrative contact to
precise SD/SDXL positional tokens. Only activates for scenes with 2+ characters.
"""

import re

INTERACTION_TEMPLATES = {
    "holding_hands": {
        "keywords": [
            "holding hands", "holds hands", "held hands", "hand in hand",
            "hold hands", "hand holding",
            "interlock fingers", "interlocked fingers", "fingers intertwined",
            "fingers interlock", "fingers interlocked",
        ],
        "tokens": [
            "interlocked fingers", "visible hand contact", "close body distance",
            "soft eye contact between characters",
        ],
        "min_chars": 2,
    },
    "hugging": {
        "keywords": ["hugging", "hugs", "embrace", "embracing", "embraces",
                     "arms around", "wrapped in arms", "pulls into hug"],
        "tokens": ["full body embrace", "arms around body", "faces close together",
                   "emotional body language"],
        "min_chars": 2,
    },
    "sword_clash": {
        "keywords": ["sword clash", "clash swords", "swords clash", "blades clash",
                     "blades meet", "weapons cross", "cross swords"],
        "tokens": ["weapons crossed at contact point", "visible impact sparks",
                   "forceful opposing stances", "dynamic combat tension"],
        "min_chars": 2,
    },
    "handshake": {
        "keywords": ["handshake", "shakes hands", "shake hands", "shaking hands",
                     "extend hand", "extends hand"],
        "tokens": ["joined hands between characters", "extended arms", "professional eye contact"],
        "min_chars": 2,
    },
    "shoulder_grab": {
        "keywords": ["grabs shoulder", "grabbed shoulder", "gripping shoulder",
                     "hand on shoulder", "places hand on shoulder"],
        "tokens": ["hand gripping shoulder", "clear physical contact", "arm placement clearly visible"],
        "min_chars": 2,
    },
    "punch": {
        "keywords": ["punch", "punches", "punching", "strikes with fist",
                     "delivers blow", "hits face", "lands punch"],
        "tokens": ["fist making contact", "impact blur", "receiver reacting to impact", "striking pose"],
        "min_chars": 2,
    },
    "standing_together": {
        "keywords": ["standing together", "stand side by side", "stand beside",
                     "stands next to", "side by side", "together overlooking"],
        "tokens": ["two characters side by side", "parallel body language", "shared gaze direction"],
        "min_chars": 2,
    },
    "confrontation": {
        "keywords": ["confront", "confronting", "confronts", "face to face",
                     "faces each other", "squares off", "stares down", "staredown"],
        "tokens": ["facing each other closely", "charged tense atmosphere",
                   "tense opposing body language", "eye contact locked"],
        "min_chars": 2,
    },
    "protecting": {
        "keywords": ["protects", "protecting", "shields", "shielding",
                     "stands in front of", "blocks for", "guards"],
        "tokens": ["one character shielding another", "arms spread protectively",
                   "body positioned in front"],
        "min_chars": 2,
    },
    "cheek_touch": {
        "keywords": ["touches cheek", "touch cheek", "caresses face", "cups face",
                     "hand on face", "holds face", "strokes cheek"],
        "tokens": ["hand touching face", "gentle close proximity", "tender intimate expression"],
        "min_chars": 2,
    },
    "carrying": {
        "keywords": ["carries", "carrying", "lifts up", "picks up", "held in arms",
                     "bridal carry", "piggyback"],
        "tokens": ["one character carrying another", "arms supporting body weight",
                   "dynamic physical lift"],
        "min_chars": 2,
    },
}


class InteractionComposer:
    """
    V1 Interaction Composer: detects physical interactions between characters
    and injects precise spatial/positional prompt tokens.

    Only activates when char_count >= 2. Single-character scenes return [].

    Usage:
        composer = InteractionComposer()
        tokens = composer.detect_and_inject(action_text, char_count=2)
    """

    def __init__(self):
        self._keyword_map: dict = {}
        self._min_char_map: dict = {}
        for name, data in INTERACTION_TEMPLATES.items():
            for kw in data["keywords"]:
                self._keyword_map[kw.lower()] = data["tokens"]
                self._min_char_map[kw.lower()] = data.get("min_chars", 2)
        # Precompile WORD-BOUNDARY patterns, longest keyword first. Word-boundary
        # matching (not raw substring) prevents false positives like "hugs" matching
        # "thugs" or "embrace" matching unrelated words — same fix as ActionLibrary.
        # [QA 2026-06-30]
        self._compiled = [
            (kw, re.compile(r"\b" + re.escape(kw) + r"\b"),
             self._keyword_map[kw], self._min_char_map.get(kw, 2))
            for kw in sorted(self._keyword_map.keys(), key=len, reverse=True)
        ]

    def detect_and_inject(self, action_text: str, char_count: int = 1) -> list:
        """
        Detects physical interaction keywords in action_text.
        Returns matching token list, or [] if:
        - No keywords match
        - char_count < 2
        - action_text is empty
        """
        if not action_text or char_count < 2:
            return []
        lower = action_text.lower()
        for kw, pattern, tokens, min_chars in self._compiled:
            if pattern.search(lower) and char_count >= min_chars:
                return list(tokens)
        return []

    def detect_all_interactions(self, action_text: str, char_count: int = 1) -> list:
        """
        Returns tokens for ALL matching interactions (deduped).
        For complex scenes with overlapping physical actions.
        """
        if not action_text or char_count < 2:
            return []
        lower = action_text.lower()
        seen = set()
        result = []
        for kw, pattern, tokens, min_chars in self._compiled:
            if pattern.search(lower) and char_count >= min_chars:
                for tok in tokens:
                    if tok.lower() not in seen:
                        seen.add(tok.lower())
                        result.append(tok)
        return result
