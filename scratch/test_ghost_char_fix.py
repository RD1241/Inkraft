"""Quick unit test for the ghost character fix."""
import sys, re
sys.path.insert(0, '.')
from collections import Counter

story = (
    "Kaito sat alone in the school library, the only sound the soft hum of the ceiling lights. "
    "He stared at the letter in his hands, reading it for the third time. "
    "Across the room, the door creaked open and Mei stepped in, her bag slung over one shoulder. "
    "She froze when she saw his expression. "
    "'What happened?' she asked, walking closer. Kaito did not look up. "
    "'They are closing the dojo. After twenty years, it is just over.' "
    "He crumpled the letter and pressed it against his chest. "
    "Mei sat down beside him, saying nothing, just staying close as the silence settled between them."
)

cap_words = re.findall(r'\b([A-Z][a-z]{2,})\b', story)
print("All capitalized words found:", cap_words)

blacklist = {
    "he", "she", "it", "they", "them", "him", "her", "his", "hers", "their", "theirs",
    "someone", "everyone", "nobody", "noone", "anybody", "somebody", "character",
    "people", "man", "woman", "boy", "girl", "knight", "commander", "enemy",
    "the", "and", "but", "then", "this", "when", "after", "for", "with", "a", "an", "of",
    "across", "above", "before", "below", "behind", "beside", "between",
    "beyond", "during", "inside", "outside", "around", "against",
    "meanwhile", "suddenly", "finally", "already", "later", "now",
    "slowly", "quickly", "quietly", "together", "however", "though",
    "although", "while", "until", "unless", "despite", "without",
}

word_counts = Counter(cap_words)
print("\nCounts:", dict(word_counts))

char_names_freq = list(dict.fromkeys(
    w for w in cap_words
    if w.lower() not in blacklist and word_counts[w] >= 2
))[:3]

print("\nAfter frequency>=2 filter:", char_names_freq)
expected = {"Kaito", "Mei"}
actual = set(char_names_freq)
print("Expected:", sorted(expected))
print("Got:     ", sorted(actual))
print()
if actual == expected:
    print("PASS: Exactly Kaito and Mei extracted, no ghost character")
else:
    print("FAIL: Got unexpected characters:", actual - expected, "  Missing:", expected - actual)
