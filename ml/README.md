# Data preparation, training and conversion

All settings are in `config.yaml`. Run every script from the repository root
with the Python of the virtual environment (see the main README).

## Scripts

| Script | What it does |
|---|---|
| `serial_dump.py` | Sets the clock of the node and downloads its CSV log into `data/raw/node/` |
| `download_ideam_uptc.py` | Downloads the hourly IDEAM files into `data/raw/public/` (skips existing files) |
| `audit_ideam_data.py` | Prints a quality report of the raw IDEAM files (read-only) |
| `clean_ideam_data.py` | Builds `data/processed/ideam_uptc_hourly.csv` |
| `prepare_dataset.py` | Builds `data/processed/dataset_vN.csv` from the node, IDEAM and Zenodo sources, with labels and the split by days |
| `train.py` | Trains the float model and reports F1, confusion matrix, precision and recall |
| `convert_tflite.py` | Converts to TFLite int8, compares F1 with the float model (R3), writes `firmware/inference/model_data.h` |
| `validate_on_device.py` | Sends test vectors to the ESP32-S3 and compares its output with the PC int8 model |
| `dataset_utils.py` | Helpers shared by the scripts above |

## Order of use

```
python ml/serial_dump.py COM9         # after the node has logged data
python ml/prepare_dataset.py
python ml/train.py
python ml/convert_tflite.py
# compile and upload firmware/inference, then:
python ml/validate_on_device.py COM9
```

## The threshold is not decided

`prepare_dataset.py` stops with an error until `labeling.thresholds_c` is
filled in `config.yaml`. It is an agronomic decision and no script contains a
default value.

## Status

The whole chain (prepare, train, convert, on-device validation) was run once
as a **pipeline test** with a placeholder threshold and output in a temporary
folder, only to check that the code works. Those numbers are not project
results and were not saved in the repository. No real dataset version or
model exists yet.

## Notes on the method

- **Dew point:** Magnus formula with a = 17.625, b = 243.04 °C (Alduchov and
  Eskridge, 1996); documented in `prepare_dataset.py` and repeated in the
  firmware.
- **Grid:** every source is averaged on a 30 min grid. Gaps are filled by
  linear interpolation only when the real readings around the gap are at most
  60 min apart. IDEAM is hourly, so about half of its 30 min values are
  interpolated; the report states the exact percentage.
- **Pressure:** the Zenodo source has no pressure. If it is included in
  `training.sources`, the model is trained without pressure.
- **Split:** by calendar day, the same day in the same split for all sources.
  Windows near midnight use a few hours of the neighbouring day.
- **Imbalance:** class weights (explained in `train.py`).
- **Test split:** evaluated once at the end; never used to choose anything.
