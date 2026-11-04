"""CSV import of annual financial statements (format v1, see docs/phase-3-design.md).

Pure parsing and validation. No database access: the service layer persists a clean
``ImportPreview``. pandas reads every cell as text (``dtype=str``, ``keep_default_na=False``),
so it never invents NaN or numbers; each cell is then parsed by the explicit rules below.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd

from app.engine.errors import EngineError, Issue, Severity
from app.engine.historical import HistoricalAnalysis, HistoricalPeriod, analyze_historicals

from .line_items import ITEMS

SCALES: dict[str, Decimal] = {
    "units": Decimal(1),
    "thousands": Decimal(10) ** 3,
    "lakhs": Decimal(10) ** 5,
    "millions": Decimal(10) ** 6,
    "crores": Decimal(10) ** 7,
    "billions": Decimal(10) ** 9,
}
MISSING_TOKENS = {"", "na", "n/a", "-", "—", "–", "nm"}
YEAR_HEADER = re.compile(r"^FY(\d{4})$")
MAX_BYTES = 2_000_000


@dataclass(frozen=True)
class ImportIssue:
    code: str
    message: str
    severity: str  # error|warning|info
    row: int | None = None  # 1-based row in the file
    column: str | None = None


@dataclass(frozen=True)
class ParsedCell:
    value: float | None  # in the company's scale; None = missing
    original_text: str
    original_value: float | None  # in the file's scale
    row: int
    column: str


@dataclass
class ParsedPeriod:
    fiscal_year: int
    period_end: date
    cells: dict[str, ParsedCell] = field(default_factory=dict)

    def value(self, code: str) -> float | None:
        cell = self.cells.get(code)
        return None if cell is None else cell.value


@dataclass
class ImportPreview:
    file_name: str
    file_sha256: str
    currency: str
    file_scale: str
    target_scale: str
    periods: list[ParsedPeriod]
    issues: list[ImportIssue]
    analysis: HistoricalAnalysis | None

    @property
    def errors(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_number(text: str) -> tuple[Decimal | None, str | None]:
    """Return (value, error). ``None`` value with no error means the cell is missing."""
    raw = text.strip()
    if raw.lower() in MISSING_TOKENS:
        return None, None
    s = raw.replace(",", "").replace("−", "-").replace(" ", "")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None, f"'{raw}' is not a number"
    if not d.is_finite():
        return None, f"'{raw}' is not a finite number"
    if negative:
        if d < 0:
            return None, f"'{raw}' mixes parentheses and a minus sign"
        d = -d
    return d, None


def to_period(p: ParsedPeriod) -> HistoricalPeriod:
    names = HistoricalPeriod.__dataclass_fields__
    return HistoricalPeriod(
        fiscal_year=p.fiscal_year,
        **{code: p.value(code) for code in ITEMS if code in names},  # type: ignore[arg-type]
    )


def _issue(
    code: str,
    message: str,
    row: int | None = None,
    column: str | None = None,
    severity: str = "error",
) -> ImportIssue:
    return ImportIssue(code, message, severity, row, column)


def parse_financials_csv(
    data: bytes,
    *,
    file_name: str,
    currency: str,
    file_scale: str,
    company_currency: str,
    company_scale: str,
    fiscal_year_end_month: int,
) -> ImportPreview:
    sha = hashlib.sha256(data).hexdigest()
    issues: list[ImportIssue] = []
    preview = ImportPreview(file_name, sha, currency, file_scale, company_scale, [], issues, None)

    if currency != company_currency:
        issues.append(
            _issue(
                "CURRENCY_MISMATCH",
                f"File currency {currency} differs from the "
                f"company's {company_currency}; FX conversion is not supported.",
            )
        )
    if file_scale not in SCALES:
        issues.append(
            _issue("UNKNOWN_SCALE", f"Scale '{file_scale}' is not one of {sorted(SCALES)}.")
        )
    if len(data) > MAX_BYTES:
        issues.append(_issue("FILE_TOO_LARGE", f"File exceeds {MAX_BYTES:,} bytes."))
    if issues:
        return preview
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        issues.append(_issue("BAD_ENCODING", "File must be UTF-8 encoded."))
        return preview
    if not text.strip():
        issues.append(_issue("EMPTY_FILE", "The file is empty."))
        return preview
    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            header=None,
            skip_blank_lines=True,
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        issues.append(_issue("MALFORMED_CSV", f"Could not read CSV: {exc}"))
        return preview
    rows = df.values.tolist()
    factor = SCALES[file_scale] / SCALES[company_scale]

    header = [str(h).strip() for h in rows[0]]
    if header[0].lower() != "item_code":
        issues.append(
            _issue("MISSING_HEADER", "The first header cell must be 'item_code'.", 1, header[0])
        )
        return preview
    years: list[tuple[int, int, str]] = []  # (column index, year, header)
    for j, h in enumerate(header[1:], start=1):
        m = YEAR_HEADER.match(h)
        if not m:
            issues.append(
                _issue("BAD_YEAR_HEADER", f"Column header '{h}' must look like FY2024.", 1, h)
            )
            continue
        y = int(m.group(1))
        if any(y == yy for _, yy, _ in years):
            issues.append(_issue("DUPLICATE_YEAR", f"{h} appears more than once.", 1, h))
            continue
        years.append((j, y, h))
    if not years:
        issues.append(_issue("NO_YEAR_COLUMNS", "No fiscal-year columns (FY2024, …) found.", 1))
        return preview

    body = [(i + 1, [str(c) for c in r]) for i, r in enumerate(rows) if i > 0]
    period_rows = [(n, r) for n, r in body if r[0].strip().lower() == "period_end"]
    if len(period_rows) != 1:
        issues.append(
            _issue(
                "MISSING_PERIOD_END_ROW" if not period_rows else "DUPLICATE_ITEM",
                "Exactly one 'period_end' row is required.",
            )
        )
        return preview
    pe_row, pe_cells = period_rows[0]
    periods: dict[int, ParsedPeriod] = {}
    for j, y, h in years:
        txt = pe_cells[j].strip()
        try:
            end = date.fromisoformat(txt)
        except ValueError:
            issues.append(_issue("BAD_PERIOD_END", f"'{txt}' is not a YYYY-MM-DD date.", pe_row, h))
            continue
        if end.year != y:
            issues.append(
                _issue(
                    "PERIOD_END_YEAR_MISMATCH",
                    f"{h} ends on {txt}; fiscal years "
                    "are labelled by the calendar year they end in.",
                    pe_row,
                    h,
                )
            )
            continue
        if end.month != fiscal_year_end_month:
            issues.append(
                _issue(
                    "FISCAL_MONTH_MISMATCH",
                    f"{h} ends in month {end.month}, but the "
                    f"company's fiscal year ends in month {fiscal_year_end_month}.",
                    pe_row,
                    h,
                    "warning",
                )
            )
        periods[y] = ParsedPeriod(y, end)

    seen: dict[str, int] = {}
    for n, r in body:
        code = r[0].strip()
        if code.lower() == "period_end" or (not code and not any(c.strip() for c in r)):
            continue
        if code not in ITEMS:
            issues.append(
                _issue("UNKNOWN_ITEM", f"'{code}' is not a recognised item code.", n, "item_code")
            )
            continue
        if code in seen:
            issues.append(
                _issue(
                    "DUPLICATE_ITEM", f"'{code}' also appears on row {seen[code]}.", n, "item_code"
                )
            )
            continue
        seen[code] = n
        for j, y, h in years:
            if y not in periods:
                continue
            raw = r[j] if j < len(r) else ""
            d, err = parse_number(raw)
            if err:
                issues.append(_issue("INVALID_NUMBER", err, n, h))
                continue
            if d is not None and ITEMS[code].magnitude and d < 0:
                issues.append(
                    _issue(
                        "SIGN_CONVENTION",
                        f"{code} is a positive magnitude (D-02); got {raw.strip()}.",
                        n,
                        h,
                    )
                )
                continue
            periods[y].cells[code] = ParsedCell(
                value=None if d is None else float(d * factor),
                original_text=raw.strip(),
                original_value=None if d is None else float(d),
                row=n,
                column=h,
            )

    preview.periods = [periods[y] for y in sorted(periods)]
    if not preview.ok or not preview.periods:
        return preview
    try:
        preview.analysis = analyze_historicals([to_period(p) for p in preview.periods])
    except EngineError as exc:  # defensive: importer checks should already catch these
        for i in exc.issues:
            issues.append(_issue(i.code, i.message))
        return preview
    for i in preview.analysis.issues:
        issues.append(_from_engine(i))
    return preview


def _from_engine(i: Issue) -> ImportIssue:
    sev = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.INFO: "info"}[i.severity]
    return ImportIssue(i.code, i.message, sev, None, i.field)
