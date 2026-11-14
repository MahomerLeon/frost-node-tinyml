"""Compare the model running on the ESP32-S3 with the int8 model on the PC.

The node must be running firmware/inference. Two checks are done:

1. MODEL check (VECTOR command). Sends already-quantized int8 inputs exported
   by ml/convert_tflite.py and checks that the raw int8 output of the node is
   identical to the PC output. This tests the model and the TFLite Micro
   library. It also reports F1 on the device for those vectors.

2. PREPROCESSING check (WINDOW command). Sends raw readings (temperature,
   humidity, pressure and the hour) of test windows; the node computes dew
   point, hour sine/cosine, standardization and quantization by itself. The
   PC does the same with the Python code and both outputs are compared.
   Small differences (1 or 2 units) can appear here because the node
   calculates with 32-bit floats and Python with 64-bit floats.

Run from the repository root (replace COM9 with the port of your board):
    python ml/validate_on_device.py COM9
    python ml/validate_on_device.py COM9 --config path/to/other_config.yaml
"""

import argparse
import json
import time

import numpy as np
import pandas as pd
import serial  # package "pyserial"
from sklearn.metrics import f1_score

from dataset_utils import DEFAULT_CONFIG, REPO_DIR, load_config, models_dir
from prepare_dataset import dew_point_c

BAUD_RATE = 115200
BOOT_WAIT_SECONDS = 4
REPLY_TIMEOUT_SECONDS = 5
WINDOWS_TO_TEST = 50
ROWS_TO_SCAN = 50000  # rows of the dataset read to find test windows


def ask(node, command):
    """Send a command and return the int8 values of the RESULT line."""
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


def summarize(name, device_outputs, pc_outputs):
    """Print how close the node outputs are to the PC outputs."""
    answered = [(d, p) for d, p in zip(device_outputs, pc_outputs) if d is not None]
    differences = [int(np.max(np.abs(np.array(d) - np.array(p)))) for d, p in answered]
    same_class = sum(int(np.argmax(d)) == int(np.argmax(p)) for d, p in answered)
    print(f"\n--- {name} ---")
    print(f"sent: {len(pc_outputs)}, answered by the node: {len(answered)}")
    print(f"identical int8 output (node == PC): "
          f"{sum(d == 0 for d in differences)} of {len(answered)}")
    print(f"same predicted class: {same_class} of {len(answered)}")
    print(f"largest difference in any output value: {max(differences, default=0)}")


def check_model(node, config):
    """Check 1: quantized vectors in, raw output compared exactly."""
    file = models_dir(config) / f"test_vectors_v{config['dataset_version']}.csv"
    vectors = pd.read_csv(file)
    input_columns = [c for c in vectors.columns if c.startswith("in_")]
    output_columns = [c for c in vectors.columns if c.startswith("out_")]

    device, pc = [], []
    for _, row in vectors.iterrows():
        command = "VECTOR " + ",".join(str(int(v)) for v in row[input_columns])
        device.append(ask(node, command))
        pc.append([int(v) for v in row[output_columns]])
    summarize("1. model check (VECTOR)", device, pc)

    answered = [i for i, d in enumerate(device) if d is not None]
    if answered:
        labels = vectors["label"].to_numpy()[answered]
        predicted = [int(np.argmax(device[i])) for i in answered]
        f1 = f1_score(labels, predicted, average="macro", zero_division=0)
        print(f"F1 macro ON THE DEVICE for these {len(answered)} test vectors: {f1:.4f}")
        print("(small sample: the F1 of the whole test split is in metrics_vN_int8.json)")


def check_preprocessing(node, config):
    """Check 2: raw readings in, the node does the whole preprocessing."""
    import tensorflow as tf  # imported here because it is slow to load

    version = config["dataset_version"]
    folder = models_dir(config)
    preprocessing = json.loads(
        (folder / f"model_v{version}_preprocessing.json").read_text(encoding="utf-8"))
    columns = preprocessing["feature_columns"]
    mean, std = np.array(preprocessing["mean"]), np.array(preprocessing["std"])
    uses_pressure = any("pressure" in c for c in columns)
    steps = config["window_hours"] * 60 // config["grid_minutes"]

    dataset_file = REPO_DIR / config["paths"]["output_dir"] / f"dataset_v{version}.csv"
    rows = pd.read_csv(dataset_file, nrows=ROWS_TO_SCAN, parse_dates=["timestamp"])
    rows = rows[(rows["split"] == "test")
                & rows["source"].isin(config["training"]["sources"])]
    rows = rows.sample(min(WINDOWS_TO_TEST, len(rows)),
                       random_state=config["training"]["seed"])
    if rows.empty:
        print("\nNo test windows found for the preprocessing check.")
        return

    interpreter = tf.lite.Interpreter(model_path=str(folder / f"model_v{version}.tflite"))
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()[0]
    output_index = interpreter.get_output_details()[0]["index"]
    scale, zero_point = input_details["quantization"]

    device, pc = [], []
    for _, row in rows.iterrows():
        lags = range(steps - 1, -1, -1)  # oldest first
        temperature = np.array([row[f"temperature_c_lag{k}"] for k in lags])
        humidity = np.array([row[f"humidity_pct_lag{k}"] for k in lags])
        pressure = (np.array([row[f"pressure_hpa_lag{k}"] for k in lags])
                    if uses_pressure else np.zeros(steps))
        hour = row["timestamp"].hour + row["timestamp"].minute / 60.0

        # PC side: the same steps as ml/prepare_dataset.py and ml/train.py
        features = list(temperature) + list(humidity)
        if uses_pressure:
            features += list(pressure)
        features += list(dew_point_c(temperature, humidity))
        features += [np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)]
        standardized = (np.array(features) - mean) / std
        quantized = np.clip(np.round(standardized / scale + zero_point),
                            -128, 127).astype(np.int8)
        interpreter.set_tensor(input_details["index"], quantized[np.newaxis, :])
        interpreter.invoke()
        pc.append([int(v) for v in interpreter.get_tensor(output_index)[0]])

        # Node side: only raw readings are sent
        readings = ";".join(f"{t:.3f},{h:.3f},{p:.3f}"
                            for t, h, p in zip(temperature, humidity, pressure))
        device.append(ask(node, f"WINDOW {hour:.4f} {readings}"))
    summarize("2. preprocessing check (WINDOW)", device, pc)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("port")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(args.config)

    with serial.Serial(args.port, BAUD_RATE, timeout=1) as node:
        print(f"Connected to {args.port}. Waiting for the node to be ready...")
        time.sleep(BOOT_WAIT_SECONDS)
        node.reset_input_buffer()
        check_model(node, config)
        check_preprocessing(node, config)


if __name__ == "__main__":
    main()
