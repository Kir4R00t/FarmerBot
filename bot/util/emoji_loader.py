"""Load the shared item-to-Discord-emoji mapping."""

import json
from pathlib import Path


def load_item_emojis() -> dict[str, str]:
    path = Path(__file__).with_name("item_emojis.json")
    with path.open(encoding="utf-8") as file:
        emojis = json.load(file)
    if not isinstance(emojis, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in emojis.items()
    ):
        raise ValueError(f"{path.name} must contain an object mapping names to strings")
    return emojis
