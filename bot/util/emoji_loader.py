"""Load the shared item-to-Discord-emoji mapping."""

import json
from pathlib import Path
import re
from typing import Mapping


DEFAULT_ITEM_EMOJI = "📦"

# PoE2Scout CurrencyCategories, checked 2026-10-19. The full /Items catalogue
# also contains uniques and categories outside the exchange (e.g. waystones).
# "idols" is the legacy command's spelling of the current "idol" category.
CURRENCY_EMOJI_CATEGORIES = frozenset({
    "currency", "fragments", "runes", "essences", "ultimatum", "expedition",
    "ritual", "vaultkeys", "breach", "abyss", "uncutgems", "lineagesupportgems",
    "delirium", "incursion", "idol", "idols", "verisium", "vaal",
})


def item_emoji_keys(api_id: str = "", name: str = "") -> tuple[str, str]:
    """Use full API IDs first, then a normalized display-name fallback."""
    return api_id.strip(), re.sub(r"[^a-z0-9]+", "-", name.strip().casefold()).strip("-")


def resolve_item_emoji(emojis: Mapping[str, str], api_id: str = "", name: str = "") -> str:
    for key in item_emoji_keys(api_id, name):
        if key and emojis.get(key):
            return emojis[key]
    return emojis.get("default-item") or DEFAULT_ITEM_EMOJI


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
