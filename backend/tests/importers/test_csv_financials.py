"""CSV import: parsing rules, validation errors with row/column, unit conversion, preview."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.engine.metrics import Status
from app.importers.csv_financials import parse_financials_csv, parse_number

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "ardent_precision_synthetic.csv"


def parse(text: str | bytes, **kw: object):  # type: ignore[no-untyped-def]
    args: dict[str, object] = dict(
        file_name="t.csv",
        currency="INR",
        file_scale="crores",
        company_currency="INR",
        company_scale="crores",
        fiscal_year_end_month=3,
    )
    args.update(kw)
    data = text.encode() if isinstance(text, str) else text
    return parse_financials_csv(data, **args)  # type: ignore[arg-type]


def codes(preview) -> list[str]:  # type: ignore[no-untyped-def]
    return [i.code for i in preview.issues]


HEAD = "item_code,FY2024,FY2025\nperiod_end,2024-03-31,2025-03-31\n"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1,234.5", "1234.5"),
        ("(123)", "-123"),
        ("-5", "-5"),
        ("−12", "-12"),
        ("  42 ", "42"),
        ("0", "0"),
        ("1e3", "1E+3"),
    ],
)
def test_parse_number_values(text: str, expected: str) -> None:
    d, err = parse_number(text)
    assert err is None and str(d) == expected


@pytest.mark.parametrize("text", ["", " ", "NA", "n/a", "N/A", "-", "—", "NM"])
def test_missing_tokens_are_missing_not_zero(text: str) -> None:
    assert parse_number(text) == (None, None)


@pytest.mark.parametrize("text", ["abc", "nan", "NaN", "inf", "-Infinity", "1.2.3", "(-5)", "12%"])
def test_invalid_numbers(text: str) -> None:
    d, err = parse_number(text)
    assert d is None and err


def test_sample_file_imports_cleanly() -> None:
    p = parse(SAMPLE.read_bytes(), file_name=SAMPLE.name)
    assert p.ok, p.errors
    assert [x.fiscal_year for x in p.periods] == [2023, 2024, 2025]
    fy25 = p.periods[-1]
    assert fy25.value("revenue") == 2000.0
    assert fy25.value("reported_ebitda") == 400.0
    assert p.periods[0].value("reported_ebitda") is None  # blank cell → missing
    assert p.periods[0].cells["reported_ebitda"].original_text == ""
    assert fy25.cells["revenue"].row == 3 and fy25.cells["revenue"].column == "FY2025"
    assert p.analysis is not None
    assert p.analysis.metric(2025, "nwc").value == pytest.approx(300.0)
    assert p.analysis.metric(2025, "ebitda_margin").value == pytest.approx(0.20)
    # Clean data: only the informational EBITDA note could appear; no warnings or errors
    assert [i for i in p.issues if i.severity != "info"] == []
    assert len(p.file_sha256) == 64


def test_blank_cells_stay_missing_and_dependent_metrics_are_missing() -> None:
    p = parse(HEAD + "revenue,100,120\ncogs,,70\n")
    assert p.ok
    assert p.periods[0].value("cogs") is None
    assert p.analysis is not None
    assert p.analysis.metric(2024, "gross_profit").status is Status.MISSING
    assert p.analysis.metric(2025, "gross_profit").value == pytest.approx(50.0)


def test_scale_conversion_keeps_original_value() -> None:
    p = parse(HEAD + 'revenue,"1,500",2500\n', file_scale="lakhs", company_scale="crores")
    cell = p.periods[0].cells["revenue"]
    assert cell.value == 15.0  # 1,500 lakhs = 15 crores (exact decimal scaling)
    assert cell.original_value == 1500.0 and cell.original_text == "1,500"
    p2 = parse(HEAD + "revenue,1,3\n", file_scale="thousands", company_scale="crores")
    assert p2.periods[0].value("revenue") == 0.0001  # one rounding only


@pytest.mark.parametrize(
    "body, code, row, column",
    [
        ("revenue,abc,1\n", "INVALID_NUMBER", 3, "FY2024"),
        ("revenue,1,nan\n", "INVALID_NUMBER", 3, "FY2025"),
        ("capex,-5,1\n", "SIGN_CONVENTION", 3, "FY2024"),
        ("revenue,(10),1\n", "SIGN_CONVENTION", 3, "FY2024"),
        ("profit,1,1\n", "UNKNOWN_ITEM", 3, "item_code"),
        ("revenue,1,1\nrevenue,2,2\n", "DUPLICATE_ITEM", 4, "item_code"),
    ],
)
def test_cell_errors_report_row_and_column(body: str, code: str, row: int, column: str) -> None:
    p = parse(HEAD + body)
    assert not p.ok
    err = next(i for i in p.errors if i.code == code)
    assert (err.row, err.column) == (row, column)


def test_signed_items_may_be_negative() -> None:
    p = parse(HEAD + "ebit,(50),10\nnet_income,-60,5\n")
    assert p.ok and p.periods[0].value("ebit") == -50.0


@pytest.mark.parametrize(
    "text, code",
    [
        ("", "EMPTY_FILE"),
        ("code,FY2024\n", "MISSING_HEADER"),
        ("item_code,2024\nperiod_end,2024-03-31\n", "BAD_YEAR_HEADER"),
        ("item_code,FY2024,FY2024\nperiod_end,2024-03-31,2024-03-31\n", "DUPLICATE_YEAR"),
        ("item_code,FY2024\nrevenue,1\n", "MISSING_PERIOD_END_ROW"),
        ("item_code,FY2024\nperiod_end,31/03/2024\n", "BAD_PERIOD_END"),
        ("item_code,FY2024\nperiod_end,2023-03-31\n", "PERIOD_END_YEAR_MISMATCH"),
        ('item_code,FY2024\n"unterminated\n', "MALFORMED_CSV"),
    ],
)
def test_structural_errors(text: str, code: str) -> None:
    assert code in codes(parse(text))


def test_currency_scale_encoding_and_size() -> None:
    assert codes(parse(HEAD, currency="USD")) == ["CURRENCY_MISMATCH"]
    assert codes(parse(HEAD, file_scale="dozens")) == ["UNKNOWN_SCALE"]
    assert codes(parse(b"\xff\xfe\x00bad")) == ["BAD_ENCODING"]
    assert "FILE_TOO_LARGE" in codes(parse(b"x" * 2_000_001))


def test_fiscal_month_mismatch_is_a_warning() -> None:
    p = parse("item_code,FY2024\nperiod_end,2024-12-31\nrevenue,1\n")
    w = [i for i in p.issues if i.code == "FISCAL_MONTH_MISMATCH"]
    assert w and w[0].severity == "warning" and p.ok


def test_engine_consistency_warnings_flow_into_preview() -> None:
    p = parse(HEAD + "revenue,100,120\ncogs,60,70\nopex,30,35\nebit,25,15\nda,95,5\n")
    found = set(codes(p))
    assert {"EBIT_RECONCILIATION", "DA_EXCEEDS_OPERATING_COSTS"} <= found
    assert p.ok  # warnings do not block an import (D-12)


def test_utf8_bom_and_blank_lines_are_tolerated() -> None:
    p = parse("﻿" + HEAD + "\nrevenue,1,2\n\n")
    assert p.ok and p.periods[1].value("revenue") == 2.0
