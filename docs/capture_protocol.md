# Data capture protocol (own dataset, R4)

Status: **draft**. One outdoor night has been recorded (2026-11-20/21), but
it is not part of the dataset because of a sensor placement error (see
"Lessons from the first night"). Items marked "to confirm" are still open.

## Where and how the node is installed

| Parameter | Value |
|---|---|
| Place | Vereda Pirgua, Tunja, at the author's home. Wall socket and home Wi-Fi available (confirmed) |
| Sensor height | 1.5 m above the ground |
| Sensor placement | **BME280 and DS18B20 outside the electronics box**, together inside the sun shield, open at the bottom, 20 to 30 cm from the box (I2C wires extended with jumpers; very long I2C wires stop working) |
| Electronics | ESP32-S3, breadboard and INA219 in a closed plastic box with silica gel; wires enter from below with a drip loop |
| Sun protection | Shield around the sensors (white cup or PVC tube with slots), so they measure air temperature and not direct sun |
| Site | Over grass or soil, away from walls, roofs, trees and concrete, which keep heat at night |
| Period | November to February, the season with most frost in the public data |
| Power | Wall charger; power bank as backup |
| Clock | NTP over the home Wi-Fi at every boot (`USE_WIFI_NTP 1`) |

## Lessons from the first night (2026-11-20/21)

The node worked without a PC for about 14 hours: 170 readings, all `ok`,
one every 5 minutes, clock set by NTP, no restarts. But the **BME280 was
inside the electronics box** and only the probe was outside:

- At night the BME280 read about 4.4 °C more than the probe (standard
  deviation 0.4 °C) and stayed almost flat, while the probe went down to
  12.5 °C at 06:14. In the indoor test, with both sensors in the same air,
  the difference had been +0.09 °C.
- The BME280 read about 60 % humidity. With its own dew point, the outdoor
  air at the probe temperature would have had about 80 %.
- The pressure is valid (it does not depend on the air around the sensor).

Rule: the BME280 must measure outdoor air, never the air of the box. The
log is kept as a test in `data/raw/node_tests/` and the chart is
[first_night_pirgua_2026-11-20.png](first_night_pirgua_2026-11-20.png).

## What is recorded

| Parameter | Value |
|---|---|
| Sensor | BME280 over I2C: temperature (°C), relative humidity (%), pressure (hPa, absolute station pressure) |
| Sampling interval | Every 5 minutes (`SAMPLE_INTERVAL_MINUTES` in the firmware `config.h`). Starting value, configurable |
| Sensor mode | Forced mode, oversampling x1, filter off: the sensor sleeps between readings to avoid self-heating |
| Timestamp | Local time (UTC-5) written with its offset, for example `2026-11-12T21:30:00-05:00` |
| Stored row | `timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status` in `/log.csv` (flash memory, LittleFS) |
| Reference probe | DS18B20 on GPIO4, read at every reading into `reference_temperature_c` (`nan` if absent). Only for calibration: the model does not use it |
| Invalid readings | NaN or outside the BME280 datasheet range (-40 to 85 °C, 0 to 100 %, 300 to 1100 hPa) are stored with status `sensor_error` and excluded later |

## Clock

The ESP32-S3 has no battery-backed clock: the time is lost on every reset or
power cut, and readings are not stored until the clock is set again.

- With Wi-Fi at the site: `USE_WIFI_NTP 1`, the clock is set at every boot.
- Without Wi-Fi: the clock is set from the PC (`SETTIME`, sent automatically
  by `ml/serial_dump.py`). After a power cut the node stops storing until
  someone connects a PC.

Which of the two will be used is to confirm.

## Calibration (to do before the capture)

1. Ice-water test: sensor and reference thermometer next to each other in a
   glass of water with ice (close to 0 °C).
2. Leave the sensor and the reference together for a few hours at ambient
   temperature.
3. Write down the offset between the two in this document. Do not correct
   the raw files: any correction is applied when the dataset is built.

The comparison is computed by `python ml/calibration_report.py` (offset =
BME280 minus probe: mean, standard deviation, minimum and maximum). Use
`--start` and `--end` to keep only the hours of one test.

Result: not done yet.

## From the node to the dataset

1. Download the log: `python ml/serial_dump.py COM9` creates
   `data/raw/node/node_log_<date>_<time>.csv`. Raw files are never edited or
   deleted. Downloading does not erase the node; `CLEAR` is sent by hand
   after checking the file.
2. Build a version: `python ml/prepare_dataset.py` creates
   `data/processed/dataset_vN.csv` with its report and a copy of the
   configuration used.

## Labeling

The class of each window depends on the minimum temperature of the following
6 hours, compared with one threshold (2 classes) or two thresholds (3
classes). **The thresholds and the number of classes are not decided**; they
need agronomic support (for example Fedepapa, ICA or literature) and are
written in `ml/config.yaml`. The preparation script stops while they are
empty.

## Versions and split

- Versions `v1`, `v2`, ...: a new one every time the dataset is extended or
  corrected (`dataset_version` in `ml/config.yaml`). A version is never
  overwritten.
- Split into train, validation and test by **whole calendar days**
  (70 / 15 / 15 %), with a fixed seed. Every reading of a day is in the same
  split, and a day is in the same split for every source, so there is no
  leakage between splits. Checked by `tests/test_prepare_dataset.py`.
- Known limitation: a window close to midnight uses a few hours of the
  neighbouring day.

## Public data

The IDEAM series of the UPTC Tunja station and the Zenodo Altiplano dataset
are support data only: they were used to develop and test the code. The
final results must come from a model trained and evaluated with data from
the node. Set `training.sources: [node]` in `ml/config.yaml` to train only
with the own data.

## Ethics

No personal data is collected. Installing the node needs the permission of
the owner of the land.
