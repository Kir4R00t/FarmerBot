import io
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

from bot.services import r2_snapshot_reader as r2
from tests.support import NOW


def key(hour=12, name=""):
    return f"market/dt=2026-10-16/hour={hour:02d}/{name}exchange-snapshot.json"


def payload(hour=12, minute=0, **overrides):
    record = {"snapshot_id": f"s-{hour}-{minute}",
              "captured_at": f"2026-10-16T{hour:02d}:{minute:02d}:00Z", "current_price": 10}
    record.update(overrides)
    return json.dumps([record]).encode()


class SnapshotReaderTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.reader = r2.R2SnapshotReader(client=self.client, bucket=" test-bucket ", prefix=" /market/ ")

    def download(self, data):
        body = io.BytesIO(data) if isinstance(data, bytes) else Mock(read=Mock(return_value=data))
        self.client.get_object.return_value = {"Body": body}
        return body

    def listing(self, *keys):
        self.client.list_objects_v2.return_value = {"Contents": [{"Key": k} for k in keys]}

    def test_configuration_validation(self):
        self.assertEqual(self.reader.bucket, "test-bucket")
        self.assertEqual(self.reader.prefix, "market/")
        for kwargs, error in (({"bucket": " "}, r2.SnapshotConfigurationError),
                              ({"cache_ttl_seconds": -1}, ValueError),
                              ({"max_cached_snapshots": 0}, ValueError)):
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                r2.R2SnapshotReader(client=self.client, **({"bucket": "b"} | kwargs))

    def test_paginated_listing_filters_and_normalises_metadata(self):
        self.client.list_objects_v2.side_effect = [
            {"Contents": [{"Key": "unrelated.json"}, {"Key": key(), "LastModified": NOW.replace(tzinfo=None), "Size": "20"}],
             "IsTruncated": True, "NextContinuationToken": "next"},
            {"Contents": [{"Key": key(11), "LastModified": NOW, "Size": "bad"},
                          {"Key": "dt=2026-99-99/hour=99/exchange-snapshot.json"},
                          {"Key": "exchange-snapshot.json"}]},
        ]
        refs = self.reader.list_snapshot_references()
        self.assertEqual(len(refs), 4)
        self.assertEqual((refs[0].partition_time, refs[0].last_modified, refs[0].size), (NOW, NOW, 20))
        self.assertIsNone(refs[1].size)
        self.assertIsNone(refs[2].partition_time)
        self.assertIsNone(refs[3].last_modified)
        self.client.list_objects_v2.assert_has_calls([
            call(Bucket="test-bucket", Prefix="market/"),
            call(Bucket="test-bucket", Prefix="market/", ContinuationToken="next")])
        self.assertEqual(self.reader.list_snapshot_keys(), tuple(ref.key for ref in refs))
        self.assertEqual(self.client.list_objects_v2.call_count, 2)

    def test_listing_ttl_force_refresh_and_clear(self):
        self.listing(key())
        with patch.object(r2.time, "monotonic", return_value=100):
            self.reader.list_snapshot_keys()
        with patch.object(r2.time, "monotonic", return_value=101):
            self.reader.list_snapshot_keys()
            self.assertEqual(self.client.list_objects_v2.call_count, 1)
            self.reader.list_snapshot_keys(force_refresh=True)
        with patch.object(r2.time, "monotonic", return_value=500):
            self.reader.list_snapshot_keys()
        self.reader.clear_cache()
        self.reader.list_snapshot_keys()
        self.assertEqual(self.client.list_objects_v2.call_count, 4)

    def test_empty_listing_is_cached(self):
        self.client.list_objects_v2.return_value = {"Contents": None}
        self.assertEqual(self.reader.list_snapshot_keys(), ())
        self.assertEqual(self.reader.list_snapshot_keys(), ())
        self.client.list_objects_v2.assert_called_once()

    def test_listing_failures_are_explicit(self):
        for responses in ([{"IsTruncated": True}],
                          [{"IsTruncated": True, "NextContinuationToken": "same"}] * 2):
            with self.subTest(responses=responses):
                self.client.list_objects_v2.side_effect = responses
                with self.assertRaises(r2.SnapshotStorageError):
                    self.reader.list_snapshot_references(force_refresh=True)
        self.client.list_objects_v2.side_effect = OSError("offline")
        with self.assertRaises(r2.SnapshotStorageError) as raised:
            self.reader.list_snapshot_keys()
        self.assertIsInstance(raised.exception.__cause__, OSError)

    def test_load_valid_snapshot_closes_body_and_uses_cache(self):
        body = self.download(b'\xef\xbb\xbf' + payload())
        result = self.reader.load_snapshot(" " + key() + " ")
        self.assertTrue(body.closed)
        self.assertEqual((result.record_count, result.captured_at, result.snapshot_id), (1, NOW, "s-12-0"))
        self.assertIs(self.reader.load_snapshot(key()), result)
        self.client.get_object.assert_called_once_with(Bucket="test-bucket", Key=key())
        self.download(payload(current_price=20))
        self.assertEqual(self.reader.load_snapshot(key(), force_refresh=True).records[0]["current_price"], 20)
        self.reader.clear_cache()
        self.download(payload())
        self.reader.load_snapshot(key())
        self.assertEqual(self.client.get_object.call_count, 3)

    def test_snapshot_cache_evicts_least_recently_used(self):
        reader = r2.R2SnapshotReader(client=self.client, bucket="b", max_cached_snapshots=2)
        self.client.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(payload())}
        for name in ("a", "b", "a", "c", "a", "b"):
            reader.load_snapshot(name)
        self.assertEqual([c.kwargs["Key"] for c in self.client.get_object.call_args_list], ["a", "b", "c", "b"])

    def test_download_failure_and_body_cleanup(self):
        with self.assertRaises(ValueError):
            self.reader.load_snapshot(" ")
        self.client.get_object.side_effect = OSError("offline")
        with self.assertRaises(r2.SnapshotStorageError):
            self.reader.load_snapshot(key())
        self.client.get_object.side_effect = None
        self.client.get_object.return_value = {}
        with self.assertRaises(r2.SnapshotStorageError):
            self.reader.load_snapshot(key())
        body = Mock()
        body.read.side_effect = OSError("read failed")
        self.client.get_object.return_value = {"Body": body}
        with self.assertRaises(r2.SnapshotStorageError):
            self.reader.load_snapshot(key())
        body.close.assert_called_once()

    def test_invalid_payloads_never_enter_cache(self):
        first = json.loads(payload())[0]
        cases = [b'\xff', b'{', None, '{}', '[]', '[1]', '[{}]',
                 json.dumps([first, 1]),
                 json.dumps([first, first | {"snapshot_id": "different"}]),
                 json.dumps([first, first | {"captured_at": ""}]),
                 json.dumps([first, first | {"captured_at": "2026-10-16T13:00:00Z"}]),
                 json.dumps([first | {"captured_at": "invalid"}]),
                 json.dumps([first | {"captured_at": "2026-10-16T12:00:00"}])]
        for data in cases:
            with self.subTest(data=data):
                body = self.download(data)
                with self.assertRaises(r2.InvalidSnapshotError):
                    self.reader.load_snapshot(key())
                if isinstance(body, io.BytesIO):
                    self.assertTrue(body.closed)
                else:
                    body.close.assert_called_once()
        self.assertEqual(self.client.get_object.call_count, len(cases))

    def test_readable_body_without_close_method_is_supported(self):
        class Readable:
            def read(self):
                return payload()
        self.client.get_object.return_value = {"Body": Readable()}
        self.assertEqual(self.reader.load_snapshot(key()).record_count, 1)

    def test_string_payload_and_offset_timestamp_normalisation(self):
        self.download(payload(captured_at="2026-10-16T14:00:00+02:00").decode())
        self.assertEqual(self.reader.load_snapshot(key()).captured_at, NOW)

    def test_latest_uses_partition_and_capture_time_not_upload_time(self):
        keys = [key(10), key(12, "a/"), key(12, "b/"), key(11)]
        self.client.list_objects_v2.return_value = {"Contents": [
            {"Key": k, "LastModified": NOW + timedelta(days=1) if k == key(10) else NOW}
            for k in keys]}
        data = {keys[0]: payload(10), keys[1]: payload(12, 5), keys[2]: payload(12, 55), keys[3]: payload(11)}
        self.client.get_object.side_effect = lambda **kw: {"Body": io.BytesIO(data[kw["Key"]])}
        latest = self.reader.load_latest_snapshots(2, require_count=True)
        self.assertEqual([s.key for s in latest], [keys[2], keys[1]])
        self.assertEqual(self.client.get_object.call_count, 2)
        self.assertEqual(self.reader.load_latest_snapshot().key, keys[2])
        self.assertEqual(self.reader.get_latest_snapshot().key, keys[2])
        self.assertEqual(len(self.reader.load_latest_snapshots(10)), 4)
        with self.assertRaises(r2.SnapshotNotFoundError):
            self.reader.load_latest_snapshots(10, require_count=True)

    def test_latest_lookup_rejects_missing_unpartitioned_and_mismatched_data(self):
        with self.assertRaises(ValueError):
            self.reader.load_latest_snapshots(0)
        self.listing()
        with self.assertRaises(r2.SnapshotNotFoundError):
            self.reader.load_latest_snapshot()
        self.listing("exchange-snapshot.json")
        with self.assertRaisesRegex(r2.SnapshotNotFoundError, "partitioned"):
            self.reader.load_latest_snapshots(force_refresh=True)
        self.listing(key())
        self.download(payload(11))
        with self.assertRaises(r2.InvalidSnapshotError):
            self.reader.load_latest_snapshots(force_refresh=True)


class SnapshotEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.env = {"R2_ENDPOINT": "https://example.invalid", "R2_ACCESS_KEY_ID": "fake-key",
                    "R2_SECRET_ACCESS_KEY": "fake-secret", "R2_BUCKET": "bucket"}

    def test_missing_configuration_lists_variable_names(self):
        with self.assertRaisesRegex(r2.SnapshotConfigurationError, "R2_ENDPOINT"):
            r2.R2SnapshotReader.from_env(environ={})

    def test_client_configuration_and_bucket_alias(self):
        env = self.env | {"R2_BUCKET": "", "R2_BUCKET_ID": "alias", "R2_SNAPSHOT_PREFIX": "market", "R2_REGION": "test"}
        with patch("boto3.client") as factory, patch.dict(os.environ, env, clear=True):
            reader = r2.R2SnapshotReader.from_env(cache_ttl_seconds=12, max_cached_snapshots=2)
        self.assertIs(reader._client, factory.return_value)
        self.assertEqual((reader.bucket, reader.prefix, reader.cache_ttl_seconds, reader.max_cached_snapshots), ("alias", "market/", 12, 2))
        args = factory.call_args.kwargs
        self.assertEqual(args["region_name"], "test")
        self.assertEqual(args["config"].signature_version, "s3v4")
        self.assertEqual(args["config"].s3, {"addressing_style": "path"})

    def test_client_creation_and_missing_dependency_errors(self):
        with patch("boto3.client", side_effect=ValueError("invalid endpoint")):
            with self.assertRaisesRegex(r2.SnapshotConfigurationError, "Could not create"):
                r2.R2SnapshotReader.from_env(environ=self.env)
        with patch.dict(sys.modules, {"boto3": None}):
            with self.assertRaisesRegex(r2.SnapshotConfigurationError, "boto3 is required"):
                r2.R2SnapshotReader.from_env(environ=self.env)
