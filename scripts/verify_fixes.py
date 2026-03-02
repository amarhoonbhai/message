import asyncio
import random
import re
from datetime import datetime, timedelta

def parse_spintax(text: str) -> str:
    """Parse spintax like {Hi|Hello|Hey} into a random choice."""
    def replace(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    # Simple recursive spintax support
    while '{' in text and '|' in text and '}' in text:
        new_text = re.sub(r'\{([^{}]*)\}', replace, text)
        if new_text == text: break
        text = new_text
    return text

def test_spintax():
    test_str = "{Hi|Hello} {there|friend}, how are {you|things}?"
    print(f"Original: {test_str}")
    for _ in range(3):
        print(f"Result: {parse_spintax(test_str)}")

def test_rotation_logic():
    groups = [{"chat_id": 1}, {"chat_id": 2}, {"chat_id": 3}]
    messages = [type('Msg', (), {'id': 101})(), type('Msg', (), {'id': 102})()]
    
    # Stable sorting
    groups.sort(key=lambda x: x.get('chat_id', 0))
    messages.sort(key=lambda x: x.id)
    
    pairs = []
    for j in range(len(groups)):
        for i in range(len(messages)):
            grp_idx = (j + i) % len(groups)
            pairs.append((messages[i], groups[grp_idx]))
    
    print("\nRotation Pairs (Stable):")
    for msg, grp in pairs:
        print(f"Msg {msg.id} -> Group {grp['chat_id']}")

    # Shuffle with seed
    seed = "test_user_20260302"
    random.Random(seed).shuffle(pairs)
    print("\nShuffled Pairs (Deterministic with Seed):")
    for msg, grp in pairs:
        print(f"Msg {msg.id} -> Group {grp['chat_id']}")

if __name__ == "__main__":
    test_spintax()
    test_rotation_logic()
