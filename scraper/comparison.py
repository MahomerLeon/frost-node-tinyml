"""Compare the predictions of the node with the scraped forecast.

These functions have no screen code, so they can be tested without Streamlit
(see tests/test_comparison.py). The dashboard only displays their results.

How the comparison works: for each prediction of the node, the forecast
values that fall inside the next comparison_horizon_hours are looked up in
the hash table. The lowest of them is turned into a class with the same rule
used to label the training data. The two "agree" when the classes are equal.
"""

from datetime import datetime, timedelta

import pandas as pd


def forecast_in_window(table, config, start):
    """Forecast temperatures after `start`, within the comparison horizon.

    The forecast exists only at a few hours of the day, so the candidate
    times are built and each one is looked up in the hash table: O(1) on
    average per lookup, instead of scanning the whole forecast log.
    """
    end = start + timedelta(hours=config["comparison_horizon_hours"])
    found = []
    for day_offset in range(3):
        day = (start + timedelta(days=day_offset)).date()
        for hour in config["period_hours"].values():
            moment = datetime(day.year, day.month, day.day, hour)
            if start < moment <= end:
                key = (config["municipality"], moment.strftime("%Y-%m-%d %H:%M"))
                forecast = table.get(key)
                if forecast is not None:
                    found.append(forecast["temperature_c"])
    return found


def class_from_minimum(minimum, thresholds):
    """Same rule as ml/prepare_dataset.py: thresholds at or above the minimum."""
    return sum(minimum <= t for t in thresholds)


def compare(predictions, table, config, thresholds):
    """One row per node prediction with the forecast of its window.

    predictions needs the columns "time" (datetime) and "predicted_class".
    The "result" column is one of: agree, DISAGREE, threshold not set,
    no forecast in the window.
    """
    rows = []
    for _, prediction in predictions.iterrows():
        temperatures = forecast_in_window(table, config, prediction["time"])
        row = {"node time": prediction["time"],
               "node class": int(prediction["predicted_class"]),
               "forecast minimum (C)": min(temperatures) if temperatures else None,
               "forecast class": None, "result": "no forecast in the window"}
        if temperatures and thresholds:
            row["forecast class"] = class_from_minimum(min(temperatures), thresholds)
            same = row["forecast class"] == row["node class"]
            row["result"] = "agree" if same else "DISAGREE"
        elif temperatures:
            row["result"] = "threshold not set"
        rows.append(row)
    return pd.DataFrame(rows)
