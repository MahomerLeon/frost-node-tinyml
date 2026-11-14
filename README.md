# Low-cost TinyML frost-risk node (Pirgua, Tunja)

Integrative project, 2nd semester, Data and AI Engineering,
Universidad Santo Tomás (Tunja, Colombia).

Official title (Spanish): *"Nodo TinyML de bajo costo para la clasificación
local del riesgo de helada y la validación de pronósticos en la vereda Pirgua,
Tunja"*.

## Description

- An **ESP32-S3 DevKitC-1** reads temperature, humidity and pressure from a
  **BME280** sensor and classifies the frost risk **on the device** with a
  TensorFlow Lite int8 model (TFLite Micro).
- An **INA219** measures the power consumption of the node.
- A **Python module** periodically scrapes a weather forecast and shows it in a
  dashboard next to the prediction of the node, to validate one against the
  other.

## Hardware

| Part | Connection |
|---|---|
| ESP32-S3 DevKitC-1 | main board |
| BME280 | I2C address 0x76, SDA = GPIO8, SCL = GPIO9 |
| INA219 | I2C address 0x40 (same bus) |
| DS18B20 (optional) | data on GPIO4, 4.7 kOhm pull-up to 3V3 |

Wiring diagram: [docs/wiring_diagram_esp32s3.png](docs/wiring_diagram_esp32s3.png)
(the labels inside the image are in Spanish).

## Repository layout

```
firmware/logger/       Arduino sketch that logs sensor data (own dataset)
firmware/inference/    Arduino sketch that runs the TFLite model on the node
firmware/i2c_scan/     Wiring diagnostic (lists the I2C devices on the bus)
data/raw/              Raw data: node captures and public support data
data/processed/        Clean tables and dataset versions (v1, v2, ...)
ml/                    Data preparation, training, int8 conversion
scraper/               Forecast scraping, hash table, dashboard
docs/                  Capture protocol, resource measurements, diagrams
tests/                 Automated tests (no board or sensors needed)
ml/config.yaml         All parameters, including the frost-risk threshold
requirements.txt       Python dependencies (requirements.lock.txt: exact versions)
```

## Course requirements

| Req. | What it asks | Folder | Status |
|---|---|---|---|
| R2 | Inference runs on the ESP32-S3, not in the cloud or on the PC | `firmware/inference/` | Code written; verified on the board with a placeholder model. Pending: real model |
| R3 | Light TFLite model with int8 quantization; F1 loss vs. the float model documented | `ml/`, `docs/` | Code written and run as a pipeline test. Pending: real dataset, real F1 comparison |
| R4 | Own dataset captured with the node, documented protocol, versions (v1, v2...), train/val/test split by days without leakage | `firmware/logger/`, `data/raw/`, `data/processed/`, `docs/` | Logger, preparation script and draft protocol written; split tested. Pending: capture (no data yet) |
| R5 | Periodic scraping used to validate the local prediction against the forecast | `scraper/` | Scraper and dashboard working with the real page. Pending: comparison with real node predictions |
| R6 | Two data structures justified with Big-O: circular buffer on the edge, hash table in the scraper/dashboard | `firmware/inference/`, `scraper/`, `docs/` | Both implemented, tested and documented |
| R7 | Flash, RAM (tensor arena), latency (mean and std over >= 100 runs), CPU load and power, as % of the total available | `firmware/inference/`, `docs/` | Benchmark written; Flash, RAM and latency verified with a placeholder model. Pending: power (INA219, not run yet), real model, Pico comparison |

No requirement is complete yet. What blocks them:

- **Sensors:** the BME280 has not answered on the I2C bus yet, so there is no
  reading from the node and no own data.
- **Frost-risk threshold:** not decided, so no real dataset or model exists.
  Everything in `ml/` and `firmware/inference` was checked with a placeholder
  threshold in a temporary folder; those numbers are not results.
- **Not run on the board yet:** flash storage of predictions, `WINDOW`
  validation, stack and power measurement in `firmware/inference`.
- **Not written:** firmware for the Raspberry Pi Pico and reading of the
  DS18B20 probe.
## Open decisions

- **Frost-risk threshold:** not decided. It is the parameter
  `labeling.thresholds_c` in `ml/config.yaml`, intentionally empty;
  `ml/prepare_dataset.py` stops until it is filled in. No script may
  hard-code a threshold.
- Capture protocol (sampling interval, duration, how the node keeps time in
  the field).

## How to reproduce

Tools used so far: Windows 11, Python 3.13.17 with TensorFlow 2.21.0,
`arduino-cli` 1.5.1, Arduino-ESP32 core 3.3.12. Firmware library versions are
listed in [firmware/README.md](firmware/README.md).

1. Create a Python 3.13 virtual environment **outside OneDrive** (TensorFlow
   has thousands of files that should not be synced) and install the
   dependencies. On Windows PowerShell:

   ```
   py install 3.13
   py -V:3.13 -m venv $env:USERPROFILE\venvs\frost-node
   & $env:USERPROFILE\venvs\frost-node\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

   Activate the environment (third line) in every new terminal. After that,
   `python` is the Python of the environment.

2. Capture data with the node and download it: see
   [firmware/README.md](firmware/README.md).

3. Decide the frost-risk threshold and write it in `ml/config.yaml`.

4. Build the dataset, train, convert and validate: see
   [ml/README.md](ml/README.md).

5. Run the scraper, the node listener and the dashboard: see
   [scraper/README.md](scraper/README.md).

To check the code without the board, run the automated tests: see
[tests/README.md](tests/README.md).
