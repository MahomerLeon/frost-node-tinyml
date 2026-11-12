"""Helpers shared by train.py and convert_tflite.py."""

from pathlib import Path

import pandas as pd
import yaml

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"


def load_config(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def models_dir(config):
    folder = REPO_DIR / config["paths"]["models_dir"]
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_dataset(config):
    """Read dataset_vN.csv and keep only the sources chosen for training."""
    version = config["dataset_version"]
    file = REPO_DIR / config["paths"]["output_dir"] / f"dataset_v{version}.csv"
    if not file.exists():
        raise SystemExit(f"ERROR: {file} not found. Run ml/prepare_dataset.py first.")
    dataset = pd.read_csv(file)
    dataset = dataset[dataset["source"].isin(config["training"]["sources"])]
    if dataset.empty:
        raise SystemExit("ERROR: the dataset has no rows for the chosen sources.")
    return dataset


def feature_columns(dataset):
    """Names of the model inputs, in the order the firmware must use.

    Order: for each variable, oldest reading first (highest lag) to newest
    (lag0); then hour_sin and hour_cos.
    Pressure is used only if every selected row has it (the Zenodo source has
    no pressure, so including it removes pressure from the model).
    """
    variables = ["temperature_c", "humidity_pct", "dew_point_c"]
    pressure = [c for c in dataset.columns if c.startswith("pressure_hpa_lag")]
    if pressure and dataset[pressure].notna().all().all():
        variables.insert(2, "pressure_hpa")

    lags = sorted(int(c.rsplit("lag", 1)[1]) for c in dataset.columns
                  if c.startswith("temperature_c_lag"))
    columns = []
    for variable in variables:
        for lag in reversed(lags):
            columns.append(f"{variable}_lag{lag}")
    return columns + ["hour_sin", "hour_cos"]
