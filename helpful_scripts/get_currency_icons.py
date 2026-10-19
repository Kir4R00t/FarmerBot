"""Download NPC currency-exchange icons, optionally from a missing-emoji audit."""

import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.audit_item_emojis import audit_items
from bot.util.emoji_loader import CURRENCY_EMOJI_CATEGORIES


def icon_entries(payload):
    """Accept audit reports, /Items catalogues, and old category responses."""
    if isinstance(payload, dict) and 'missing' in payload:
        entries = payload['missing']
    else:
        items = payload
        if isinstance(payload, dict):
            items = payload.get('Items', payload.get('items'))
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise ValueError('Expected an item list, category response, or emoji audit report')
        # Older category endpoints used camelCase instead of PascalCase.
        normalized = [
            {key[:1].upper() + key[1:]: value for key, value in item.items()}
            for item in items
        ]
        entries = audit_items(normalized, {})
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ValueError('Report missing entries must be a list of objects')
    for entry in entries:
        key = entry.get('key')
        if not isinstance(key, str) or not re.fullmatch(r'[\w-]+', key):
            raise ValueError('Icon keys must be safe, nonempty filename identifiers')
    return [entry for entry in entries
            if entry.get('category') in CURRENCY_EMOJI_CATEGORIES and entry['key'] != 'sep']


def download_icons(entries, folder):
    """Preserve existing files; report each failure and continue with other icons."""
    folder.mkdir(parents=True, exist_ok=True)
    saved = skipped = failed = 0
    for entry in entries:
        key = entry['key']
        destination = folder / (key + '.png')
        if destination.exists():
            skipped += 1
            continue
        url = entry.get('icon_url')
        if not isinstance(url, str) or urlparse(url).scheme not in ('https', 'http'):
            print(f'No usable icon URL for {key}', file=sys.stderr)
            failed += 1
            continue
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            if not response.content.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Response is not a PNG image')
            destination.write_bytes(response.content)
            saved += 1
        except (requests.RequestException, OSError, ValueError) as exc:
            print(f'Could not save {key}: {exc}', file=sys.stderr)
            failed += 1
    print(f'Icons saved: {saved}; already present: {skipped}; failed: {failed}')
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('url', nargs='?', help='PoE2Scout /Items or category endpoint')
    parser.add_argument('--report', type=Path, help='Download only missing entries in this audit JSON')
    parser.add_argument('--category', action='append', help='Category API ID; repeat to select several')
    args = parser.parse_args(argv)
    if bool(args.url) == bool(args.report):
        parser.error('Provide either a URL or --report')
    try:
        if args.report:
            payload = json.loads(args.report.read_text(encoding='utf-8'))
        else:
            response = requests.get(args.url, timeout=30)
            response.raise_for_status()
            payload = response.json()
        entries = icon_entries(payload)
        if args.category:
            entries = [entry for entry in entries if entry.get('category') in args.category]
        print(f'Selected {len(entries)} icons')
        return download_icons(entries, args.folder)
    except (requests.RequestException, OSError, ValueError) as exc:
        print(f'Icon download failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
