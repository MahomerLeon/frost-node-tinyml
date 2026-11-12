# Raw data captured with the node

CSV logs downloaded from the node with `ml/serial_dump.py`, one file per
download (`node_log_<date>_<time>.csv`). No real log has been downloaded yet.

Columns: `timestamp_iso` (local time with UTC offset), `temperature_c`,
`humidity_pct`, `pressure_hpa`, `status` (`ok` or `sensor_error`).

- Raw files are never edited or deleted. `ml/prepare_dataset.py` reads all the
  files in this folder, ignores `sensor_error` rows and removes rows repeated
  between two downloads.
- Dataset versions are built from them and saved in `data/processed/`.

This is the source of the main dataset of the project (course requirement R4):

- Captured with our own node, following a documented protocol (to be written
  in `docs/`).
- Versioned in `data/processed/` as `dataset_v1`, `dataset_v2`, ... A version
  is never overwritten.
- Split into train / validation / test **by days**.

Still to be defined: the capture protocol (where, how long, sampling interval).
