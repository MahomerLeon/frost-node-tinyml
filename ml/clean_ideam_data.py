"""Build one clean hourly table from the three public IDEAM files.

Input  (never modified): data/raw/public/*_uptc_tunja.csv
Output (re-created on every run): data/processed/ideam_uptc_hourly.csv

Cleaning steps:
1. Keep only the timestamp and the observed value of each file.
2. Remove duplicated timestamps (the audit showed that duplicated rows always
   have the same value, so no information is lost).
3. Join the three variables by timestamp.
4. Keep only the hours that have the three variables.

No values are invented: gaps are NOT filled and nothing is interpolated.

Run from the repository root:
    py ml/clean_ideam_data.py
"""

from pathlib import Path

import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO_DIR / "data" / "raw" / "public"
OUTPUT_FILE = REPO_DIR / "data" / "processed" / "ideam_uptc_hourly.csv"

# Output column name -> input CSV file
FILES = {
    "temperature_c": "temperatura_uptc_tunja.csv",
    "humidity_pct": "humedad_uptc_tunja.csv",
    "pressure_hpa": "presion_uptc_tunja.csv",
}


def load_variable(column_name, file_name):
    """Return one variable as a Series indexed by timestamp, without duplicates."""
    df = pd.read_csv(
        INPUT_DIR / file_name,
        usecols=["fechaobservacion", "valorobservado"],
        parse_dates=["fechaobservacion"],
    )
    rows_before = len(df)

    # Safety check: stop if two rows of the same hour have different values.
    values_per_time = df.groupby("fechaobservacion")["valorobservado"].nunique()
    if (values_per_time > 1).any():
        raise ValueError(f"{file_name}: duplicated timestamps with different "
                         "values; decide how to resolve them before cleaning.")

    df = df.drop_duplicates("fechaobservacion")
    print(f"{column_name}: {rows_before} rows read, "
          f"{rows_before - len(df)} duplicates removed, {len(df)} kept")

    series = df.set_index("fechaobservacion")["valorobservado"]
    return series.rename(column_name)


def main():
    variables = [load_variable(name, file) for name, file in FILES.items()]

    # Outer join: one row per hour that appears in at least one file
    table = pd.concat(variables, axis=1, sort=True)
    hours_any = len(table)

    # Keep only the hours where the three variables are present
    table = table.dropna()
    print(f"hours with at least one variable: {hours_any}")
    print(f"hours dropped (some variable missing): {hours_any - len(table)}")
    print(f"hours kept (all three variables): {len(table)}")

    table.index.name = "timestamp"
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT_FILE)
    print(f"saved: {OUTPUT_FILE}")
    print(f"period: {table.index.min()} to {table.index.max()}")


if __name__ == "__main__":
    main()
