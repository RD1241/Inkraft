"""
action_library.py
Stage 3 — Phase 2 (Action Library V2)
Structured visual action token mappings for comic panel image generation.
Maps narrative action keywords to precise SD/SDXL prompt tokens.
"""

ACTION_LIBRARY = {
    "sword_clash": {
        "keywords": ["sword clash", "clash sword", "swords clash", "blades clash", "clash blade", "sword fight", "sword combat"],
        "tokens": ["crossed swords", "impact point visible", "metal sparks", "motion blur", "dynamic combat stance", "dramatic foreshortening"]
    },
    "running": {
        "keywords": ["running", "sprinting", "dashing", "fled", "fleeing", "chase", "chasing", "races"],
        "tokens": ["forward momentum", "windswept clothing", "speed lines", "dynamic action pose", "foot push-off"]
    },
    "magic_attack": {
        "keywords": ["magic attack", "cast spell", "casting spell", "fire spell", "magic blast", "energy blast", "magical attack", "lightning spell"],
        "tokens": ["energy burst", "glowing particles", "light bloom", "shockwave rings", "dramatic upward lighting"]
    },
    "jump": {
        "keywords": ["jump", "leaping", "leaps", "jumped", "vaulting", "vault", "airborne", "mid-air"],
        "tokens": ["mid-air action pose", "foreshortening", "camera tilt", "dramatic upward angle", "motion lines"]
    },
    "attack": {
        "keywords": ["attack", "attacking", "strike", "striking", "lunge", "lunges", "assail", "assaults"],
        "tokens": ["aggressive striking pose", "weapon raised", "power stance"]
    },
    "defend": {
        "keywords": ["defend", "defending", "block", "blocking", "parry", "parrying", "deflect", "shield raised", "guards", "guarding"],
        "tokens": ["defensive stance", "arms raised", "shield raised", "bracing posture"]
    },
    "charge": {
        "keywords": ["charge", "charging", "charges forward", "charges at", "rushes forward", "rushing"],
        "tokens": ["low angle shot", "full sprint", "dust kick-up", "battle cry"]
    },
    "fall": {
        "keywords": ["fall", "falling", "falls", "fell", "collapse", "collapses", "collapsed", "stumbles", "topples"],
        "tokens": ["falling backwards", "motion blur", "high-angle view"]
    },
    "cast_spell": {
        "keywords": ["cast", "casts", "conjure", "conjures", "summon", "summons", "incantation", "magical circle"],
        "tokens": ["hands outstretched", "magic circle", "arcane energy"]
    },
    "draw_weapon": {
        "keywords": ["draw weapon", "draws weapon", "drawing sword", "draws sword", "unsheathe", "unsheathes", "pulls out blade", "reaches for hilt"],
        "tokens": ["reaching for hilt", "metallic glint", "dramatic anticipation"]
    },
    "duel": {
        "keywords": ["duel", "dueling", "duels", "face off", "facing off", "standoff", "stand-off"],
        "tokens": ["fighters facing each other", "weapons crossed", "dramatic tension"]
    },
    "punch_kick": {
        "keywords": ["punch", "punches", "kick", "kicks", "hit", "hits", "slam", "slams", "smash", "smashes", "brawl"],
        "tokens": ["impact strike pose", "contact point visible", "motion blur"]
    },
    "embrace": {
        "keywords": ["embrace", "embracing", "embraces", "hug", "hugs", "hugging", "holds tightly", "holding tight"],
        "tokens": ["arms around body", "full body contact", "warm lighting"]
    },
    "slash": {
        "keywords": ["slash", "slashes", "slashing", "swipes", "swiping", "cuts through", "cleave"],
        "tokens": ["sword slashing motion", "glowing blade trail", "speed lines", "dynamic sweeping pose"]
    },
    "explosion": {
        "keywords": ["explode", "explosion", "blast", "blasts", "detonates", "erupts"],
        "tokens": ["fire explosion", "debris flying", "smoke billowing", "shockwave"]
    },
}


class ActionLibrary:
    """
    V2 Action Library: maps narrative action text to visual SD/SDXL prompt tokens.

    Usage:
        library = ActionLibrary()
        tokens = library.get_action_tokens(action_text)
        # Returns list of token strings, or empty list if no match.

    IMPORTANT: Returns [] when no keyword matches (dialogue/romance scenes stay natural).
    """

    def __init__(self):
        self._keyword_map: dict = {}
        for action_name, data in ACTION_LIBRARY.items():
            for kw in data["keywords"]:
                self._keyword_map[kw.lower()] = data["tokens"]

    def get_action_tokens(self, action_text: str) -> list:
        """
        Scans action_text for known action keywords (longest-first to prevent partial matches).
        Returns the matching visual token list for the FIRST keyword found.
        Returns [] if no match (DO NOT inject generic fallback tokens).
        """
        if not action_text:
            return []
        lower = action_text.lower()
        sorted_kws = sorted(self._keyword_map.keys(), key=len, reverse=True)
        for kw in sorted_kws:
            if kw in lower:
                return list(self._keyword_map[kw])
        return []

    def get_all_matches(self, action_text: str) -> list:
        """
        Returns tokens for ALL matching keywords (deduped).
        For complex scenes with multiple simultaneous actions.
        """
        if not action_text:
            return []
        lower = action_text.lower()
        seen = set()
        result = []
        sorted_kws = sorted(self._keyword_map.keys(), key=len, reverse=True)
        for kw in sorted_kws:
            if kw in lower:
                for tok in self._keyword_map[kw]:
                    if tok.lower() not in seen:
                        seen.add(tok.lower())
                        result.append(tok)
        return result
