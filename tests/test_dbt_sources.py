"""The dbt project must stay in step with the clean-zone schemas it reads.

The clean-zone tables are defined once, in processing/glue/src/clean_zone; the dbt
sources file is generated from them. These checks fail on drift, so a schema change
in processing cannot silently break the dbt models (or the other way round).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT = ROOT / "dbt"
SOURCES_YML = DBT / "models" / "staging" / "_sources.yml"


def _generator():
    spec = importlib.util.spec_from_file_location("gen_sources", DBT / "scripts" / "gen_sources.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sources_yml_matches_clean_zone_schemas():
    expected = _generator().render()
    actual = SOURCES_YML.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual == expected, (
        "dbt/models/staging/_sources.yml is out of date with processing/glue/src/clean_zone. "
        "Regenerate: python dbt/scripts/gen_sources.py > dbt/models/staging/_sources.yml"
    )


def test_models_only_read_declared_sources():
    declared = set(_generator().used_tables())
    used = set()
    for sql in (DBT / "models").rglob("*.sql"):
        used |= set(re.findall(r"source\(\s*'clean'\s*,\s*'(\w+)'\s*\)", sql.read_text(encoding="utf-8")))
    assert used, "expected the models to read clean-zone sources"
    assert used <= declared, f"models read undeclared sources: {sorted(used - declared)}"


def test_every_model_is_documented_and_tested():
    yml = "".join(p.read_text(encoding="utf-8") for p in (DBT / "models").rglob("*.yml"))
    documented = set(re.findall(r"^  - name: (\w+)$", yml, flags=re.M))
    models = {p.stem for p in (DBT / "models").rglob("*.sql")}
    assert models <= documented, f"models missing from a schema .yml: {sorted(models - documented)}"


def test_required_marts_exist():
    marts = {p.stem for p in (DBT / "models" / "marts").glob("*.sql")}
    assert {"fact_events", "dim_team", "dim_player", "dim_session"} <= marts


def test_profiles_hold_no_credentials():
    text = (DBT / "profiles.yml").read_text(encoding="utf-8")
    for key in ("aws_access_key_id", "aws_secret_access_key", "aws_session_token"):
        assert key not in text
