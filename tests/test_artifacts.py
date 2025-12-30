import unittest

from worker_llm_client.artifacts.domain import (
    ArtifactPathPolicy,
    GcsUri,
    InvalidGcsUri,
    InvalidIdentifier,
)
from worker_llm_client.artifacts.services import ArtifactWriteFailed, WriteResult
from worker_llm_client.infra.gcs import GcsArtifactStore


class FakeBlob:
    def __init__(self, *, exists: bool = False, raise_on_upload: Exception | None = None) -> None:
        self._exists = exists
        self.raise_on_upload = raise_on_upload
        self.uploads: list[dict] = []

    def download_as_bytes(self) -> bytes:
        return b"payload"

    def exists(self) -> bool:
        return self._exists

    def upload_from_string(self, data: bytes, *, content_type: str, if_generation_match: int) -> None:
        if self.raise_on_upload is not None:
            raise self.raise_on_upload
        self.uploads.append(
            {
                "data": data,
                "content_type": content_type,
                "if_generation_match": if_generation_match,
            }
        )


class FakeBucket:
    def __init__(self, blob: FakeBlob) -> None:
        self._blob = blob

    def blob(self, object_path: str) -> FakeBlob:
        return self._blob


class FakeClient:
    def __init__(self, blob: FakeBlob) -> None:
        self._bucket = FakeBucket(blob)

    def bucket(self, name: str) -> FakeBucket:
        return self._bucket


class ArtifactsDomainTests(unittest.TestCase):
    def test_gcs_uri_parse_ok(self) -> None:
        uri = GcsUri.parse("gs://bucket/path/to/object.json")
        self.assertEqual(uri.bucket, "bucket")
        self.assertEqual(uri.object_path, "path/to/object.json")
        self.assertEqual(str(uri), "gs://bucket/path/to/object.json")

    def test_gcs_uri_parse_invalid(self) -> None:
        with self.assertRaises(InvalidGcsUri):
            GcsUri.parse("http://bucket/object")
        with self.assertRaises(InvalidGcsUri):
            GcsUri.parse("gs://")
        with self.assertRaises(InvalidGcsUri):
            GcsUri.parse("gs://bucket")
        with self.assertRaises(InvalidGcsUri):
            GcsUri.parse("gs://bucket/")
        with self.assertRaises(InvalidGcsUri):
            GcsUri.parse("gs://bucket/with#fragment")

    def test_artifact_path_policy_prefix_normalization(self) -> None:
        policy = ArtifactPathPolicy(bucket="bkt", prefix="/foo/bar/")
        uri = policy.report_uri("run-1", "1M", "llm_report_1M_v1")
        self.assertEqual(str(uri), "gs://bkt/foo/bar/run-1/1M/llm_report_1M_v1.json")

        policy = ArtifactPathPolicy(bucket="bkt", prefix=" ")
        uri = policy.report_uri("run-1", "1M", "llm_report_1M_v1")
        self.assertEqual(str(uri), "gs://bkt/run-1/1M/llm_report_1M_v1.json")

    def test_artifact_path_policy_timeframe_mismatch(self) -> None:
        policy = ArtifactPathPolicy(bucket="bkt", prefix=None)
        with self.assertRaises(InvalidIdentifier):
            policy.report_uri("run-1", "1D", "llm_report_1M_v1")

    def test_artifact_path_policy_step_id_no_timeframe_token_ok(self) -> None:
        policy = ArtifactPathPolicy(bucket="bkt", prefix=None)
        uri = policy.report_uri("run-1", "1M", "llmreport_summary_v1")
        self.assertEqual(str(uri), "gs://bkt/run-1/1M/llmreport_summary_v1.json")


class ArtifactStoreTests(unittest.TestCase):
    def test_write_create_only_success(self) -> None:
        blob = FakeBlob()
        store = GcsArtifactStore(FakeClient(blob))
        uri = GcsUri.parse("gs://bucket/path/report.json")
        result = store.write_bytes_create_only(uri, b"data", content_type="application/json")
        self.assertIsInstance(result, WriteResult)
        self.assertTrue(result.created)
        self.assertFalse(result.reused)
        self.assertEqual(blob.uploads[0]["if_generation_match"], 0)

    def test_write_create_only_already_exists(self) -> None:
        class AlreadyExists(Exception):
            pass

        blob = FakeBlob(raise_on_upload=AlreadyExists())
        store = GcsArtifactStore(FakeClient(blob))
        uri = GcsUri.parse("gs://bucket/path/report.json")
        result = store.write_bytes_create_only(uri, b"data", content_type="application/json")
        self.assertFalse(result.created)
        self.assertTrue(result.reused)

    def test_write_create_only_retryable_error(self) -> None:
        class ServiceUnavailable(Exception):
            pass

        blob = FakeBlob(raise_on_upload=ServiceUnavailable())
        store = GcsArtifactStore(FakeClient(blob))
        uri = GcsUri.parse("gs://bucket/path/report.json")
        with self.assertRaises(ArtifactWriteFailed) as ctx:
            store.write_bytes_create_only(uri, b"data", content_type="application/json")
        self.assertTrue(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
