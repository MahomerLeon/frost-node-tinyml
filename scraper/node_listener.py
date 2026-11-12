"""Save the predictions of the node (firmware/inference) to CSV files.

The node prints two kinds of lines on the serial port:
    STEP,<time>,<temperature>,<humidity>,<pressure>,<ok|no_data>
    PREDICTION,<time>,class=<c>,p0=<p>,p1=<p>[,p2=<p>]
This script sets the clock of the node, then appends every STEP line to
data/raw/node_live/readings.csv and every PREDICTION line to
data/raw/node_live/predictions.csv, which the dashboard reads.

Run from the repository root (replace COM9 with the port of your board):
    python scraper/node_listener.py COM9
Stop with Ctrl+C.
"""

import argparse
import csv
import time
from pathlib import Path

import serial  # package "pyserial"

from forecast_scraper import DEFAULT_CONFIG, REPO_DIR, load_config

BAUD_RATE = 115200
BOOT_WAIT_SECONDS = 4

READING_COLUMNS = ["timestamp", "temperature_c", "humidity_pct", "pressure_hpa"]
PREDICTION_COLUMNS = ["timestamp", "predicted_class", "probabilities"]


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
        return "reading", parts[1:5]
    if parts[0] == "PREDICTION" and len(parts) >= 4 and parts[2].startswith("class="):
        predicted_class = parts[2].split("=")[1]
        # "p0=0.980,p1=0.020" -> "0.980;0.020"
        probabilities = ";".join(p.split("=")[1] for p in parts[3:])
        return "prediction", [parts[1], predicted_class, probabilities]
    return None


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
        node.write(f"SETTIME {int(time.time())}\n".encode())
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
