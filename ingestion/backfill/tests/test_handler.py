import sys
import types

import pytest

from backfill import handler
from backfill.sources import jolpica, registry
from conftest import TODAY, FakeHttp, FakeS3


def test_registry_has_all_four_sources_with_polite_limits():
    sources = registry()
    assert set(sources) == {"statsbomb", "jolpica", "cricsheet", "thesportsdb"}
    assert sources["jolpica"].min_interval >= 3600 / 500  # 500 requests/hour
    assert sources["thesportsdb"].min_interval >= 60 / 30  # 30 requests/minute


def test_run_source_merges_params_over_defaults_and_summarises():
    http, s3 = FakeHttp(), FakeS3()
    http.add(f"{jolpica.BASE_URL}/2025/races.json?limit=100", {"MRData": {"RaceTable": {"Races": []}}})
    summary = handler.run_source("jolpica", {"seasons": [2025]}, s3_client=s3, bucket="b", today=TODAY, http=http)
    assert summary == {
        "source": "jolpica",
        "complete": True,
        "written": 1,
        "skipped": 0,
        "requests": 1,
        "dry_run": False,
    }


def test_run_source_rejects_unknown_source():
    with pytest.raises(ValueError, match="unknown source"):
        handler.run_source("espn", {}, s3_client=FakeS3(), bucket="b")


def test_lambda_handler_wires_env_bucket_and_time_budget(monkeypatch):
    s3 = FakeS3()
    fake_boto3 = types.SimpleNamespace(client=lambda name: s3)
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("RAW_BUCKET", "sports-dev-raw-x")
    monkeypatch.delenv("THESPORTSDB_API_KEY_SECRET_ARN", raising=False)

    captured = {}

    def fake_run_source(source, params, **kw):
        captured.update(source=source, params=params, **kw)
        return {"complete": True}

    monkeypatch.setattr(handler, "run_source", fake_run_source)

    class Ctx:
        remaining = 120_000

        def get_remaining_time_in_millis(self):
            return self.remaining

    ctx = Ctx()
    handler.lambda_handler({"source": "jolpica", "params": {"seasons": [2024]}}, ctx)
    assert captured["bucket"] == "sports-dev-raw-x"
    assert captured["s3_client"] is s3
    assert captured["dry_run"] is False
    assert captured["should_stop"]() is False
    ctx.remaining = 30_000
    assert captured["should_stop"]() is True  # stops a minute before the Lambda timeout


def test_api_key_read_from_secrets_manager(monkeypatch):
    class SM:
        def get_secret_value(self, SecretId):
            assert SecretId == "arn:aws:secretsmanager:us-east-1:123456789012:secret:sports-dev-x"
            return {"SecretString": "k"}

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda name: SM()))
    monkeypatch.setenv("THESPORTSDB_API_KEY_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789012:secret:sports-dev-x")
    assert handler._api_keys() == {"thesportsdb": "k"}


def test_cli_dry_run_requires_no_bucket(monkeypatch, capsys):
    from backfill import __main__ as cli

    monkeypatch.setattr(cli, "run_source", lambda *a, **kw: {"complete": True, "dry_run": kw["dry_run"]})
    assert cli.main(["--source", "statsbomb", "--dry-run"]) == 0
    assert '"dry_run": true' in capsys.readouterr().out


def test_cli_requires_bucket_for_real_runs():
    from backfill import __main__ as cli

    with pytest.raises(SystemExit):
        cli.main(["--source", "statsbomb"])
