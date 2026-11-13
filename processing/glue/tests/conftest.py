"""Offline fakes for both engines: no Spark, no network, no AWS."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest


class FakeClientError(Exception):
    """Mimics botocore's ClientError shape (err.response['Error']['Code'])."""

    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    """list_objects_v2 paginator (2 keys per page, to exercise paging), get/put/delete."""

    def __init__(self, objects: dict[str, Any] | None = None):
        self.objects = {k: (v if isinstance(v, bytes) else json.dumps(v).encode()) for k, v in (objects or {}).items()}
        self.gets: list[str] = []
        self.prefixes: list[str] = []
        self.puts: list[str] = []
        self.deleted: list[str] = []

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket: str, Prefix: str):
        self.prefixes.append(Prefix)
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        if not keys:
            yield {"KeyCount": 0}
        for i in range(0, len(keys), 2):
            yield {"Contents": [{"Key": k} for k in keys[i : i + 2]]}

    def get_object(self, Bucket: str, Key: str):
        self.gets.append(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes):
        self.puts.append(Key)
        self.objects[Key] = Body

    def delete_objects(self, Bucket: str, Delete: dict):
        assert len(Delete["Objects"]) <= 1000
        for o in Delete["Objects"]:
            self.deleted.append(o["Key"])
            del self.objects[o["Key"]]
        return {}


class FakeGlue:
    """Just enough of the Glue Data Catalog API."""

    def __init__(self):
        self.tables: dict[tuple[str, str], dict] = {}
        self.partitions: dict[tuple[str, str], dict[tuple, dict]] = {}
        self.calls: list[str] = []

    def get_table(self, DatabaseName: str, Name: str):
        self.calls.append("get_table")
        if (DatabaseName, Name) not in self.tables:
            raise FakeClientError("EntityNotFoundException")
        return {"Table": self.tables[(DatabaseName, Name)]}

    def create_table(self, DatabaseName: str, TableInput: dict):
        self.calls.append("create_table")
        self.tables[(DatabaseName, TableInput["Name"])] = TableInput

    def update_table(self, DatabaseName: str, TableInput: dict):
        self.calls.append("update_table")
        assert (DatabaseName, TableInput["Name"]) in self.tables
        self.tables[(DatabaseName, TableInput["Name"])] = TableInput

    def batch_create_partition(self, DatabaseName: str, TableName: str, PartitionInputList: list[dict]):
        self.calls.append("batch_create_partition")
        assert len(PartitionInputList) <= 100
        parts = self.partitions.setdefault((DatabaseName, TableName), {})
        errors = []
        for p in PartitionInputList:
            values = tuple(p["Values"])
            if values in parts:
                errors.append({"PartitionValues": list(values), "ErrorDetail": {"ErrorCode": "AlreadyExistsException"}})
            else:
                parts[values] = p
        return {"Errors": errors}

    def batch_update_partition(self, DatabaseName: str, TableName: str, Entries: list[dict]):
        self.calls.append("batch_update_partition")
        parts = self.partitions[(DatabaseName, TableName)]
        for e in Entries:
            parts[tuple(e["PartitionValueList"])] = e["PartitionInput"]
        return {"Errors": []}


@pytest.fixture
def fake_glue() -> FakeGlue:
    return FakeGlue()


@pytest.fixture
def fake_s3_factory():
    return FakeS3


@pytest.fixture
def client_error():
    return FakeClientError
