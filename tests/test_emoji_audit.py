import json
from pathlib import Path
import tempfile
import unittest

from tools.audit_item_emojis import audit_items, main


class EmojiAuditTests(unittest.TestCase):
    def test_matches_api_id_and_name_fallback_and_deduplicates_missing(self):
        items = [
            {'ApiId': 'chaos', 'Text': 'Chaos Orb'},
            {'ApiId': None, 'Name': "Hero's Gift", 'Text': "Hero's Gift Ring"},
            {'ApiId': 'new-rune', 'Text': 'New Rune', 'CategoryApiId': 'runes', 'IconUrl': 'https://example.com/icon.png'},
        ]
        missing = audit_items(items + [items[-1]], {'chaos': '<:c:1>', 'hero-s-gift': '<:h:2>'})
        self.assertEqual([row['key'] for row in missing], ['new-rune'])
        self.assertEqual(missing[0]['icon_url'], 'https://example.com/icon.png')

    def test_invalid_response_is_an_error_not_empty_success(self):
        for value in ({'Items': []}, '<html>', [None], [{}]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit_items(value, {})

    def test_offline_cli_writes_report_and_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, mapping, output = [root / name for name in ('items.json', 'mapping.json', 'report.json')]
            source.write_text('[{"ApiId":"new","Text":"New"}]')
            mapping.write_text('{}')
            args = ['--input', str(source), '--mapping', str(mapping), '--output', str(output)]
            self.assertEqual(main(args), 0)
            self.assertEqual(json.loads(output.read_text())['missing'][0]['key'], 'new')
            source.write_text('<html>')
            self.assertEqual(main(args), 1)
