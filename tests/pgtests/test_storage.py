"""Object storage adapters: local quarantine store and the S3 adapter against the moto emulator (no real bucket)."""
from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from policyguard.infra.storage import LocalObjectStore, S3ObjectStore, sign, verify


def test_local_store_refuses_keys_that_escape_the_root(tmp_path):
    store = LocalObjectStore(tmp_path)
    store.put("quarantine/t1/a", b"x")
    store.move("quarantine/t1/a", "clean/t1/a")
    assert store.get("clean/t1/a") == b"x"
    with pytest.raises(ValueError):
        store.put("../outside", b"x")


def test_s3_adapter_encrypts_and_moves_objects():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(Bucket="pg-test", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        store = S3ObjectStore(client, "pg-test")
        store.put("quarantine/t1/u1", b"%PDF-1.4")
        store.move("quarantine/t1/u1", "clean/t1/u1")
        assert store.get("clean/t1/u1") == b"%PDF-1.4"
        head = client.head_object(Bucket="pg-test", Key="clean/t1/u1")
        assert head["ServerSideEncryption"] == "AES256"
        assert "Contents" not in client.list_objects_v2(Bucket="pg-test", Prefix="quarantine/")


def test_upload_signatures_expire_and_bind_the_upload_id():
    sig = sign(b"k", "upl_1", 2000)
    assert verify(b"k", "upl_1", 2000, sig, now=1999)
    assert not verify(b"k", "upl_1", 2000, sig, now=2000)
    assert not verify(b"k", "upl_2", 2000, sig, now=1000)
