# Low-cost TinyML frost-risk node (Pirgua, Tunja)

Integrative project, 2nd semester, Data and AI Engineering,
Universidad Santo Tomás (Tunja, Colombia).

Official title (Spanish): *"Nodo TinyML de bajo costo para la clasificación
local del riesgo de helada y la validación de pronósticos en la vereda Pirgua,
Tunja"*.

Project proposal (IEEE format): [docs/IEEE_proposal_frost_node.pdf](docs/IEEE_proposal_frost_node.pdf).

## Description

- An **ESP32-S3 DevKitC-1** reads temperature, humidity and pressure from a
  **BME280** sensor and classifies the frost risk **on the device** with a
  TensorFlow Lite int8 model (TFLite Micro).
- An **INA219** measures the power consumption of the node.
- A **DS18B20** probe gives a reference temperature, used only to calibrate
  the BME280 (it is not a model input).
- A **Raspberry Pi Pico (RP2040)** runs the same model only to compare its
  resources with the ESP32-S3 (R7). It is not part of the field node.
- A **Python module** periodically scrapes a weather forecast and shows it in a
  dashboard next to the prediction of the node, to validate one against the
  other.

## Hardware

| Part | Connection |
|---|---|
| ESP32-S3 DevKitC-1 (ESP32-S3-N16R8: 16 MB flash, 8 MB PSRAM) | main board |
| BME280 | I2C address 0x76, SDA = GPIO8, SCL = GPIO9 |
| INA219 | I2C address 0x40 (same bus) |
| DS18B20 reference probe | 1-Wire data on GPIO4, 4.7 kOhm pull-up to 3V3; logged as `reference_temperature_c` |
| Raspberry Pi Pico (RP2040) | R7 comparison only. Its benchmark needs no sensor, so it can be connected to the PC at the same time as the ESP32-S3; the INA219 is moved to it only to measure its power (SDA = GP4, SCL = GP5) |

Wiring diagrams:

- [Complete current setup](docs/wiring_diagram_both.png): ESP32-S3 with BME280,
  INA219 and DS18B20, and the Pico alone, both connected to the PC.
- [Node with the ESP32-S3](docs/wiring_diagram_esp32s3.png) (labels in Spanish),
  including the 5 V path of the INA219 to measure power.
- [Raspberry Pi Pico](docs/wiring_diagram_pico.png) with the sensors moved to it.

Step-by-step guide: [docs/hardware_setup.md](docs/hardware_setup.md). On the
ESP32-S3 board the numbers printed next to the pins are GPIO names, not
positions: GPIO8 (SDA) is the 12th pin and GPIO9 (SCL) the 15th of the left row.

## Repository layout

```
firmware/logger/       Arduino sketch that logs sensor data (own dataset)
firmware/inference/    Arduino sketch that runs the TFLite model on the node
firmware/i2c_scan/     Wiring check (lists the I2C devices and the 1-Wire probe)
firmware/pico_benchmark/  Same model and benchmark on the Raspberry Pi Pico (R7)
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
| R4 | Own dataset captured with the node, documented protocol, versions (v1, v2...), train/val/test split by days without leakage | `firmware/logger/`, `data/raw/`, `data/processed/`, `docs/` | Logger, preparation script and draft protocol written; split tested; real BME280 readings verified on the board. Pending: capture in Pirgua (no data yet) |
| R5 | Periodic scraping used to validate the local prediction against the forecast | `scraper/` | Scraper and dashboard working with the real page. Pending: comparison with real node predictions |
| R6 | Two data structures justified with Big-O: circular buffer on the edge, hash table in the scraper/dashboard | `firmware/inference/`, `scraper/`, `docs/` | Both implemented, tested and documented |
| R7 | Flash, RAM (tensor arena), latency (mean and std over >= 100 runs), CPU load and power, as % of the total available | `firmware/inference/`, `firmware/pico_benchmark/`, `docs/` | Benchmark verified on the ESP32-S3 and the Raspberry Pi Pico with a placeholder model (see `docs/resource_report.md`). Pending: power (INA219), real model |

No requirement is complete yet. What blocks them:

- **Capture:** the node already works outdoors without a PC (first night in
  Pirgua, 2026-11-20/21: 170 readings, no gaps), but that night the BME280
  was inside the electronics box, so it is kept as a test and not used. No
  valid field data yet; see `docs/capture_protocol.md`.
- **Frost-risk threshold:** not decided, so no real dataset or model exists.
  Everything in `ml/` and `firmware/inference` was checked with a placeholder
  threshold in a temporary folder; those numbers are not results.
- **Not run on the board yet:** a full 3 h window of real readings with a
  prediction, and the power measurement through the INA219 on either board.
- **Calibration:** the DS18B20 probe works on the board (checked on
  2026-11-20), but the calibration against the BME280 has not been done.

## Open decisions

- **Frost-risk threshold:** not decided. It is the parameter
  `labeling.thresholds_c` in `ml/config.yaml`, intentionally empty;
  `ml/prepare_dataset.py` stops until it is filled in. No script may
  hard-code a threshold.
- Capture protocol (sampling interval, duration, how the node keeps time in
  the field).

## How to reproduce

Tools used so far: Windows 11, Python 3.13.17 with TensorFlow 2.21.0,
`arduino-cli` 1.5.1, Arduino-ESP32 core 3.3.12, Raspberry Pi Pico core
(`rp2040:rp2040`) 6.3.2. Firmware library versions are listed in
[firmware/README.md](firmware/README.md).

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
