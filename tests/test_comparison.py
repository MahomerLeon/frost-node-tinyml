"""Tests of the node-vs-forecast comparison (scraper/comparison.py).

Temperatures and thresholds here are test values chosen to make each case
easy to check by hand; they are not project data or decisions.
"""

from datetime import datetime

import pandas as pd

from comparison import class_from_minimum, compare, forecast_in_window
from hash_table import HashTable

CONFIG = {
    "municipality": "Tunja",
    "period_hours": {"Morning": 9, "Noon": 12, "Evening": 18, "Night": 21},
    "comparison_horizon_hours": 6,
}


def make_table():
    table = HashTable()
    for time, temperature in [("2026-11-12 18:00", 13.0), ("2026-11-12 21:00", 11.0),
                              ("2026-11-13 09:00", 15.0), ("2026-11-13 12:00", 18.0)]:
        table.put(("Tunja", time), {"temperature_c": temperature})
    return table


def predictions(*rows):
    return pd.DataFrame([{"time": datetime.fromisoformat(time), "predicted_class": c}
                         for time, c in rows])


def test_window_takes_only_forecasts_after_the_prediction_and_inside_the_horizon():
    table = make_table()
    # 16:00 + 6 h = 22:00 -> 18:00 and 21:00 are inside
    assert forecast_in_window(table, CONFIG, datetime(2026, 11, 12, 16)) == [13.0, 11.0]
    # A forecast at exactly the prediction time is not "after" it
    assert forecast_in_window(table, CONFIG, datetime(2026, 11, 12, 18)) == [11.0]


def test_window_crosses_midnight():
    table = make_table()
    # 04:00 + 6 h = 10:00 of the same day -> only 09:00
    assert forecast_in_window(table, CONFIG, datetime(2026, 11, 13, 4)) == [15.0]
    # 22:00 + 6 h = 04:00 next day -> the page has no values at night
    assert forecast_in_window(table, CONFIG, datetime(2026, 11, 12, 22)) == []


def test_class_rule_matches_the_labeling_rule():
    assert class_from_minimum(5.0, [2.0]) == 0
    assert class_from_minimum(2.0, [2.0]) == 1       # "at or below" the threshold
    assert class_from_minimum(1.0, [2.0, 6.0]) == 2  # three classes
    assert class_from_minimum(4.0, [2.0, 6.0]) == 1
    assert class_from_minimum(9.0, [2.0, 6.0]) == 0


def test_compare_marks_agreement_and_disagreement():
    result = compare(predictions(("2026-11-12T16:00:00", 1), ("2026-11-12T17:00:00", 0)),
                     make_table(), CONFIG, thresholds=[12.0])
    # Forecast minimum is 11.0 <= 12.0 -> forecast class 1
    assert result["forecast minimum (C)"].tolist() == [11.0, 11.0]
    assert result["result"].tolist() == ["agree", "DISAGREE"]


def test_compare_without_threshold_or_without_forecast():
    table = make_table()
    no_threshold = compare(predictions(("2026-11-12T16:00:00", 1)), table, CONFIG, [])
    assert no_threshold["result"].tolist() == ["threshold not set"]
    no_forecast = compare(predictions(("2026-11-12T22:00:00", 1)), table, CONFIG, [12.0])
    assert no_forecast["result"].tolist() == ["no forecast in the window"]
