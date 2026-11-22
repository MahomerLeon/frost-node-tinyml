"""Tests of ml/prepare_dataset.py with tiny hand-made tables.

The numbers used here are test inputs chosen to make the expected result
easy to check by hand. They are not project data or thresholds.
"""

import numpy as np
import pandas as pd
import pytest

import prepare_dataset as pd_script

CONFIG = {
    "grid_minutes": 30,
    "window_hours": 3,
    "horizon_hours": 6,
    "max_interpolation_gap_minutes": 60,
    "split": {"train": 0.70, "val": 0.15, "test": 0.15, "seed": 42},
}


def make_grid(temperatures, start="2026-01-01 00:00"):
    """A station already on the 30 min grid, with constant humidity."""
    index = pd.date_range(start, periods=len(temperatures), freq="30min")
    grid = pd.DataFrame({"temperature_c": temperatures, "humidity_pct": 80.0,
                         "pressure_hpa": 739.0, "interpolated": False}, index=index)
    grid["dew_point_c"] = pd_script.dew_point_c(grid["temperature_c"], grid["humidity_pct"])
    return grid


# ------------------------------------------------------------- dew point

def test_dew_point_equals_temperature_at_100_percent_humidity():
    assert pd_script.dew_point_c(np.array([10.0]), np.array([100.0]))[0] == pytest.approx(10.0)


def test_dew_point_known_value():
    # 20 C and 50 % humidity give a dew point of about 9.3 C (standard tables)
    assert pd_script.dew_point_c(np.array([20.0]), np.array([50.0]))[0] == pytest.approx(9.3, abs=0.1)


def test_dew_point_is_nan_for_zero_humidity():
    assert np.isnan(pd_script.dew_point_c(np.array([10.0]), np.array([0.0]))[0])


# --------------------------------------------------------- interpolation

def test_short_gap_is_filled_and_long_gap_is_not():
    index = pd.date_range("2026-01-01 00:00", periods=8, freq="30min")
    #        00:00 00:30 01:00 01:30 02:00 02:30 03:00 03:30
    values = [10.0, None, 12.0, None, None, None, None, 20.0]
    filled, mask = pd_script.interpolate_short_gaps(
        pd.Series(values, index=index), pd.Timedelta(minutes=60))

    assert filled.iloc[1] == pytest.approx(11.0)      # 60 min gap: filled
    assert filled.iloc[3:7].isna().all()              # 150 min gap: left empty
    assert mask.tolist() == [False, True, False, False, False, False, False, False]


def test_values_at_the_edges_are_never_invented():
    index = pd.date_range("2026-01-01 00:00", periods=3, freq="30min")
    filled, _ = pd_script.interpolate_short_gaps(
        pd.Series([None, 5.0, None], index=index), pd.Timedelta(minutes=60))
    assert np.isnan(filled.iloc[0]) and np.isnan(filled.iloc[2])


# ---------------------------------------------------------------- windows

def test_window_lags_and_future_minimum():
    # Temperature equal to the step number: 0, 1, 2, ... 29
    grid = make_grid([float(i) for i in range(30)])
    windows = pd_script.build_windows(grid, has_pressure=True, config=CONFIG)

    # First complete window ends at step 5 (6 steps = 3 h)
    first = windows.iloc[0]
    assert windows.index[0] == grid.index[5]
    assert first["temperature_c_lag0"] == 5.0   # newest reading
    assert first["temperature_c_lag5"] == 0.0   # oldest reading
    # The label looks at the NEXT 12 steps (6..17): the present is excluded
    assert first["future_min_temperature_c"] == 6.0

    # The last window must still have 12 future steps: it ends at step 17
    assert windows.index[-1] == grid.index[17]


def test_window_with_a_missing_reading_is_dropped():
    temperatures = [float(i) for i in range(30)]
    temperatures[8] = np.nan
    grid = make_grid(temperatures)
    windows = pd_script.build_windows(grid, has_pressure=True, config=CONFIG)
    # No window may contain step 8 as an input (windows ending at steps 8..13)
    for step in range(8, 14):
        assert grid.index[step] not in windows.index


def test_missing_pressure_is_allowed_only_when_the_source_has_none():
    grid = make_grid([float(i) for i in range(30)])
    grid["pressure_hpa"] = np.nan
    assert len(pd_script.build_windows(grid, has_pressure=False, config=CONFIG)) > 0
    assert len(pd_script.build_windows(grid, has_pressure=True, config=CONFIG)) == 0


def test_hour_is_encoded_on_a_circle():
    grid = make_grid([5.0] * 60)
    windows = pd_script.build_windows(grid, has_pressure=True, config=CONFIG)
    six_am = windows.loc[pd.Timestamp("2026-01-01 06:00")]
    assert six_am["hour_sin"] == pytest.approx(1.0)
    assert six_am["hour_cos"] == pytest.approx(0.0, abs=1e-9)


# ----------------------------------------------------------- cold events

def test_cold_events_are_counted_as_separate_episodes():
    #                 cold  cold        cold              cold
    grid = make_grid([1.0, 1.5, 8.0, 9.0, 0.5, 7.0, 7.0, 2.0])
    assert pd_script.count_cold_events(grid, threshold=2.0) == 3


# ------------------------------------------------------------------ split

def test_every_day_goes_to_exactly_one_split():
    days = list(pd.date_range("2026-01-01", periods=100, freq="D").date)
    split = pd_script.assign_splits(days * 3, CONFIG)  # repeated days, as in real data
    assert set(split) == set(days)                     # every day assigned once
    counts = pd.Series(list(split.values())).value_counts()
    assert counts.to_dict() == {"train": 70, "val": 15, "test": 15}


def test_split_is_stratified_by_the_class_of_each_day():
    days = list(pd.date_range("2026-01-01", periods=100, freq="D").date)
    # 20 cold days (class 2) and 80 normal days (class 0)
    day_class = {day: (2 if i < 20 else 0) for i, day in enumerate(days)}
    split = pd_script.assign_splits(days, CONFIG, day_class)
    cold = pd.Series([split[day] for day in days[:20]]).value_counts().to_dict()
    normal = pd.Series([split[day] for day in days[20:]]).value_counts().to_dict()
    assert cold == {"train": 14, "val": 3, "test": 3}
    assert normal == {"train": 56, "val": 12, "test": 12}


def test_node_temperature_offset_is_subtracted(tmp_path):
    log = tmp_path / "node_log.csv"
    log.write_text(
        "timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status\n"
        "2026-11-21T02:00:00-05:00,10.50,80.00,740.00,10.00,ok\n"
        "2026-11-21T02:05:00-05:00,nan,nan,nan,10.00,sensor_error\n", encoding="utf-8")
    config = {"paths": {"node_dir": str(tmp_path)}}
    assert pd_script.load_node(config)["temperature_c"].tolist() == [10.5]   # no offset
    config["calibration"] = {"node_temperature_offset_c": 0.5}
    assert pd_script.load_node(config)["temperature_c"].tolist() == [10.0]
    assert "10.50" in log.read_text(encoding="utf-8")   # the raw file is unchanged


def test_node_rows_outside_the_valid_periods_are_ignored(tmp_path):
    log = tmp_path / "node_log.csv"
    log.write_text(
        "timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status\n"
        "2026-11-20T23:00:00-05:00,19.00,60.00,740.00,14.50,ok\n"   # first night, BME280 in the box
        "2026-11-21T19:50:00-05:00,15.00,72.00,740.00,16.50,ok\n"
        "2026-11-21T20:00:00-05:00,14.00,74.00,740.00,14.80,ok\n"
        "2026-11-22T08:30:00-05:00,20.50,61.00,741.00,20.10,ok\n", encoding="utf-8")  # boot at the PC
    config = {"paths": {"node_dir": str(tmp_path)}}
    assert len(pd_script.load_node(config)) == 4                      # no periods: all rows
    config["node"] = {"valid_periods": [["2026-11-21 19:45:00", "2026-11-22 07:40:00"]]}
    assert pd_script.load_node(config)["temperature_c"].tolist() == [15.0, 14.0]
    config["node"] = {"valid_periods": [["2027-01-01 00:00:00", "2027-01-02 00:00:00"]]}
    assert pd_script.load_node(config) is None                        # nothing valid yet
    assert "19.00" in log.read_text(encoding="utf-8")                 # the raw file is unchanged


def test_split_is_reproducible_with_the_same_seed():
    days = list(pd.date_range("2026-01-01", periods=50, freq="D").date)
    assert pd_script.assign_splits(days, CONFIG) == pd_script.assign_splits(days, CONFIG)


def test_no_day_is_shared_between_splits_in_a_built_dataset():
    # 10 days of windows from two "stations" sharing the same dates
    grid = make_grid([5.0] * (48 * 10))
    windows = pd.concat([pd_script.build_windows(grid, True, CONFIG)] * 2).reset_index()
    windows["date"] = windows["index"].dt.date
    windows["split"] = windows["date"].map(pd_script.assign_splits(windows["date"], CONFIG))
    splits_per_day = windows.groupby("date")["split"].nunique()
    assert (splits_per_day == 1).all()  # no data leakage between splits


# --------------------------------------------------------------- labeling

def test_labeling_stops_when_the_threshold_is_missing():
    with pytest.raises(SystemExit):
        pd_script.check_labeling({"labeling": {"num_classes": 2, "thresholds_c": []}})


def test_labeling_accepts_one_threshold_per_class_boundary():
    two = {"labeling": {"num_classes": 2, "thresholds_c": [1.0]}}
    three = {"labeling": {"num_classes": 3, "thresholds_c": [1.0, 4.0]}}
    assert pd_script.check_labeling(two) == [1.0]
    assert pd_script.check_labeling(three) == [1.0, 4.0]
    with pytest.raises(SystemExit):  # thresholds must be in increasing order
        pd_script.check_labeling({"labeling": {"num_classes": 3, "thresholds_c": [4.0, 1.0]}})
