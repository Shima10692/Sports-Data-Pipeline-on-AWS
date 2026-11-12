import datetime as dt

import pytest

from clean_zone.coltypes import coerce, parse_type


@pytest.mark.parametrize(
    "text",
    [
        "string",
        "bigint",
        "array<double>",
        "struct<a:boolean,b:string>",
        "array<struct<teammate:boolean,location_x:double>>",
        "array<array<int>>",
    ],
)
def test_parse_round_trips(text):
    assert parse_type(text).ddl() == text


def test_parse_ignores_spaces_and_case():
    assert parse_type("ARRAY< STRUCT<a: BIGINT> >").ddl() == "array<struct<a:bigint>>"


@pytest.mark.parametrize("bad", ["varchar", "array<double", "struct<a>", "struct<:int>", "intx", "map<string,int>"])
def test_parse_rejects_bad_types(bad):
    with pytest.raises(ValueError):
        parse_type(bad)


@pytest.mark.parametrize(
    "value,type_,expected",
    [
        ("57", "int", 57),
        (3.0, "bigint", 3),
        ("26.0325", "double", 26.0325),
        (1, "double", 1.0),
        ("true", "boolean", True),
        ("False", "boolean", False),
        (7, "string", "7"),
        (True, "string", "true"),
        ("2024-03-02", "date", dt.date(2024, 3, 2)),
        ("1997-09-30T00:00:00", "date", dt.date(1997, 9, 30)),
        ("0000-00-00", "date", None),
        ("2026-05-04T01:46:04.664252", "timestamp", dt.datetime(2026, 5, 4, 1, 46, 4, 664252)),
        ("2024-03-02T15:00:00Z", "timestamp", dt.datetime(2024, 3, 2, 15, 0)),
        ("2024-03-02T17:00:00+02:00", "timestamp", dt.datetime(2024, 3, 2, 15, 0)),
        ("", "int", None),
        ("", "string", ""),
        (None, "array<string>", None),
        (["a", 1], "array<string>", ["a", "1"]),
        ({"a": "1", "b": None}, "struct<a:int,b:string>", (1, None)),
        ([{"x": 1}], "array<struct<x:double,y:double>>", [(1.0, None)]),
    ],
)
def test_coerce(value, type_, expected):
    assert coerce(value, parse_type(type_)) == expected


@pytest.mark.parametrize(
    "value,type_",
    [
        ("1.5", "int"),
        (1.5, "bigint"),
        (True, "int"),
        (2**31, "int"),
        ("abc", "double"),
        (float("nan"), "double"),
        ("maybe", "boolean"),
        ("02/03/2024", "date"),
        ({"a": 1}, "string"),
        ("x", "array<string>"),
        ({"z": 1}, "struct<a:int>"),
    ],
)
def test_coerce_fails_loudly(value, type_):
    with pytest.raises(ValueError):
        coerce(value, parse_type(type_))


def test_error_names_the_column():
    with pytest.raises(ValueError, match=r"tbl\.points"):
        coerce("x", parse_type("double"), "tbl.points")
