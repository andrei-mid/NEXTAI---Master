"""STUB. Owner: @role-2-core. S3 raw-response archive and submitted documents."""

from __future__ import annotations

from verifirm.core.ports.object_store import ObjectStore


class S3ObjectStore(ObjectStore):
    """Implement with S3 PutObject / GetObject / HeadObject on settings.s3_bucket.

    - put(): key `<prefix>/<sha256>`. Skip the upload if HeadObject says it already exists.
    - Bucket in eu-central-1 with SSE-S3 or KMS encryption and versioning on (audit + replay).
    - Submitted client documents need a retention policy (PENDING in DECISIONS.md: GDPR).
    """

    def __init__(self, bucket: str, region: str) -> None:
        self.bucket = bucket
        self.region = region

    async def put(self, data: bytes, *, prefix: str) -> str:
        raise NotImplementedError

    async def put_named(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        raise NotImplementedError
