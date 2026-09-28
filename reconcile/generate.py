"""Synthetic data: a shop export and a reporting-layer copy with a known set of planted errors.

The point is not realism, it is knowing the answer: the checker must find exactly these rows and nothing else.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

COUNTRIES = ["DE", "NL", "BE", "FR", "AT", "PL", "DK", "SE"]


def make_orders(n: int, seed: int = 7, start: date = date(2026, 8, 1), days: int = 45) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        d = start + timedelta(days=rng.randrange(days))
        total = round(rng.uniform(9.9, 249.0), 2)
        rows.append({"order_id": f"O{100000 + i}", "order_date": d.isoformat(),
                     "country": rng.choice(COUNTRIES), "total": f"{total:.2f}", "currency": "EUR"})
    return rows


def plant_errors(shop: list[dict], seed: int = 11) -> tuple[list[dict], list[tuple[str, str]]]:
    """Return the report copy and the list of (check_name, order_id) the checker is expected to produce."""
    rng = random.Random(seed)
    report = [dict(r) for r in shop]
    expected: list[tuple[str, str]] = []
    picks = rng.sample(range(len(report)), 7)

    # 2 orders missing from the report
    for i in picks[0:2]:
        expected.append(("missing_in_report", report[i]["order_id"]))
    # 2 duplicated rows
    for i in picks[2:4]:
        expected.append(("duplicate_in_report", report[i]["order_id"]))
    # 2 amount mismatches: one cent of rounding, one real error
    report[picks[4]]["total"] = f"{float(report[picks[4]]['total']) + 0.01:.2f}"
    report[picks[5]]["total"] = f"{float(report[picks[5]]['total']) + 12.50:.2f}"
    expected.append(("amount_mismatch", report[picks[4]]["order_id"]))
    expected.append(("amount_mismatch", report[picks[5]]["order_id"]))
    # 1 phantom order that the shop never had
    phantom = {"order_id": "O999999", "order_date": report[picks[6]]["order_date"], "country": "DE",
               "total": "49.90", "currency": "EUR"}
    expected.append(("extra_in_report", phantom["order_id"]))

    missing_ids = {report[i]["order_id"] for i in picks[0:2]}
    dup_rows = [dict(report[i]) for i in picks[2:4]]
    report = [r for r in report if r["order_id"] not in missing_ids] + dup_rows + [phantom]
    rng.shuffle(report)
    return report, sorted(expected)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["order_id", "order_date", "country", "total", "currency"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data")
    out.mkdir(parents=True, exist_ok=True)
    shop = make_orders(n)
    report, expected = plant_errors(shop)
    write_csv(out / "shop_export.csv", shop)
    write_csv(out / "report_table.csv", report)
    with (out / "expected_findings.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["check_name", "order_id"]); w.writerows(expected)
    print(f"wrote {n} shop orders, {len(report)} report rows, {len(expected)} planted errors -> {out}/")
