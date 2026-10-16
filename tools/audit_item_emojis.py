"""Compare a PoE2Scout item catalogue with FarmerBot's emoji mapping."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def audit_items(items, emojis):
    """Match market-menu's API-ID then slugged-name lookup; preserve icon URLs."""
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise ValueError('Expected the /Items endpoint to return a list of objects')
    missing = {}
    for item in items:
        name = item.get('Name') or item.get('Text') or ''
        api_id = item.get('ApiId') or ''
        if not isinstance(name, str) or not isinstance(api_id, str):
            raise ValueError('Item Name/Text and ApiId must be strings or null')
        slug = re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')
        if not (api_id or slug):
            raise ValueError('Item has no usable API ID or name')
        if any(key and key in emojis for key in (api_id, slug)):
            continue
        key = api_id or slug
        category = item.get('CategoryApiId') or 'unknown'
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
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/missing-item-emojis.json')
    args = parser.parse_args(argv)
    try:
        if args.input:
            items = json.loads(args.input.read_text(encoding='utf-8'))
            source_name = str(args.input)
        else:
            source_name = ('https://api.poe2scout.com/poe2/Leagues/'
                           + quote(args.league, safe='') + '/Items')
            with urlopen(source_name, timeout=30) as response:
                items = json.load(response)
        emojis = json.loads(args.mapping.read_text(encoding='utf-8'))
        if not isinstance(emojis, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in emojis.items()
        ):
            raise ValueError('Emoji mapping must map names to strings')
        missing = audit_items(items, emojis)
        report = {'source': source_name, 'league': args.league,
                  'items_checked': len(items), 'missing': missing}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except (OSError, URLError, ValueError) as exc:
        print(f'Emoji audit failed: {exc}', file=sys.stderr)
        return 1
    print(f'Checked {len(items)} items; {len(missing)} missing mappings.')
    for category, count in sorted(Counter(row['category'] for row in missing).items()):
        print(f'  {category}: {count}')
    print(f'Full list and icon URLs: {args.output}')
    print('This checks local mapping coverage, not whether Discord emoji IDs still exist.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
