"""Compare the model running on the ESP32-S3 with the int8 model on the PC.

It sends the test vectors exported by ml/convert_tflite.py to the node (which
must be running firmware/inference) with the VECTOR command, and checks that
the raw int8 output of the node is identical to the output computed on the PC.

Run from the repository root (replace COM9 with the port of your board):
    python ml/validate_on_device.py COM9
    python ml/validate_on_device.py COM9 --config path/to/other_config.yaml
"""

import argparse
import time

import numpy as np
import pandas as pd
import serial  # package "pyserial"

from dataset_utils import DEFAULT_CONFIG, load_config, models_dir

BAUD_RATE = 115200
BOOT_WAIT_SECONDS = 4
REPLY_TIMEOUT_SECONDS = 5


def ask(node, command):
    """Send a VECTOR command and return the int8 values of the RESULT line."""
    node.write((command + "\n").encode())
    deadline = time.time() + REPLY_TIMEOUT_SECONDS
    while time.time() < deadline:
        line = node.readline().decode("utf-8", errors="replace").strip()
        if line.startswith("RESULT "):
            return [int(v) for v in line[7:].split(",")]
        if line.startswith("# ERROR") or "skipped" in line:
            print(line)
            return None
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("port")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(args.config)

    file = models_dir(config) / f"test_vectors_v{config['dataset_version']}.csv"
    vectors = pd.read_csv(file)
    input_columns = [c for c in vectors.columns if c.startswith("in_")]
    output_columns = [c for c in vectors.columns if c.startswith("out_")]

    identical = same_class = answered = 0
    largest_difference = 0
    with serial.Serial(args.port, BAUD_RATE, timeout=1) as node:
        print(f"Connected to {args.port}. Waiting for the node to be ready...")
        time.sleep(BOOT_WAIT_SECONDS)
        node.reset_input_buffer()

        for _, row in vectors.iterrows():
            command = "VECTOR " + ",".join(str(int(v)) for v in row[input_columns])
            device = ask(node, command)
            if device is None:
                continue
            answered += 1
            pc = [int(v) for v in row[output_columns]]
            difference = int(np.max(np.abs(np.array(device) - np.array(pc))))
            largest_difference = max(largest_difference, difference)
            identical += int(difference == 0)
            same_class += int(int(np.argmax(device)) == int(np.argmax(pc)))

    total = len(vectors)
    print(f"test vectors sent: {total}, answered by the node: {answered}")
    print(f"identical int8 output (node == PC): {identical} of {answered}")
    print(f"same predicted class: {same_class} of {answered}")
    print(f"largest difference in any output value: {largest_difference}")
    if answered == total and identical == total:
        print("RESULT: the node reproduces the PC int8 model exactly.")
    else:
        print("RESULT: there are differences or missing answers. Check the output above.")


if __name__ == "__main__":
    main()
