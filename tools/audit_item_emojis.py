"""Audit emoji coverage and upload capacity for NPC currency-exchange items."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.util.emoji_loader import CURRENCY_EMOJI_CATEGORIES, item_emoji_keys


# Verified against Discord's application-owned emoji documentation on 2026-10-19.
# Server emoji quotas are separate and must not be inferred from this limit.
APPLICATION_EMOJI_LIMIT = 2000
EMOJI_LIMIT_SOURCE = 'https://docs.discord.com/developers/resources/emoji#application-owned-emoji'


def emoji_capacity(emojis, missing, application_emoji_count=None):
    """Plan application uploads without mistaking local references for inventory."""
    if application_emoji_count is not None and (
        type(application_emoji_count) is not int or application_emoji_count < 0
    ):
        raise ValueError('Application emoji count must be a nonnegative integer')
    custom_ids = {
        match.group(1)
        for value in emojis.values()
        if (match := re.fullmatch(r'<a?:[^:<>]+:([0-9]+)>', value))
    }
    # One new upload per unmapped key is conservative: shared artwork can reuse
    # a slot. Include keys lacking an icon URL so they are not silently omitted.
    planned_uploads = len({item['key'] for item in missing})
    projected = (
        application_emoji_count + planned_uploads
        if application_emoji_count is not None else None
    )
    status = 'unverified'
    if projected is not None:
        if projected > APPLICATION_EMOJI_LIMIT:
            status = 'would_exceed_limit'
        elif projected == APPLICATION_EMOJI_LIMIT:
            status = 'at_limit'
        else:
            status = 'within_limit'
    return {
        'scope': 'application',
        'limit': APPLICATION_EMOJI_LIMIT,
        'limit_source': EMOJI_LIMIT_SOURCE,
        'limit_verified_on': '2026-10-19',
        'mapped_custom_emoji_ids': len(custom_ids),
        'planned_new_uploads_upper_bound': planned_uploads,
        'distinct_missing_icon_urls': len({item['icon_url'] for item in missing if item['icon_url']}),
        'missing_keys_without_icon_url': len({item['key'] for item in missing if not item['icon_url']}),
        'mapping_only_projection_upper_bound': len(custom_ids) + planned_uploads,
        'current_application_emoji_count': application_emoji_count,
        'current_count_source': 'user_supplied' if application_emoji_count is not None else None,
        'remaining_slots': (
            APPLICATION_EMOJI_LIMIT - application_emoji_count
            if application_emoji_count is not None else None
        ),
        'projected_application_emoji_count_upper_bound': projected,
        'status': status,
    }


def audit_items(items, emojis):
    """Audit only exchange currencies; ignore uniques and catalogue separators."""
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValueError('Expected the /Items endpoint to return a list of objects')
    missing = {}
    for item in items:
        name = item.get('Name') or item.get('Text') or ''
        api_id = item.get('ApiId') or ''
        if not isinstance(name, str) or not isinstance(api_id, str):
            raise ValueError('Item Name/Text and ApiId must be strings or null')
        api_id, slug = item_emoji_keys(api_id, name)
        if not (api_id or slug):
            raise ValueError('Item has no usable API ID or name')
        category = item.get('CategoryApiId') or 'unknown'
        if not api_id or api_id == 'sep' or category not in CURRENCY_EMOJI_CATEGORIES:
            continue
        if any(key and emojis.get(key) for key in (api_id, slug)):
            continue
        key = api_id or slug
        missing[(category, key)] = {
            'key': key, 'name': name, 'api_id': api_id or None,
            'category': category, 'icon_url': item.get('IconUrl'),
        }
    return sorted(missing.values(), key=lambda row: (row['category'], row['key']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--league', help='Exact league name, e.g. "Runes of Aldur"')
    source.add_argument('--input', type=Path, help='Saved JSON response from /Items')
    parser.add_argument('--mapping', type=Path, default=ROOT / 'bot/util/item_emojis.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'emoji_audit/reports/missing-item-emojis.json')
    parser.add_argument(
        '--application-emoji-count', type=int,
        help='Current total uploaded in this application, including unused emojis; read it from the Developer Portal',
    )
    args = parser.parse_args(argv)
    try:
        if args.input:
            items = json.loads(args.input.read_text(encoding='utf-8'))
            source_name = str(args.input)
        else:
            source_name = ('https://api.poe2scout.com/poe2/Leagues/'
                           + quote(args.league, safe='') + '/Items')
            request = Request(source_name, headers={
                'User-Agent': 'FarmerBot emoji coverage audit',
                'Accept': 'application/json',
            })
            with urlopen(request, timeout=30) as response:
                items = json.load(response)
        emojis = json.loads(args.mapping.read_text(encoding='utf-8'))
        if not isinstance(emojis, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in emojis.items()
        ):
            raise ValueError('Emoji mapping must map names to strings')
        missing = audit_items(items, emojis)
        capacity = emoji_capacity(emojis, missing, args.application_emoji_count)
        eligible_count = sum(
            bool((item.get('ApiId') or '').strip())
            and (item.get('ApiId') or '').strip() != 'sep'
            and item.get('CategoryApiId') in CURRENCY_EMOJI_CATEGORIES
            for item in items
        )
        report = {'source': source_name, 'league': args.league,
                  'scope': 'currency_exchange', 'items_checked': len(items),
                  'currency_items_checked': eligible_count,
                  'items_excluded': len(items) - eligible_count,
                  'missing': missing, 'capacity': capacity}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except (OSError, URLError, ValueError) as exc:
        print(f'Emoji audit failed: {exc}', file=sys.stderr)
        return 1
    print(f'Checked {eligible_count} exchange currency items from {len(items)} catalogue entries; {len(missing)} missing mappings.')
    print(f'Excluded {len(items) - eligible_count} uniques, non-exchange entries, and separators.')
    for category, count in sorted(Counter(row['category'] for row in missing).items()):
        print(f'  {category}: {count}')
    print(f'Full list and icon URLs: {args.output}')
    print('This checks local mapping coverage, not whether Discord emoji IDs still exist.')
    print(f"Distinct custom emoji IDs in mapping: {capacity['mapped_custom_emoji_ids']}")
    print(f"Application limit: {APPLICATION_EMOJI_LIMIT}; planned new uploads: at most {capacity['planned_new_uploads_upper_bound']}")
    if capacity['status'] == 'unverified':
        print(f"Mapping-only projection: {capacity['mapping_only_projection_upper_bound']} (not a live inventory check).")
        print('Application usage is unverified. Supply --application-emoji-count with the full Developer Portal count.')
    else:
        print(f"Application usage (supplied): {args.application_emoji_count}; remaining slots: {capacity['remaining_slots']}")
        print(f"Projected application usage: {capacity['projected_application_emoji_count_upper_bound']}; {capacity['status']}")
    print('This budget applies to new uploads to one application, not to server emoji slots. No emojis are uploaded.')
    return 2 if capacity['status'] == 'would_exceed_limit' else 0


if __name__ == '__main__':
    sys.exit(main())
