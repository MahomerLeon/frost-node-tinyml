"""Build the training dataset from the node logs and the public sources.

Run from the repository root:
    python ml/prepare_dataset.py
    python ml/prepare_dataset.py --config path/to/other_config.yaml

Output (N = dataset_version in the config):
    data/processed/dataset_vN.csv          one row per training window
    data/processed/dataset_vN_report.txt   class balance, coverage, warnings
    data/processed/dataset_vN_config.yaml  copy of the config that was used

Each output row is one window:
    source, station, timestamp, date, split, label, future_min_temperature_c,
    interpolated_fraction, hour_sin, hour_cos, and the last readings of each
    variable: <variable>_lag0 is the newest, <variable>_lag5 the oldest
    (with the default 30 min grid and 3 h window).

Design decisions:
- All timestamps are treated as local time (Colombia, UTC-5). The node writes
  the offset explicitly; for IDEAM and Zenodo this is an assumption (their
  files have no time zone).
- The split is done by calendar DAY and the same day goes to the same split
  for every source and station, so two stations never share a day across
  train and test. Known limitation: a window near midnight uses a few hours
  of the neighbouring day.
- Raw input files are only read, never modified.
"""

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"

# Measured variables. Dew point is computed from temperature and humidity.
MEASURED = ["temperature_c", "humidity_pct", "pressure_hpa"]
FEATURES = ["temperature_c", "humidity_pct", "pressure_hpa", "dew_point_c"]

IDEAM_FILES = {
    "temperature_c": "temperatura_uptc_tunja.csv",
    "humidity_pct": "humedad_uptc_tunja.csv",
    "pressure_hpa": "presion_uptc_tunja.csv",
}


# ------------------------------------------------------------------ helpers

def dew_point_c(temperature_c, humidity_pct):
    """Dew point with the Magnus formula.

        gamma = ln(RH / 100) + a * T / (b + T)
        Td    = b * gamma / (a - gamma)

    with a = 17.625 and b = 243.04 C (Alduchov and Eskridge, 1996).
    T is the air temperature in C and RH the relative humidity in %.
    The firmware must use exactly the same formula and constants.
    """
    a, b = 17.625, 243.04
    humidity = np.where(humidity_pct > 0, humidity_pct, np.nan)  # ln(0) is undefined
    gamma = np.log(humidity / 100.0) + a * temperature_c / (b + temperature_c)
    return b * gamma / (a - gamma)


def interpolate_short_gaps(series, max_gap):
    """Fill gaps by linear interpolation, but only short ones.

    A missing value is filled only if the real readings before and after it
    are at most max_gap apart. Returns (filled series, mask of filled values).
    """
    real = series.notna()
    times = series.index.to_series()
    previous_real = times.where(real).ffill()
    next_real = times.where(real).bfill()
    gap = next_real - previous_real  # NaT at the edges -> never filled

    filled = series.interpolate(method="time", limit_area="inside")
    too_long = ~real & ~(gap <= max_gap)
    filled[too_long] = np.nan
    return filled, ~real & filled.notna()


# ------------------------------------------------------------------ sources
# Every loader returns the same columns:
#   source, station, timestamp (local, no time zone), temperature_c,
#   humidity_pct, pressure_hpa, source_interpolated (True if the SOURCE
#   itself had already filled in that value)

def load_node(config):
    """Source A: CSV logs captured with our own node."""
    files = sorted((REPO_DIR / config["paths"]["node_dir"]).glob("*.csv"))
    if not files:
        return None
    table = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    table = table[table["status"] == "ok"]  # ignore sensor_error rows
    if table.empty:
        return None
    # "2026-11-12T21:30:00-05:00" -> keep the local wall-clock time
    table["timestamp"] = pd.to_datetime(
        table["timestamp_iso"].str.slice(0, 19), format="%Y-%m-%dT%H:%M:%S")
    table = table.drop_duplicates("timestamp")  # two dumps may overlap
    table["source"] = "node"
    table["station"] = "node"
    table["source_interpolated"] = False
    return table[["source", "station", "timestamp"] + MEASURED + ["source_interpolated"]]


def load_ideam(config):
    """Source B: IDEAM station UPTC Tunja (hourly)."""
    folder = REPO_DIR / config["paths"]["ideam_dir"]
    columns = []
    for name, file_name in IDEAM_FILES.items():
        raw = pd.read_csv(folder / file_name,
                          usecols=["fechaobservacion", "valorobservado"],
                          parse_dates=["fechaobservacion"])
        # Several readings may share an hour: average them
        hourly = raw.groupby(raw["fechaobservacion"].dt.floor("h"))["valorobservado"].mean()
        columns.append(hourly.rename(name))
    table = pd.concat(columns, axis=1, sort=True)
    table.index.name = "timestamp"
    table = table.reset_index()
    table["source"] = "ideam"
    table["station"] = "uptc_tunja"
    table["source_interpolated"] = False
    return table[["source", "station", "timestamp"] + MEASURED + ["source_interpolated"]]


def load_zenodo(config):
    """Source C: Zenodo Altiplano frost dataset (30 min, no pressure)."""
    with zipfile.ZipFile(REPO_DIR / config["paths"]["zenodo_zip"]) as archive:
        with archive.open(config["paths"]["zenodo_member"]) as member:
            raw = pd.read_csv(member, compression="gzip", low_memory=False,
                              parse_dates=["timestamp"])

    # 1. Remove the excluded stations before anything else
    raw = raw[~raw["station_id"].isin(config["zenodo"]["exclude_stations"])]
    # 2. Temperature and humidity both exactly 0.0 means a sensor failure
    sensor_failure = (raw["temperature_c"] == 0.0) & (raw["relative_humidity_pct"] == 0.0)
    raw = raw[~sensor_failure]

    table = pd.DataFrame({
        "source": "zenodo",
        "station": "zenodo_" + raw["station_id"].astype(str),
        "timestamp": raw["timestamp"],
        "temperature_c": raw["temperature_c"],
        "humidity_pct": raw["relative_humidity_pct"],
        "pressure_hpa": np.nan,  # this dataset has no pressure
        # The dataset marks the values its authors reconstructed
        "source_interpolated": (raw["temperature_c_status"] != "observed")
                               | (raw["relative_humidity_pct_status"] != "observed"),
    })
    return table


# -------------------------------------------------------- grid and windows

def to_grid(station_table, config):
    """Put one station on the regular time grid and fill short gaps."""
    step = pd.Timedelta(minutes=config["grid_minutes"])
    max_gap = pd.Timedelta(minutes=config["max_interpolation_gap_minutes"])
    indexed = station_table.set_index("timestamp").sort_index()

    # resample() creates every step between the first and last reading
    grid = indexed[MEASURED].resample(step).mean()
    from_source = indexed["source_interpolated"].astype(float).resample(step).max() > 0

    filled_here = pd.Series(False, index=grid.index)
    for column in MEASURED:
        grid[column], mask = interpolate_short_gaps(grid[column], max_gap)
        if column != "pressure_hpa":  # pressure may be absent in a source
            filled_here |= mask

    grid["interpolated"] = filled_here | from_source
    grid["dew_point_c"] = dew_point_c(grid["temperature_c"], grid["humidity_pct"])
    return grid


def build_windows(grid, has_pressure, config):
    """Turn the grid of one station into one row per window."""
    step_minutes = config["grid_minutes"]
    window_steps = config["window_hours"] * 60 // step_minutes
    horizon_steps = config["horizon_hours"] * 60 // step_minutes

    columns = {}
    for feature in FEATURES:
        for lag in range(window_steps):
            columns[f"{feature}_lag{lag}"] = grid[feature].shift(lag)
    windows = pd.DataFrame(columns, index=grid.index)

    # Fraction of the window that was interpolated
    windows["interpolated_fraction"] = (
        grid["interpolated"].astype(float).rolling(window_steps).mean())

    # Minimum temperature of the NEXT horizon_steps steps (the present step is
    # excluded). Reversing the series turns "next" into "previous".
    reversed_temperature = grid["temperature_c"][::-1]
    future_min = reversed_temperature.rolling(horizon_steps, min_periods=horizon_steps).min()
    windows["future_min_temperature_c"] = future_min[::-1].shift(-1)

    # Hour of the day as a point on a circle, so 23:30 is close to 00:00
    hour = windows.index.hour + windows.index.minute / 60.0
    windows["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    windows["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

    # Keep only complete windows: every input present and a full future
    required = [c for c in windows.columns
                if has_pressure or not c.startswith("pressure_hpa")]
    windows = windows.dropna(subset=required)
    return windows


def count_cold_events(grid, threshold):
    """Number of separate episodes with temperature at or below the threshold."""
    cold = (grid["temperature_c"] <= threshold).astype(int)
    starts = (cold.diff() == 1).sum() + int(cold.iloc[0] == 1)
    return int(starts)


def assign_splits(dates, config):
    """Assign every calendar day to train, val or test (fixed seed)."""
    split = config["split"]
    days = np.array(sorted(set(dates)))
    order = np.random.default_rng(split["seed"]).permutation(len(days))
    n_train = int(round(len(days) * split["train"]))
    n_val = int(round(len(days) * split["val"]))
    names = np.array(["test"] * len(days), dtype=object)
    names[order[:n_train]] = "train"
    names[order[n_train:n_train + n_val]] = "val"
    return dict(zip(days, names))


# --------------------------------------------------------------------- main

def check_labeling(config):
    """Stop with a clear message if the thresholds are missing or wrong."""
    labeling = config["labeling"]
    thresholds = labeling.get("thresholds_c") or []
    classes = labeling["num_classes"]
    if classes not in (2, 3):
        sys.exit("ERROR: labeling.num_classes must be 2 or 3.")
    if len(thresholds) != classes - 1:
        sys.exit(
            f"ERROR: labeling.thresholds_c must have {classes - 1} value(s) for "
            f"{classes} classes, but it has {len(thresholds)}.\n"
            "The frost-risk threshold is an agronomic decision. Write it in "
            "ml/config.yaml (labeling.thresholds_c) and run again.")
    if sorted(thresholds) != list(thresholds):
        sys.exit("ERROR: labeling.thresholds_c must be in increasing order.")
    return [float(t) for t in thresholds]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    thresholds = check_labeling(config)
    version = config["dataset_version"]
    output_dir = REPO_DIR / config["paths"]["output_dir"]
    output_file = output_dir / f"dataset_v{version}.csv"
    if output_file.exists():
        sys.exit(f"ERROR: {output_file} already exists. Dataset versions are "
                 "never overwritten: increase dataset_version in the config.")

    loaders = {"node": load_node, "ideam": load_ideam, "zenodo": load_zenodo}
    report = [f"Dataset v{version}",
              f"grid: {config['grid_minutes']} min, window: {config['window_hours']} h, "
              f"horizon: {config['horizon_hours']} h",
              f"classes: {config['labeling']['num_classes']}, thresholds (C): {thresholds}",
              ""]
    all_windows = []

    for source, loader in loaders.items():
        if not config["sources"].get(source, False):
            report.append(f"[{source}] disabled in the config")
            continue
        table = loader(config)
        if table is None:
            report.append(f"[{source}] no data found, skipped")
            continue
        has_pressure = table["pressure_hpa"].notna().any()

        steps_total = steps_with_data = steps_interpolated = cold_events = 0
        for station, station_table in table.groupby("station"):
            grid = to_grid(station_table, config)
            present = grid["temperature_c"].notna() & grid["humidity_pct"].notna()
            steps_total += len(grid)
            steps_with_data += int(present.sum())
            steps_interpolated += int((grid["interpolated"] & present).sum())
            cold_events += count_cold_events(grid, max(thresholds))

            windows = build_windows(grid, has_pressure, config)
            windows.insert(0, "station", station)
            windows.insert(0, "source", source)
            all_windows.append(windows)

        report += [
            f"[{source}] stations: {table['station'].nunique()}, "
            f"pressure available: {'yes' if has_pressure else 'no'}",
            f"[{source}] coverage: {steps_with_data} of {steps_total} grid steps "
            f"have temperature and humidity ({100 * steps_with_data / steps_total:.1f}%)",
            f"[{source}] interpolated: {steps_interpolated} of those steps "
            f"({100 * steps_interpolated / max(steps_with_data, 1):.1f}%)",
            f"[{source}] real cold events (separate episodes with temperature <= "
            f"{max(thresholds)} C): {cold_events}",
        ]

    if not all_windows:
        sys.exit("ERROR: no source produced data.")

    dataset = pd.concat(all_windows)
    dataset.index.name = "timestamp"
    dataset = dataset.reset_index()
    if dataset.empty:
        sys.exit("ERROR: no complete window could be built from the data.")

    # Label = how many thresholds the future minimum is at or below
    future_min = dataset["future_min_temperature_c"].to_numpy()
    dataset["label"] = sum((future_min <= t).astype(int) for t in thresholds)

    dataset["date"] = dataset["timestamp"].dt.date
    split_of_day = assign_splits(dataset["date"], config)
    dataset["split"] = dataset["date"].map(split_of_day)

    first = ["source", "station", "timestamp", "date", "split", "label",
             "future_min_temperature_c", "interpolated_fraction",
             "hour_sin", "hour_cos"]
    dataset = dataset[first + [c for c in dataset.columns if c not in first]]

    # ---- report ----
    report += ["", f"windows: {len(dataset)}",
               "", "windows per split, source and class:"]
    balance = (dataset.groupby(["split", "source", "label"]).size()
               .unstack("label", fill_value=0))
    report.append(balance.to_string())
    report += ["", "days per split:"]
    report.append(dataset.groupby("split")["date"].nunique().to_string())

    # Positive days in train: distinct days with at least one risk window
    train_positive = dataset[(dataset["split"] == "train") & (dataset["label"] > 0)]
    positive_days_train = train_positive.groupby("station")["date"].nunique().sum()
    report += ["", f"risk windows in train: {len(train_positive)}",
               f"station-days with risk in train: {positive_days_train}"]

    minimum = config["min_positive_events_train"]
    if positive_days_train < minimum:
        report += [
            "",
            "*" * 70,
            f"WARNING: only {positive_days_train} station-days with risk in the "
            f"training split (minimum configured: {minimum}).",
            "This is too few positive examples to train or evaluate a model "
            "reliably. Capture more cold nights, add sources, or review the "
            "threshold.",
            "*" * 70,
        ]
    node_windows = int((dataset["source"] == "node").sum())
    if node_windows == 0:
        report += ["", "NOTE: the dataset has NO windows from the own node. "
                       "R4 requires the main dataset to be captured with the node."]

    # ---- save ----
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(output_file, index=False, float_format="%.3f")
    (output_dir / f"dataset_v{version}_report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8")
    shutil.copyfile(config_path, output_dir / f"dataset_v{version}_config.yaml")

    print("\n".join(report))
    print(f"\nsaved: {output_file}")


if __name__ == "__main__":
    main()
