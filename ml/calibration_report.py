"""Compare the BME280 temperature with the reference probe (DS18B20).

The calibration step of the capture protocol (docs/capture_protocol.md):
the BME280 and the reference probe measure next to each other for a while,
and the difference between them (the "offset") is written down.

Run from the repository root:
    python ml/calibration_report.py                     # every node log
    python ml/calibration_report.py data/raw/node/node_log_20261117_120000.csv
    python ml/calibration_report.py --start "2026-11-17 10:00" --end "2026-11-17 14:00"

--start and --end keep only the readings of one period, for example the
night hours. Times are local time.

The script only reads and reports. It does not correct any file: whether a
correction is applied, and how, is a decision to write in the protocol.
"""

import argparse
from pathlib import Path

import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
NODE_DIR = REPO_DIR / "data" / "raw" / "node"


def load_pairs(files):
    """Readings that have both a valid BME280 value and a probe value."""
    tables = [pd.read_csv(f) for f in files]
    table = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    if "reference_temperature_c" not in table.columns:
        return pd.DataFrame(columns=["time", "temperature_c", "reference_temperature_c"])
    table = table[table["status"] == "ok"].copy()
    table["reference_temperature_c"] = pd.to_numeric(
        table["reference_temperature_c"], errors="coerce")  # "nan" text -> NaN
    table = table.dropna(subset=["temperature_c", "reference_temperature_c"])
    # "2026-11-17T09:07:17-05:00" -> local wall-clock time
    table["time"] = pd.to_datetime(table["timestamp_iso"].str.slice(0, 19))
    table = table.drop_duplicates("time").sort_values("time")
    return table[["time", "temperature_c", "reference_temperature_c"]]


def offset_summary(pairs):
    """Offset = BME280 minus probe. Positive means the BME280 reads higher."""
    offset = pairs["temperature_c"] - pairs["reference_temperature_c"]
    return {
        "readings": int(len(offset)),
        "first": pairs["time"].min(),
        "last": pairs["time"].max(),
        "mean_offset_c": float(offset.mean()),
        "std_offset_c": float(offset.std()),
        "min_offset_c": float(offset.min()),
        "max_offset_c": float(offset.max()),
        "reference_range_c": (float(pairs["reference_temperature_c"].min()),
                              float(pairs["reference_temperature_c"].max())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("files", nargs="*", help="node log files (default: all)")
    parser.add_argument("--start", help='first local time, e.g. "2026-11-17 10:00"')
    parser.add_argument("--end", help="last local time")
    args = parser.parse_args()

    files = [Path(f) for f in args.files] or sorted(NODE_DIR.glob("*.csv"))
    pairs = load_pairs(files)
    if args.start:
        pairs = pairs[pairs["time"] >= pd.Timestamp(args.start)]
    if args.end:
        pairs = pairs[pairs["time"] <= pd.Timestamp(args.end)]

    print(f"files read: {len(files)}")
    if len(pairs) < 2:
        print("Not enough readings with both the BME280 and the probe.")
        print("Check that the probe is connected (command TEST on the node).")
        return

    s = offset_summary(pairs)
    print(f"readings with both sensors: {s['readings']} ({s['first']} to {s['last']})")
    print(f"probe temperature range: {s['reference_range_c'][0]:.2f} "
          f"to {s['reference_range_c'][1]:.2f} C")
    print(f"offset (BME280 - probe): mean {s['mean_offset_c']:+.2f} C, "
          f"std {s['std_offset_c']:.2f} C, "
          f"min {s['min_offset_c']:+.2f} C, max {s['max_offset_c']:+.2f} C")
    print("Write these numbers in the calibration section of docs/capture_protocol.md.")


if __name__ == "__main__":
    main()
