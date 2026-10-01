#!/usr/bin/env python3
"""Calculate margin comparisons from explicit, normalized customer CSV data."""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
from pathlib import Path

REQUIRED = {"record_id", "company", "currency", "period", "revenue", "cogs"}
ZERO = Decimal("0")
HUNDRED = Decimal("100")
getcontext().prec = 50


def amount(value, line, field):
    normalized = value.strip() if isinstance(value, str) else ""
    if len(normalized) > 40 or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", normalized):
        raise ValueError(f"Line {line}: invalid {field}; provide a plain signed decimal")
    try:
        result = Decimal(normalized)
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Line {line}: invalid {field}; provide a plain signed decimal") from None
    if not result.is_finite() or result.copy_abs() > Decimal("1e18"):
        raise ValueError(f"Line {line}: non-finite or out-of-range {field}")
    if result.as_tuple().exponent < -6:
        raise ValueError(f"Line {line}: {field} exceeds six decimal places")
    return result


def read_rows(path):
    rows, seen = [], set()
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED <= set(reader.fieldnames or []):
            raise ValueError("Missing CSV fields: " + ", ".join(sorted(REQUIRED - set(reader.fieldnames or []))))
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError("Duplicate CSV column names")
        for line, row in enumerate(reader, 2):
            if None in row or any(row.get(field) is None for field in REQUIRED):
                raise ValueError(f"Line {line}: incorrect column count")
            for field in REQUIRED - {"revenue", "cogs"}:
                row[field] = row[field].strip()
                if not row[field]:
                    raise ValueError(f"Line {line}: missing {field}")
            currency = row["currency"]
            if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
                raise ValueError(f"Line {line}: currency must be an uppercase three-letter code")
            key = (row["company"], row["record_id"])
            if key in seen:
                raise ValueError(f"Line {line}: duplicate source record within company")
            seen.add(key)
            row["revenue"] = amount(row["revenue"], line, "revenue")
            row["cogs"] = amount(row["cogs"], line, "cogs")
            row["segment"] = (row.get("segment") or "").strip() or "Unallocated"
            rows.append(row)
    if not rows:
        raise ValueError("CSV has no data rows")
    return rows


def display(number):
    if number is None:
        return None
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(abs(rounded) if rounded == ZERO else rounded, "f")


def aggregate(rows):
    if not rows:
        return None
    revenue = sum((row["revenue"] for row in rows), ZERO)
    cogs = sum((row["cogs"] for row in rows), ZERO)
    profit = revenue - cogs
    return {"row_count": len(rows), "revenue": revenue, "cogs": cogs,
            "gross_profit": profit, "gross_margin_pct": profit / revenue * HUNDRED if revenue else None}


def compare_group(rows, current, prior):
    current_totals = aggregate([row for row in rows if row["period"] == current])
    prior_totals = aggregate([row for row in rows if row["period"] == prior])
    result = {"current": current_totals, "prior": prior_totals, "changes": None,
              "warnings": []}
    if current_totals is None or prior_totals is None:
        result["warnings"].append("One comparison period is absent; missing data was not replaced with zero.")
    else:
        delta = current_totals["revenue"] - prior_totals["revenue"]
        cm, pm = current_totals["gross_margin_pct"], prior_totals["gross_margin_pct"]
        result["changes"] = {
            "revenue": delta,
            "revenue_pct": delta / prior_totals["revenue"] * HUNDRED if prior_totals["revenue"] else None,
            "cogs": current_totals["cogs"] - prior_totals["cogs"],
            "gross_profit": current_totals["gross_profit"] - prior_totals["gross_profit"],
            "gross_margin_percentage_points": cm - pm if cm is not None and pm is not None else None,
        }
        if prior_totals["revenue"] <= ZERO:
            result["warnings"].append("Prior revenue is zero or negative; interpret percentage change cautiously.")
    return result


def review(rows, current, prior):
    if not current or not prior or current == prior:
        raise ValueError("Provide two distinct nonempty fiscal period labels")
    relevant = [row for row in rows if row["period"] in {current, prior}]
    if not relevant:
        raise ValueError("Neither requested period appears in the input")
    groups = defaultdict(list)
    for row in relevant:
        groups[(row["company"], row["currency"])].append(row)
    results = []
    for (company, currency), group in sorted(groups.items()):
        item = {"company": company, "currency": currency, **compare_group(group, current, prior)}
        segments = defaultdict(list)
        for row in group:
            segments[row["segment"]].append(row)
        item["segments"] = [{"segment": name, **compare_group(segment_rows, current, prior)}
                            for name, segment_rows in sorted(segments.items())]
        results.append(item)
    return {"current_period": current, "prior_period": prior,
            "reconciliation": "Calculated from supplied data; control total not provided.",
            "source_completeness": "Not verified by this calculator.",
            "rows_read": len(rows), "rows_used": len(relevant), "groups": results}


def json_default(value):
    if isinstance(value, Decimal):
        return display(value)
    raise TypeError(f"Unsupported value: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--current", required=True)
    parser.add_argument("--prior", required=True)
    args = parser.parse_args()
    try:
        result = review(read_rows(args.input), args.current, args.prior)
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, default=json_default, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
