"""Save what the node prints on the serial port to CSV files, for the dashboard.

It understands the two firmwares of the node:

- firmware/logger prints one row per reading:
    <time>,<temperature>,<humidity>,<pressure>,<reference temperature>,<ok|sensor_error>
- firmware/inference prints
    STEP,<time>,<temperature>,<humidity>,<pressure>,<ok|no_data>
    PREDICTION,<time>,class=<c>,p0=<p>,p1=<p>[,p2=<p>]

This script sets the clock of the node, then appends every reading to
data/raw/node_live/readings.csv and every PREDICTION line to
data/raw/node_live/predictions.csv, which the dashboard reads. With the logger
there are readings (and the probe temperature) but no predictions.

The inference firmware also keeps its predictions in its flash memory, so the
ones made while no PC was connected are not lost: when this script starts, it
asks for them (command DUMPPRED) and adds the ones that are not in the CSV
files yet. The logger does not have that command and the script skips it.

Run from the repository root (replace COM9 with the port of your board):
    python scraper/node_listener.py COM9
Stop with Ctrl+C.
"""

import argparse
import csv
import re
import time
from pathlib import Path

import serial  # package "pyserial"

from forecast_scraper import DEFAULT_CONFIG, REPO_DIR, load_config

BAUD_RATE = 115200
BOOT_WAIT_SECONDS = 4
DUMP_TIMEOUT_SECONDS = 60

READING_COLUMNS = ["timestamp", "temperature_c", "humidity_pct", "pressure_hpa",
                   "reference_temperature_c"]
PREDICTION_COLUMNS = ["timestamp", "predicted_class", "probabilities"]

# "2026-11-22T21:30:00-05:00": the first field of a row of the logger
LOGGER_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$")


def append_row(file, columns, row):
    """Append one row to a CSV file, writing the header if the file is new."""
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    is_new = not file.exists()
    with open(file, "a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if is_new:
            writer.writerow(columns)
        writer.writerow(row)


def parse_line(line):
    """Return ("reading" | "prediction", row) or None for any other line."""
    parts = line.split(",")
    if parts[0] == "STEP" and len(parts) == 6 and parts[5] == "ok":
        return "reading", parts[1:5] + [""]  # the inference firmware has no probe
    if len(parts) == 6 and LOGGER_TIME.match(parts[0]) and parts[5] == "ok":
        reference = "" if parts[4] == "nan" else parts[4]  # nan = probe not connected
        return "reading", parts[0:4] + [reference]
    if parts[0] == "PREDICTION" and len(parts) >= 4 and parts[2].startswith("class="):
        predicted_class = parts[2].split("=")[1]
        # "p0=0.980,p1=0.020" -> "0.980;0.020"
        probabilities = ";".join(p.split("=")[1] for p in parts[3:])
        return "prediction", [parts[1], predicted_class, probabilities]
    return None


def saved_timestamps(file):
    """Timestamps already present in a CSV file (empty set if it is missing)."""
    file = Path(file)
    if not file.exists():
        return set()
    with open(file, encoding="utf-8", newline="") as handle:
        return {row["timestamp"] for row in csv.DictReader(handle)}


def download_stored_predictions(node, files):
    """Ask the node for the predictions kept in its flash and save the new ones.

    Each stored row is:
    timestamp_iso,temperature_c,humidity_pct,pressure_hpa,predicted_class,probabilities
    """
    node.write(b"DUMPPRED\n")
    rows = []
    inside = False
    finished = False
    deadline = time.time() + DUMP_TIMEOUT_SECONDS
    while time.time() < deadline and not finished:
        line = node.readline().decode("utf-8", errors="replace").strip()
        if "unknown command: DUMPPRED" in line:
            print("This firmware does not store predictions (it is the logger): skipped.")
            return
        if line == "# DUMPPRED BEGIN":
            inside = True
        elif line == "# DUMPPRED END":
            finished = True
        elif inside and line and not line.startswith(("#", "timestamp_iso")):
            parts = line.split(",")
            if len(parts) == 6:
                rows.append(parts)
    if not finished:
        print("WARNING: the node did not answer DUMPPRED (older firmware?).")
        return

    known_predictions = saved_timestamps(files["prediction"][0])
    known_readings = saved_timestamps(files["reading"][0])
    added = 0
    for timestamp, temperature, humidity, pressure, predicted_class, probabilities in rows:
        if timestamp not in known_readings:
            append_row(*files["reading"], [timestamp, temperature, humidity, pressure, ""])
        if timestamp not in known_predictions:
            append_row(*files["prediction"], [timestamp, predicted_class, probabilities])
            added += 1
    print(f"Predictions stored in the node: {len(rows)}; new ones saved: {added}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("port")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    paths = load_config(args.config)["paths"]
    files = {"reading": (REPO_DIR / paths["node_readings"], READING_COLUMNS),
             "prediction": (REPO_DIR / paths["node_predictions"], PREDICTION_COLUMNS)}

    with serial.Serial(args.port, BAUD_RATE, timeout=1) as node:
        print(f"Connected to {args.port}. Waiting for the node to be ready...")
        time.sleep(BOOT_WAIT_SECONDS)
        node.reset_input_buffer()  # discard the boot messages
        node.write(f"SETTIME {int(time.time())}\n".encode())
        download_stored_predictions(node, files)
        # Ask for one reading right now (the logger has this command), so the
        # dashboard does not wait up to 5 minutes for the first one. The
        # inference firmware answers "unknown command", which is harmless.
        node.write(b"SAMPLE\n")
        print("Listening. Press Ctrl+C to stop.")
        try:
            while True:
                line = node.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                print(line)
                parsed = parse_line(line)
                if parsed:
                    kind, row = parsed
                    append_row(*files[kind], row)
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
