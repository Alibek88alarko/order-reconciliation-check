"""10,000 orders, 7 planted errors: the checker must list exactly those 7 rows and nothing else."""
from pathlib import Path

from reconcile.generate import make_orders, plant_errors, write_csv
from reconcile.run import reconcile


def build(tmp_path: Path, n=10_000):
    shop = make_orders(n)
    report, expected = plant_errors(shop)
    write_csv(tmp_path / "shop.csv", shop)
    write_csv(tmp_path / "report.csv", report)
    return expected


def test_finds_exactly_the_planted_errors(tmp_path):
    expected = build(tmp_path)
    findings, days, counts = reconcile(str(tmp_path / "shop.csv"), str(tmp_path / "report.csv"))
    got = sorted((f[0], f[1]) for f in findings)
    assert got == expected                      # same rows, same classification, no false positives
    assert len(findings) == 7
    assert counts["shop_rows"] == 10_000 and counts["report_rows"] == 10_001   # -2 missing +2 dup +1 phantom


def test_every_finding_explains_itself(tmp_path):
    build(tmp_path)
    findings, _, _ = reconcile(str(tmp_path / "shop.csv"), str(tmp_path / "report.csv"))
    for check_name, order_id, order_date, detail in findings:
        assert order_id and order_date and detail
        if check_name == "amount_mismatch":
            assert "diff" in detail
        if check_name == "duplicate_in_report":
            assert "2 times" in detail


def test_one_cent_is_a_finding_not_noise(tmp_path):
    """Rounding drift of 0.01 is reported: a total that is off by a cent is still wrong."""
    build(tmp_path)
    findings, _, _ = reconcile(str(tmp_path / "shop.csv"), str(tmp_path / "report.csv"))
    diffs = [f[3] for f in findings if f[0] == "amount_mismatch"]
    assert any("diff 0.01" in d for d in diffs) and any("diff 12.5" in d for d in diffs)


def test_daily_totals_flag_only_affected_days(tmp_path):
    expected = build(tmp_path)
    findings, days, _ = reconcile(str(tmp_path / "shop.csv"), str(tmp_path / "report.csv"))
    affected = {f[2] for f in findings}
    flagged = {d[0] for d in days}
    assert flagged == affected                  # every planted error moves its day's total, no other day moves


def test_identical_sources_produce_nothing(tmp_path):
    shop = make_orders(2_000)
    write_csv(tmp_path / "a.csv", shop)
    write_csv(tmp_path / "b.csv", shop)
    findings, days, _ = reconcile(str(tmp_path / "a.csv"), str(tmp_path / "b.csv"))
    assert findings == [] and days == []
