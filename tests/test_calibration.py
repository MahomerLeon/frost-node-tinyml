"""Tests of ml/calibration_report.py with a small hand-made log.

The temperatures are test values chosen so the offset is easy to check by
hand; they are not measurements.
"""

import pytest

import calibration_report

LOG = """timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status
2026-11-17T10:00:00-05:00,20.50,50.00,739.50,20.00,ok
2026-11-17T10:05:00-05:00,20.70,50.00,739.50,20.10,ok
2026-11-17T10:10:00-05:00,nan,nan,nan,20.20,sensor_error
2026-11-17T10:15:00-05:00,21.00,50.00,739.50,nan,ok
2026-11-17T10:20:00-05:00,21.10,50.00,739.50,20.70,ok
"""

OLD_LOG = """timestamp_iso,temperature_c,humidity_pct,pressure_hpa,status
2026-11-12T10:00:00-05:00,20.50,50.00,739.50,ok
"""


def test_offset_uses_only_rows_with_both_sensors(tmp_path):
    file = tmp_path / "node_log.csv"
    file.write_text(LOG, encoding="utf-8")
    pairs = calibration_report.load_pairs([file])

    # The sensor_error row and the row without probe are left out
    assert len(pairs) == 3
    summary = calibration_report.offset_summary(pairs)
    # Offsets: 0.5, 0.6, 0.4 -> mean 0.5
    assert summary["mean_offset_c"] == pytest.approx(0.5)
    assert summary["min_offset_c"] == pytest.approx(0.4)
    assert summary["max_offset_c"] == pytest.approx(0.6)


def test_logs_without_the_probe_column_give_no_pairs(tmp_path):
    file = tmp_path / "old_log.csv"
    file.write_text(OLD_LOG, encoding="utf-8")
    assert len(calibration_report.load_pairs([file])) == 0
