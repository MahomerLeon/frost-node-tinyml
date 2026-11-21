# Firmware (ESP32-S3)

Code that runs on the ESP32-S3 DevKitC-1.

| Sketch | Purpose |
|---|---|
| `logger/` | Logs BME280 readings to the flash memory as CSV (own dataset, R4) |
| `inference/` | Runs the TFLite int8 model on the node (R2), circular buffer (R6), benchmark (R7) |
| `i2c_scan/` | Wiring diagnostic: lists the I2C devices and the 1-Wire probe that answer |
| `pico_benchmark/` | Raspberry Pi Pico (RP2040): runs the same model and benchmark, to compare with the ESP32-S3 (R7) |

## Toolchain and library versions

Checked on 2026-11-12 by compiling for `esp32:esp32:esp32s3`.

| Component | Version |
|---|---|
| arduino-cli | 1.5.1 |
| Arduino-ESP32 core (`esp32:esp32`) | 3.3.12 |
| Adafruit BME280 Library | 2.3.0 |
| Adafruit INA219 (only for `inference/`, power measurement) | 1.2.3 |
| OneWire (reference probe, `logger/`, `inference/`, `i2c_scan/`) | 2.3.8 |
| DallasTemperature (reference probe, `logger/`, `inference/`) | 4.0.6 |
| Adafruit BusIO (dependency) | 1.17.4 |
| Adafruit Unified Sensor (dependency) | 1.1.15 |
| Chirale_TensorFLowLite (TensorFlow Lite Micro, only for `inference/`) | 2.0.0 |
| LittleFS, Wire, WiFi | included in the core |
| Raspberry Pi Pico core (`rp2040:rp2040`, by Earle Philhower), only for `pico_benchmark/` | 6.3.2 |

Before adding any other library, check that it compiles for the ESP32-S3 with
this core version and add it to the table.

### Arduino IDE

- Boards Manager: install **esp32 by Espressif Systems**, version 3.3.12.
  (File > Preferences > Additional boards manager URLs:
  `https://espressif.github.io/arduino-esp32/package_esp32_index.json`)
- Library Manager: install **Adafruit BME280 Library** (accept its
  dependencies) and, for `inference/`, **Adafruit INA219** and
  **Chirale_TensorFLowLite**.
- Tools menu:

  | Option | Value |
  |---|---|
  | Board | ESP32S3 Dev Module |
  | Port | the port of the connector labelled **UART** |
  | USB CDC On Boot | **Disabled** (the sketches print on the UART connector) |
  | Flash Size | the size of your module (the default 4MB works on every DevKitC-1) |
  | Partition Scheme | Default 4MB with spiffs (1.2MB APP/1.5MB SPIFFS) |
  | Upload Speed | 921600 |

  If the board is connected through the connector labelled **USB** instead,
  set USB CDC On Boot to Enabled; the port number will be different.
  The "SPIFFS" partition of the scheme is the one LittleFS uses for the log.

### arduino-cli

```
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://espressif.github.io/arduino-esp32/package_esp32_index.json
arduino-cli core update-index
arduino-cli core install esp32:esp32@3.3.12
arduino-cli lib install "Adafruit BME280 Library@2.3.0" "Adafruit INA219@1.2.3" "Chirale_TensorFLowLite@2.0.0" "OneWire@2.3.8" "DallasTemperature@4.0.6"
```

For the Raspberry Pi Pico, also:

```
arduino-cli config add board_manager.additional_urls https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
arduino-cli core update-index
arduino-cli core install rp2040:rp2040@6.3.2
```

How to wire the sensors, step by step: [docs/hardware_setup.md](../docs/hardware_setup.md).

Connect the board with the connector labelled **UART**, with the 5 V charger
disconnected (see `docs/wiring_diagram_esp32s3.png`), and find the port with
`arduino-cli board list`. The examples use `COM9`.

## `i2c_scan`: check the wiring first

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/i2c_scan
arduino-cli monitor -p COM9 -c baudrate=115200
```

Expected with correct wiring: `FOUND 0x76 chip_id=0x60` (BME280) and, if the
INA219 is connected, `FOUND 0x40`. Chip ID `0x58` means the module is a
BMP280, which cannot measure humidity.

## `logger`

Settings are in `logger/config.h`: sampling interval (5 minutes), clock
source and valid ranges.

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/logger
arduino-cli monitor -p COM9 -c baudrate=115200
```

Type a command in the monitor and press Enter:

| Command | Effect |
|---|---|
| `SETTIME <epoch>` | sets the clock (seconds since 1970-01-01 UTC) |
| `STATUS` | rows saved, flash used and free, current time, sensor state |
| `DUMP` | prints the whole CSV between `# DUMP BEGIN` and `# DUMP END` |
| `CLEAR` | deletes all saved rows |
| `TEST` | checks the chip ID (warns if the sensor is not a BME280) and whether the probe answers |
| `SAMPLE` | takes one extra reading right now |

Behaviour to know:

- Each reading is printed as a CSV row and appended to `/log.csv` in the
  flash:
  `timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status`.
  `reference_temperature_c` is the DS18B20 probe (`nan` if it is not connected).
- A log written by the previous firmware (without the probe column) is kept:
  the logger asks to download it with `DUMP` and then `CLEAR` it. An empty one
  is simply restarted with the new columns.
- An invalid reading (NaN or outside the BME280 datasheet ranges) is saved
  with status `sensor_error`; the program continues and retries the sensor.
- While the clock is not set, readings are printed but **not saved**.
- The clock is lost on reset or power loss. `USE_WIFI_NTP` is `1` in
  `logger/config.h`, so the node sets its clock from the network by itself:
  at boot and, while the clock is still not set, again before every
  reading (the Wi-Fi may come back later than the node after a power cut).
  This is what lets the node work without a PC. Without Wi-Fi, send
  `SETTIME`, which `ml/serial_dump.py` does automatically.
- The Wi-Fi name and password go in `logger/secrets.h` (copy
  `secrets.example.h`). That file is in `.gitignore` and is never uploaded.
  If it is missing, the compiler stops with a message that explains it; set
  `USE_WIFI_NTP` to `0` to compile without Wi-Fi. The ESP32-S3 only connects
  to 2.4 GHz networks. With Wi-Fi the logger uses about 75 % of the program
  partition (983 681 bytes).
- The log partition holds about 1.4 MB. `STATUS` shows the free space.

Download the log to the PC (close the monitor first):

```
python ml/serial_dump.py COM9
```

Expected: `# SETTIME done: <time>` and
`Saved <n> data rows to ...\data\raw\node\node_log_<date>_<time>.csv`.

Tested on the board: on 2026-11-12 without sensors (rows saved as
`sensor_error`), and on 2026-11-17 with the BME280 connected: `i2c_scan` found
`0x40` (INA219) and `0x76` with chip ID `0x60` (a real BME280), and `SAMPLE`,
`STATUS` and `DUMP` gave valid rows (indoors: about 21.6 °C, 49.7 %, 739.5 hPa).

## `inference`

Needs `inference/model_data.h`, which is generated by
`python ml/convert_tflite.py`. The file does not exist until a model has been
trained, so the sketch does not compile before that.

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/inference
arduino-cli monitor -p COM9 -c baudrate=115200
```

The first compilation takes more than 10 minutes because the whole
TensorFlow Lite Micro library is compiled; later ones are fast.

This sketch also does the job of the logger, so in the field only this one
is needed once a model exists: every reading goes to `/log.csv` (same format
as the logger) and every prediction to `/predictions.csv` in the flash.

| Command | Effect |
|---|---|
| `SETTIME <epoch>` | sets the clock; required, the model uses the hour of the day |
| `STATUS` | clock, sensor, model, window fill, rows stored and free flash |
| `PREDICT` | runs the model now on the current window (not saved) |
| `DUMP` | prints `/log.csv`; `ml/serial_dump.py` works with this firmware too |
| `DUMPPRED` | prints `/predictions.csv`; used by `scraper/node_listener.py` |
| `CLEAR` | deletes both files |
| `BENCHMARK` | times 200 inferences and prints latency mean/std, tensor arena, Flash, heap, stack and CPU load with percentages (R7); with an INA219 connected it adds current, power and energy per inference. The report is also saved in the flash |
| `LASTBENCH` | prints the last saved benchmark report (needed for the power measurement, which runs without a PC: see `docs/hardware_setup.md`) |
| `VECTOR a,b,...` | runs the model on a raw int8 input |
| `WINDOW <hour> t,h,p;...` | runs the whole preprocessing and the model on raw readings; nothing is stored |

Output lines: one CSV row per reading, `STEP,...` when a 30 min step closes,
and `PREDICTION,<time>,class=<c>,p0=...,p1=...` after each step once the 3 h
window is complete.

Clock in the field: with `USE_WIFI_NTP 1` in `inference/config.h` (and a
`secrets.h` copied from `secrets.example.h`) the clock is set from the
network at boot and retried before every reading while it is not set. It is
`0` by default in this sketch: Wi-Fi plus TensorFlow Lite Micro has not been
compiled together yet, and the program partition (1.25 MB) may be tight.
Without Wi-Fi the clock is lost on a power cut and nothing is predicted until
`SETTIME` is sent again.

Validate the node against the PC:

```
python ml/validate_on_device.py COM9
```

It runs two checks: the model alone (`VECTOR`, expected
`identical int8 output (node == PC): 100 of 100`) and the whole preprocessing
(`WINDOW`), where differences of 1 or 2 units are possible because the node
uses 32-bit floats.

Test status, on the board with the placeholder model and **without
sensors** (2026-11-17):

- Verified: `STATUS`, `CLEAR`, `DUMP`, `DUMPPRED`, `BENCHMARK` (including the
  stack), `LASTBENCH` after a reset, and `RUN_BENCHMARK_AT_BOOT`.
- `ml/validate_on_device.py`: 100 of 100 identical outputs with `VECTOR` and
  50 of 50 with `WINDOW`, so the preprocessing of the node gives exactly the
  same model input as the Python code.
- 2026-11-17, with the sensors connected: `STATUS` shows `sensor=ok` and
  `power_meter=ok`, and the benchmark prints its power lines. They read about
  0 mA because the board was powered by USB, not through the INA219.
- Not verified yet: a complete 3 h window with real readings (the first
  prediction needs 3 hours of data) and a real power measurement through the
  INA219.

Reference probe (DS18B20 on GPIO4): read by `logger/` and `inference/` into the
column `reference_temperature_c`, only to calibrate the BME280; the model does
not use it. Tested on 2026-11-20: `i2c_scan` found it with family code `0x28`
(a DS18B20), and `TEST` and `SAMPLE` in the logger read it next to the BME280.

## `pico_benchmark` (Raspberry Pi Pico, RP2040)

Runs the same int8 model as `inference/` on a more limited board, to show
whether the ESP32-S3 is oversized (R7). It only benchmarks: it does not log
data or predict in the field. Wiring: section 10 of
[docs/hardware_setup.md](../docs/hardware_setup.md).

Needs `pico_benchmark/model_data.h`, written by `python ml/convert_tflite.py`
together with the one of `inference/`.

Arduino IDE (Tools menu):

| Option | Value |
|---|---|
| Board | Raspberry Pi Pico (in the "Raspberry Pi Pico/RP2040/RP2350" section) |
| Flash Size | 2MB (Sketch: 1984KB, FS: 64KB), so `LASTBENCH` can keep the report |
| Port | the port of the Pico |

**Extra compiler option.** The TensorFlow Lite Micro library
(Chirale_TensorFLowLite 2.0.0, the same one as on the ESP32-S3) does not
compile on the RP2040 core as it is: its latbuffers part omits
#include <cstdint> when it detects Arduino, and this core compiles with
C++23, which no longer adds that header indirectly. The fix is the compiler
option -include stdint.h; the library itself is not modified. The
	flm_cortexm library was also tried and has the same problem.

- arduino-cli: add --build-property "compiler.cpp.extra_flags=-include stdint.h"
  (already in the command below).
- Arduino IDE: create a text file named platform.local.txt in
  %LOCALAPPDATA%\Arduino15\packages\rp2040\hardware\rp2040\6.3.2\ with this
  single line, and restart the IDE:

  `
  compiler.cpp.extra_flags=-include stdint.h
  `

  It applies to every sketch compiled for RP2040 boards and does no harm to
  sketches that do not need it.

Compiled on 2026-11-17 with the placeholder model: 138 564 bytes of program
(6 % of the 2 027 520 bytes available) and 26 804 bytes of global variables
(10 % of 262 144).

arduino-cli (replace `COM12` with the port of the Pico):

```
arduino-cli compile --fqbn rp2040:rp2040:rpipico:flash=2097152_65536 --build-property "compiler.cpp.extra_flags=-include stdint.h" -u -p COM12 firmware/pico_benchmark
arduino-cli monitor -p COM12 -c baudrate=115200
```

The first upload may need BOOTSEL: unplug the Pico, hold its `BOOTSEL`
button, plug it in, release the button and upload again.

| Command | Effect |
|---|---|
| `STATUS` | model, sensor, power meter and storage state |
| `TEST` | checks the chip ID of the BME280 |
| `SAMPLE` | reads the BME280 once |
| `BENCHMARK` | same report as on the ESP32-S3 (latency, tensor arena, flash, RAM, power) |
| `LASTBENCH` | last report saved in the flash |
| `VECTOR a,b,...` | runs the model on a raw int8 input |

Check that the Pico gives the same result as the PC:

```
python ml/validate_on_device.py COM12 --model-only
```

Expected: `identical int8 output (node == PC): 100 of 100`.

Test status, on a real Pico on 2026-11-20 with the placeholder model and no
sensors: it loads by copying the `.uf2` file to the `RPI-RP2` drive (BOOTSEL
mode), shows up as a USB serial port, `STATUS`, `BENCHMARK` and `LASTBENCH` work,
and `validate_on_device.py --model-only` gave 100 of 100 identical outputs.
Not tested yet: `TEST` and `SAMPLE` with the BME280, and power through the INA219.

To load it without `-u`: compile with `--output-dir <folder>` and copy the
`pico_benchmark.ino.uf2` file from that folder to the `RPI-RP2` drive.
