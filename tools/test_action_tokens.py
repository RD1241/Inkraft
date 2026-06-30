"""Regression test for action/interaction token matching (free, no fal spend).

Guards against the substring false-positive class fixed 2026-06-30, e.g. "cast"
matching "the moonlight CASTing shadows" -> spurious "magic circle, arcane energy"
on a plain chase scene. Run:  venv/Scripts/python tools/test_action_tokens.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.action_library import ActionLibrary
from core.interaction_composer import InteractionComposer

lib = ActionLibrary()
comp = InteractionComposer()

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")


def has_magic(tokens):
    return any("magic" in t or "arcane" in t for t in tokens)


print("== Action library: MUST NOT false-match (substring bug) ==")
check(not has_magic(lib.get_action_tokens("the moonlight casting long shadows behind him")),
      "'casting shadows' must NOT inject magic")
check(lib.get_action_tokens("the white wall stood tall") == [],
      "'white' must NOT match 'hit'")
check(not has_magic(lib.get_action_tokens("a forecast of doom")),
      "'forecast' must NOT inject magic")
check(lib.get_action_tokens("they reached the castle gate") == [],
      "'castle' must NOT match 'cast'")

print("== Action library: MUST still match the real action verb ==")
check(has_magic(lib.get_action_tokens("Kael casts a fireball")),
      "'casts' SHOULD inject magic")
check(has_magic(lib.get_action_tokens("they cast a spell together")),
      "'cast' (standalone) SHOULD inject magic")
check(lib.get_action_tokens("their swords clash violently") != [],
      "'swords clash' SHOULD inject combat tokens")
check(lib.get_action_tokens("the knight charges forward") != [],
      "'charges forward' SHOULD inject charge tokens")

print("== Interaction composer: MUST NOT false-match ==")
check(comp.detect_and_inject("a gang of thugs approached", char_count=2) == [],
      "'thugs' must NOT match 'hugs'")
print("== Interaction composer: MUST still match ==")
check(comp.detect_and_inject("he hugs her tightly", char_count=2) != [],
      "'hugs' SHOULD inject embrace tokens")

print()
if failures:
    print(f"*** {len(failures)} REGRESSION(S) ***")
    sys.exit(1)
print("ALL ACTION/INTERACTION TOKEN CHECKS PASSED")
