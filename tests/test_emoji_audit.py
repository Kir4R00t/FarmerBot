import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.audit_item_emojis import audit_items, emoji_capacity, main


class EmojiAuditTests(unittest.TestCase):
    def test_live_catalogue_request_identifies_client_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping, output = root / 'mapping.json', root / 'report.json'
            mapping.write_text('{}')
            response = io.BytesIO(b'[{"ApiId":"new","CategoryApiId":"currency"}]')
            with patch('tools.audit_item_emojis.urlopen', return_value=response) as get:
                self.assertEqual(main(['--league', 'Example League', '--mapping', str(mapping),
                                       '--output', str(output)]), 0)
            request = get.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.poe2scout.com/poe2/Leagues/Example%20League/Items')
            self.assertEqual(request.get_header('User-agent'), 'FarmerBot emoji coverage audit')
            self.assertEqual(request.get_header('Accept'), 'application/json')
            self.assertEqual(get.call_args.kwargs['timeout'], 30)
            report = json.loads(output.read_text())
            self.assertEqual(report['source'], request.full_url)
            self.assertEqual(report['missing'][0]['key'], 'new')

    def test_default_report_is_created_inside_local_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mapping = root / 'bot/util/item_emojis.json'
            mapping.parent.mkdir(parents=True)
            mapping.write_text('{}')
            source = root / 'items.json'
            source.write_text('[{"ApiId":"new","Text":"New","CategoryApiId":"currency"}]')
            with patch('tools.audit_item_emojis.ROOT', root):
                self.assertEqual(main(['--input', str(source)]), 0)
            report = root / 'emoji_audit/reports/missing-item-emojis.json'
            self.assertEqual(json.loads(report.read_text())['missing'][0]['key'], 'new')
            self.assertFalse((root / 'reports/missing-item-emojis.json').exists())

    def test_capacity_counts_distinct_ids_and_does_not_infer_live_usage(self):
        mapping = {'one': '<:item:123>', 'alias': '<:renamed:123>',
                   'animated': '<a:animated:456>', 'default-item': '📦'}
        missing = [
            {'key': 'first', 'icon_url': 'https://example.com/shared.png'},
            {'key': 'second', 'icon_url': 'https://example.com/shared.png'},
            {'key': 'no-icon', 'icon_url': None},
        ]
        capacity = emoji_capacity(mapping, missing + [missing[0]])
        self.assertEqual(capacity['mapped_custom_emoji_ids'], 2)
        self.assertEqual(capacity['planned_new_uploads_upper_bound'], 3)
        self.assertEqual(capacity['distinct_missing_icon_urls'], 1)
        self.assertEqual(capacity['missing_keys_without_icon_url'], 1)
        self.assertEqual(capacity['mapping_only_projection_upper_bound'], 5)
        self.assertEqual(capacity['status'], 'unverified')
        self.assertIsNone(capacity['remaining_slots'])
        self.assertIsNone(capacity['projected_application_emoji_count_upper_bound'])

    def test_capacity_includes_unused_uploads_and_handles_limit_boundaries(self):
        missing = [{'key': 'new', 'icon_url': None}]
        for current, expected in ((0, 'within_limit'), (1998, 'within_limit'),
                                  (1999, 'at_limit'), (2000, 'would_exceed_limit')):
            with self.subTest(current=current):
                capacity = emoji_capacity({}, missing, current)
                self.assertEqual(capacity['status'], expected)
                self.assertEqual(capacity['remaining_slots'], 2000 - current)
                self.assertEqual(capacity['projected_application_emoji_count_upper_bound'], current + 1)
        self.assertEqual(emoji_capacity({}, [], 2000)['status'], 'at_limit')
        self.assertEqual(emoji_capacity({}, [], 2001)['status'], 'would_exceed_limit')
        for invalid in (-1, True, '200', 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                emoji_capacity({}, [], invalid)

    def test_matches_api_id_and_name_fallback_and_deduplicates_missing(self):
        items = [
            {'ApiId': 'chaos', 'Text': 'Chaos Orb', 'CategoryApiId': 'currency'},
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

    def test_default_and_empty_mappings_do_not_hide_missing_items(self):
        missing = audit_items(
            [{'ApiId': 'missing', 'Text': 'Missing', 'CategoryApiId': 'currency'},
             {'ApiId': None, 'Name': "Hero's Gift", 'CategoryApiId': 'accessory'}],
            {'default-item': '📦', 'missing': ''},
        )
        self.assertEqual({row['key'] for row in missing}, {'missing'})

    def test_only_npc_exchange_categories_are_audited(self):
        items = [
            {'ApiId': None, 'Name': 'Headhunter', 'CategoryApiId': 'accessory'},
            {'ApiId': '123', 'Name': 'Against the Darkness', 'CategoryApiId': 'jewel'},
            {'ApiId': 'waystone-1', 'Text': 'Waystone', 'CategoryApiId': 'waystones'},
            {'ApiId': 'bear-talisman', 'Text': 'Bear Talisman', 'CategoryApiId': 'talismans'},
            {'ApiId': 'sep', 'Text': 'Currency', 'CategoryApiId': 'currency'},
            {'ApiId': 'unknown', 'Text': 'Unknown', 'CategoryApiId': 'new-unverified-category'},
            {'ApiId': 'new-rune', 'Text': 'New Rune', 'CategoryApiId': 'runes'},
            {'ApiId': 'new-core', 'Text': 'New Core', 'CategoryApiId': 'ultimatum'},
        ]
        missing = audit_items(items, {})
        self.assertEqual({row['key'] for row in missing}, {'new-rune', 'new-core'})
        self.assertEqual(emoji_capacity({}, missing)['planned_new_uploads_upper_bound'], 2)

    def test_offline_cli_writes_report_and_rejects_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, mapping, output = [root / name for name in ('items.json', 'mapping.json', 'report.json')]
            source.write_text('[{"ApiId":"new","Text":"New","CategoryApiId":"currency"},'
                              '{"ApiId":null,"Name":"Headhunter","CategoryApiId":"accessory"}]')
            mapping.write_text('{}')
            args = ['--input', str(source), '--mapping', str(mapping), '--output', str(output)]
            self.assertEqual(main(args), 0)
            report = json.loads(output.read_text())
            self.assertEqual(report['missing'][0]['key'], 'new')
            self.assertEqual(report['scope'], 'currency_exchange')
            self.assertEqual(report['currency_items_checked'], 1)
            self.assertEqual(report['items_excluded'], 1)
            self.assertEqual(report['capacity']['status'], 'unverified')
            self.assertEqual(main(args + ['--application-emoji-count', '1999']), 0)
            self.assertEqual(json.loads(output.read_text())['capacity']['status'], 'at_limit')
            self.assertEqual(main(args + ['--application-emoji-count', '2000']), 2)
            self.assertEqual(json.loads(output.read_text())['capacity']['status'], 'would_exceed_limit')
            self.assertEqual(main(args + ['--application-emoji-count', '-1']), 1)
            source.write_text('<html>')
            self.assertEqual(main(args), 1)
