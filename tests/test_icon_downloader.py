import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

from helpful_scripts.get_currency_icons import icon_entries, main


PNG = b'\x89PNG\r\n\x1a\n' + b'test icon bytes'


class IconDownloaderTests(unittest.TestCase):
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
            with patch('helpful_scripts.get_currency_icons.requests.get', return_value=Mock(content=PNG)) as get:
                self.assertEqual(main(args), 0)
                self.assertEqual((folder / 'new-rune.png').read_bytes(), PNG)
                self.assertFalse((folder / 'hero-s-gift.png').exists())
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
            with patch('helpful_scripts.get_currency_icons.requests.get', side_effect=responses):
                self.assertEqual(main([str(folder), 'https://example.com/Items']), 1)
            self.assertEqual([p.name for p in folder.iterdir()], ['valid.png'])

    def test_bad_json_or_failed_catalog_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.json'
            report.write_text('<html>')
            self.assertEqual(main([directory, '--report', str(report)]), 1)
            with patch('helpful_scripts.get_currency_icons.requests.get', side_effect=requests.Timeout):
                self.assertEqual(main([directory, 'https://example.com/Items']), 1)
