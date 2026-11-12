"""Audit the public IDEAM files of the UPTC Tunja station.

The script only READS the CSV files in data/raw/public and prints a report.
It does not change or delete any data.

Run from the repository root:
    py ml/audit_ideam_data.py
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "public"

# Variable name -> CSV file
FILES = {
    "temperature": "temperatura_uptc_tunja.csv",
    "humidity": "humedad_uptc_tunja.csv",
    "pressure": "presion_uptc_tunja.csv",
}

# Columns that describe the station/sensor (they should be constant)
METADATA_COLUMNS = ["codigosensor", "nombreestacion", "municipio", "latitud",
                    "longitud", "descripcionsensor", "unidadmedida"]

ONE_HOUR = pd.Timedelta(hours=1)


def load(file_name):
    """Read one CSV, keeping the codes as text and parsing the timestamp."""
    return pd.read_csv(
        DATA_DIR / file_name,
        dtype={"codigoestacion": str, "codigosensor": str},
        parse_dates=["fechaobservacion"],
    )


def title(text):
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)


def audit_time(df):
    """Check duplicates, coverage and gaps of the timestamps."""
    time = df["fechaobservacion"]
    first, last = time.min(), time.max()
    print(f"rows: {len(df)}")
    print(f"first timestamp: {first}")
    print(f"last timestamp:  {last}")

    not_on_the_hour = (time != time.dt.floor("h")).sum()
    print(f"timestamps not exactly on the hour: {not_on_the_hour}")

    duplicated = time.duplicated().sum()
    # Duplicated timestamps whose values disagree with each other
    values_per_time = df.groupby("fechaobservacion")["valorobservado"].nunique()
    conflicting = (values_per_time > 1).sum()
    print(f"duplicated timestamps: {duplicated} "
          f"(timestamps with conflicting values: {conflicting})")

    unique_times = pd.DatetimeIndex(time.drop_duplicates().sort_values())
    expected = pd.date_range(first.floor("h"), last.floor("h"), freq="h")
    present = len(unique_times.floor("h").unique())
    print(f"expected hours in the period: {len(expected)}")
    print(f"hours with data: {present} "
          f"({100 * present / len(expected):.1f}% coverage)")

    # A gap is a jump of more than one hour between consecutive timestamps
    steps = pd.Series(unique_times[1:] - unique_times[:-1],
                      index=unique_times[:-1])
    gaps = steps[steps > ONE_HOUR]
    print(f"gaps (jump > 1 h): {len(gaps)}")
    print("longest gaps:")
    for start, length in gaps.sort_values(ascending=False).head(5).items():
        print(f"  from {start} to {start + length}  ({length})")

    print("coverage by year (hours with data / hours in the audited period):")
    hours = pd.Series(1, index=unique_times.floor("h").unique())
    for year, count in hours.groupby(hours.index.year).sum().items():
        expected_in_year = (expected.year == year).sum()
        print(f"  {year}: {count:5d} / {expected_in_year:5d} "
              f"({100 * count / expected_in_year:5.1f}%)")


def audit_values(df):
    """Show the range of the observed values."""
    values = df["valorobservado"]
    print(f"missing values: {values.isna().sum()}")
    print(values.describe(percentiles=[0.01, 0.5, 0.99]).round(2).to_string())
    # The sensor description changes over time. If the values look the same
    # under each description, the change is probably only in the label.
    print("values grouped by sensor description:")
    by_description = df.groupby("descripcionsensor")["valorobservado"]
    print(by_description.describe().round(2).to_string())


def audit_metadata(df):
    """Show every distinct value of the metadata columns and when it appears."""
    for column in METADATA_COLUMNS:
        summary = df.groupby(column, dropna=False)["fechaobservacion"].agg(
            rows="count", first="min", last="max")
        if len(summary) == 1:
            print(f"{column}: constant = {summary.index[0]}")
        else:
            print(f"{column}: {len(summary)} different values")
            print(summary.to_string())


def audit_combined(tables):
    """Check how many hours have the three variables at the same time."""
    title("COMBINED (temperature + humidity + pressure)")
    series = {}
    for name, df in tables.items():
        clean = df.drop_duplicates("fechaobservacion")
        series[name] = clean.set_index("fechaobservacion")["valorobservado"]
    joined = pd.concat(series, axis=1, sort=True)
    complete = joined.dropna()
    print(f"hours with at least one variable: {len(joined)}")
    print(f"hours with all three variables:   {len(complete)}")
    print(f"first complete hour: {complete.index.min()}")
    print(f"last complete hour:  {complete.index.max()}")


def audit_temperature_cycle(df):
    """Describe the daily temperature cycle.

    The hour with the lowest mean temperature helps to tell whether the
    timestamps are in local time or in UTC (Colombia is UTC-5 and the coldest
    moment of the day is normally around sunrise).
    """
    title("TEMPERATURE: daily cycle and daily minimum")
    clean = df.drop_duplicates("fechaobservacion")
    temperature = clean.set_index("fechaobservacion")["valorobservado"]

    by_hour = temperature.groupby(temperature.index.hour).mean().round(2)
    print("mean temperature by hour of day (as written in the file):")
    print(by_hour.to_string())
    print(f"coldest hour on average: {by_hour.idxmin()}h, "
          f"warmest hour on average: {by_hour.idxmax()}h")

    # Daily minimum, using the dates exactly as written in the file
    daily_min = temperature.groupby(temperature.index.date).min()
    print()
    print(f"days with at least one reading: {len(daily_min)}")
    print("daily minimum temperature (C):")
    print(daily_min.describe(percentiles=[0.01, 0.05, 0.5]).round(2).to_string())
    # 0 C is the physical freezing point of water. It is reported only as a
    # description of the data; it is NOT the agronomic threshold of the project.
    print(f"days with a reading at or below 0 C: {(daily_min <= 0).sum()}")
    print("ten coldest days:")
    print(daily_min.sort_values().head(10).to_string())


def main():
    tables = {}
    for name, file_name in FILES.items():
        df = load(file_name)
        tables[name] = df
        title(f"{name.upper()}  ({file_name})")
        audit_time(df)
        print()
        audit_values(df)
        print()
        audit_metadata(df)

    audit_combined(tables)
    audit_temperature_cycle(tables["temperature"])


if __name__ == "__main__":
    main()
