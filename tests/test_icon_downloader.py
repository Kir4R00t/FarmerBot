import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from tools.get_currency_icons import icon_entries, icon_filename, main


PNG = b'\x89PNG\r\n\x1a\n' + b'test icon bytes'


class IconDownloaderTests(unittest.TestCase):
    def test_upload_filenames_use_lowercase_underscores_without_changing_keys(self):
        for key, filename in (
            ('Soul-Core-Of-Cholotl', 'soul_core_of_cholotl.png'),
            ('mórrigans-insight', 'morrigans_insight.png'),
            ('already_snake_case', 'already_snake_case.png'),
            ('x', 'item_x.png'),
        ):
            with self.subTest(key=key):
                self.assertEqual(icon_filename(key), filename)
                self.assertEqual(icon_entries({'missing': [{'key': key, 'category': 'currency'}]})[0]['key'], key)
        with self.assertRaises(ValueError):
            icon_filename('___')

    def test_conflicting_upload_names_are_rejected_before_downloading(self):
        entries = [{'key': key, 'category': 'currency'} for key in ('new-rune', 'new_rune')]
        with self.assertRaisesRegex(ValueError, 'share upload filename'):
            icon_entries({'missing': entries})

    def test_existing_hyphenated_icons_are_renamed_without_redownloading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.json'
            report.write_text(json.dumps({'missing': [
                {'key': 'soul-core-of-cholotl', 'category': 'ultimatum', 'icon_url': 'https://example.com/core.png'},
            ]}))
            folder = root / 'icons'
            folder.mkdir()
            legacy = folder / 'soul-core-of-cholotl.png'
            legacy.write_bytes(PNG)
            with patch('tools.get_currency_icons.requests.get') as get:
                self.assertEqual(main([str(folder), '--report', str(report)]), 0)
                get.assert_not_called()
            self.assertFalse(legacy.exists())
            self.assertEqual((folder / 'soul_core_of_cholotl.png').read_bytes(), PNG)

    def test_existing_upload_filename_is_not_overwritten_by_legacy_icon(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.json'
            report.write_text(json.dumps({'missing': [{'key': 'new-rune', 'category': 'runes'}]}))
            (root / 'new-rune.png').write_bytes(PNG + b'old')
            destination = root / 'new_rune.png'
            destination.write_bytes(PNG + b'current')
            with patch('tools.get_currency_icons.requests.get') as get:
                self.assertEqual(main([str(root), '--report', str(report)]), 0)
                get.assert_not_called()
            self.assertEqual(destination.read_bytes(), PNG + b'current')
            self.assertEqual((root / 'new-rune.png').read_bytes(), PNG + b'old')

    def test_currency_names_match_audit_keys_and_uniques_are_excluded(self):
        old = {'items': [{'apiId': 'chaos', 'categoryApiId': 'currency', 'iconUrl': 'https://example.com/chaos.png'}]}
        unique = [{'ApiId': None, 'Name': "Hero's Gift", 'Text': "Hero's Gift Ring",
                   'IconUrl': 'https://example.com/ring.png'}]
        self.assertEqual(icon_entries(old)[0]['key'], 'chaos')
        self.assertEqual(icon_entries({'Items': old['items']})[0]['key'], 'chaos')
        self.assertEqual(icon_entries(unique), [])
        self.assertEqual(icon_entries([{'ApiId': 'mórrigans-insight', 'CategoryApiId': 'lineagesupportgems'}])[0]['key'], 'mórrigans-insight')

    def test_invalid_reports_and_unsafe_paths_are_rejected(self):
        for payload in ('html', {'Items': [None]}, {'missing': {}}, {'missing': [None]},
                        {'missing': [{'key': '../escape'}]}, {'missing': [{'key': '/escape'}]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                icon_entries(payload)

    def test_report_filters_categories_excludes_uniques_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'report.json'
            report.write_text(json.dumps({'missing': [
                {'key': 'chaos', 'category': 'currency', 'icon_url': 'https://example.com/chaos.png'},
                {'key': 'hero-s-gift', 'category': 'accessory', 'icon_url': 'https://example.com/ring.png'},
                {'key': 'new-rune', 'category': 'runes', 'icon_url': 'https://example.com/rune.png'},
            ]}))
            folder = root / 'icons'
            args = [str(folder), '--report', str(report), '--category', 'runes', '--category', 'accessory']
            with patch('tools.get_currency_icons.requests.get', return_value=Mock(content=PNG)) as get:
                self.assertEqual(main(args), 0)
                self.assertEqual((folder / 'new_rune.png').read_bytes(), PNG)
                self.assertFalse((folder / 'hero_s_gift.png').exists())
                self.assertFalse((folder / 'chaos.png').exists())
                self.assertEqual(main(args), 0)
                get.assert_called_once_with('https://example.com/rune.png', timeout=30)

    def test_url_mode_reports_failures_without_saving_bad_images_and_continues(self):
        items = [{'ApiId': key, 'IconUrl': url, 'CategoryApiId': 'currency'} for key, url in (
            ('failed', 'https://example.com/failed.png'),
            ('html', 'https://example.com/html.png'),
            ('no-url', None), ('valid', 'https://example.com/valid.png'))]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            responses = [Mock(json=Mock(return_value=items)), requests.Timeout('timeout'),
                         Mock(content=b'<html>not an icon</html>'), Mock(content=PNG)]
            with patch('tools.get_currency_icons.requests.get', side_effect=responses):
                self.assertEqual(main([str(folder), 'https://example.com/Items']), 1)
            self.assertEqual([p.name for p in folder.iterdir()], ['valid.png'])

    def test_bad_json_or_failed_catalog_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            report.write_text('<html>')
            self.assertEqual(main([directory, '--report', str(report)]), 1)
            with patch('tools.get_currency_icons.requests.get', side_effect=requests.Timeout):
                self.assertEqual(main([directory, 'https://example.com/Items']), 1)
