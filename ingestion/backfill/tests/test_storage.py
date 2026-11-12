import datetime as dt

import pytest

from backfill.storage import RawWriter, raw_key
from conftest import FakeClientError


class TestRawKey:
    def test_builds_partitioned_key(self):
        assert raw_key("jolpica", dt.date(2024, 3, 2), "results/season=2024/round=01.json") == (
            "source=jolpica/date=2024-03-02/results/season=2024/round=01.json"
        )

    def test_accepts_iso_string_date(self):
        assert raw_key("cricsheet", "2024-01-05", "matches/match_id=1.json").startswith(
            "source=cricsheet/date=2024-01-05/"
        )

    @pytest.mark.parametrize("bad", ["2024-13-01", "20240101", "yesterday"])
    def test_rejects_bad_dates(self, bad):
        with pytest.raises(ValueError):
            raw_key("jolpica", bad, "x.json")

    @pytest.mark.parametrize("bad", ["Jolpica", "jol pica", "a/b", ""])
    def test_rejects_bad_source_names(self, bad):
        with pytest.raises(ValueError):
            raw_key(bad, "2024-01-01", "x.json")

    @pytest.mark.parametrize("bad", ["../escape.json", "/abs.json", "a/../b.json", "has space.json", "q?.json"])
    def test_rejects_unsafe_paths(self, bad):
        with pytest.raises(ValueError):
            raw_key("jolpica", "2024-01-01", bad)


class TestRawWriter:
    def test_put_writes_once_and_never_overwrites(self, s3):
        w = RawWriter(s3, "b")
        assert w.put("k.json", b"first", source_url="u") is True
        assert w.put("k.json", b"second", source_url="u") is False
        assert s3.objects["k.json"]["Body"] == b"first"
        assert (w.stats.written, w.stats.skipped) == (1, 1)

    def test_put_is_conditional_and_records_source(self, s3):
        RawWriter(s3, "b").put("k.json", b"{}", source_url="https://example.test/x")
        obj = s3.objects["k.json"]
        assert obj["ContentType"] == "application/json"
        assert obj["Metadata"] == {"source-url": "https://example.test/x"}

    def test_put_if_absent_skips_fetch_for_existing_key(self, s3):
        w = RawWriter(s3, "b")
        w.put("k.json", b"x", source_url="u")
        fetched = []
        assert w.put_if_absent("k.json", lambda: fetched.append(1) or b"y", source_url="u") is False
        assert fetched == []  # no API call spent on data we already have

    def test_put_if_absent_fetches_missing_key(self, s3):
        w = RawWriter(s3, "b")
        assert w.put_if_absent("new.json", lambda: b"data", source_url="u") is True
        assert s3.objects["new.json"]["Body"] == b"data"

    def test_dry_run_writes_nothing(self, s3):
        w = RawWriter(s3, "b", dry_run=True)
        assert w.put_if_absent("k.json", lambda: b"x", source_url="u") is True
        assert s3.objects == {} and s3.heads == 0
        assert w.stats.keys_written == ["k.json"]

    def test_unexpected_s3_errors_propagate(self):
        class Broken:
            def head_object(self, **_):
                raise FakeClientError("AccessDenied")

            def put_object(self, **_):
                raise FakeClientError("AccessDenied")

        w = RawWriter(Broken(), "b")
        with pytest.raises(FakeClientError):
            w.exists("k")
        with pytest.raises(FakeClientError):
            w.put("k", b"x", source_url="u")
