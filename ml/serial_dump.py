"""Download the CSV log stored in the node and set its clock.

What it does:
1. Opens the serial port of the node.
2. Sends "SETTIME <epoch>" with the current time of the PC.
3. Sends "DUMP" and saves the rows to data/raw/node/node_log_<date>_<time>.csv

It never deletes anything in the node. To empty the node after checking the
saved file, send the CLEAR command yourself from a serial monitor.

Run from the repository root (replace COM9 with the port of your board):
    python ml/serial_dump.py COM9
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import serial  # package "pyserial"

BAUD_RATE = 115200  # must match SERIAL_BAUD_RATE in firmware/logger/config.h
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "node"

BOOT_WAIT_SECONDS = 4      # opening the port may reset the board
REPLY_TIMEOUT_SECONDS = 5  # time to wait for the answer to SETTIME
DUMP_TIMEOUT_SECONDS = 120  # maximum time for the whole DUMP


def read_line(node):
    """Read one line of text from the node ('' if nothing arrived)."""
    return node.readline().decode("utf-8", errors="replace").strip()


def set_node_clock(node):
    """Send the PC time to the node and show its answer."""
    epoch = int(time.time())  # seconds since 1970-01-01 UTC
    node.write(f"SETTIME {epoch}\n".encode())
    deadline = time.time() + REPLY_TIMEOUT_SECONDS
    while time.time() < deadline:
        line = read_line(node)
        if line.startswith("# SETTIME done"):
            print(line)
            return True
    print("WARNING: the node did not confirm SETTIME.")
    return False


def download_rows(node):
    """Send DUMP and return the CSV lines, or None if the dump is incomplete."""
    node.write(b"DUMP\n")
    rows = []
    inside_dump = False
    deadline = time.time() + DUMP_TIMEOUT_SECONDS
    while time.time() < deadline:
        line = read_line(node)
        if line == "# DUMP BEGIN":
            inside_dump = True
        elif line == "# DUMP END":
            return rows
        elif inside_dump and line and not line.startswith("#"):
            rows.append(line)
    return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python ml/serial_dump.py <serial port>")
        print("Example: python ml/serial_dump.py COM9")
        sys.exit(1)
    port = sys.argv[1]

    with serial.Serial(port, BAUD_RATE, timeout=1) as node:
        print(f"Connected to {port}. Waiting for the node to be ready...")
        time.sleep(BOOT_WAIT_SECONDS)
        node.reset_input_buffer()  # discard the boot messages

        set_node_clock(node)
        rows = download_rows(node)

    if rows is None:
        print("ERROR: the dump did not finish. Nothing was saved.")
        sys.exit(1)

    data_rows = len(rows) - 1 if rows else 0  # the first line is the header
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"node_log_{stamp}.csv"
    output_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Saved {data_rows} data rows to {output_file}")


if __name__ == "__main__":
    main()
