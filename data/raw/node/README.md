# Raw data captured with the node

CSV logs downloaded from the node with `ml/serial_dump.py`, one file per
download (`node_log_<date>_<time>.csv`).

Columns: `timestamp_iso` (local time with UTC offset), `temperature_c`,
`humidity_pct`, `pressure_hpa`, `reference_temperature_c` (DS18B20 probe, `nan` if
absent; logs from before 2026-11-17 do not have it), `status` (`ok` or
`sensor_error`, about the BME280).

- Raw files are never edited or deleted.
- `ml/prepare_dataset.py` reads all the files in this folder, but keeps only
  the rows inside the periods listed in `node.valid_periods` of
  `ml/config.yaml`, ignores `sensor_error` rows and removes rows repeated
  between two downloads. A file can therefore contain tests without
  contaminating the dataset.
- Dataset versions are built from them and saved in `data/processed/`.

## Files

| File | Content | Used |
|---|---|---|
| `node_log_20261122_083209.csv` | The whole memory of the node at 2026-11-22 08:32: 335 rows from 2026-11-20 17:30 to 2026-11-22 08:30. It includes the first night (BME280 inside the box, 11-20/21), indoor tests and boot readings. | Only 2026-11-21 19:45 to 2026-11-22 07:40: **143 readings**, the second night, both sensors outside the box |

The second night (2026-11-21 19:49 to 2026-11-22 07:35): 143 readings, all
`ok`, one every 5 minutes with no gaps, minimum 13.2 °C (class 0). Chart:
`docs/night2_pirgua_2026-11-21.png`. Add every new outdoor capture to
`node.valid_periods` after checking it.

This is the source of the main dataset of the project (course requirement R4):

- Captured with our own node, following the protocol in
  `docs/capture_protocol.md`.
- Versioned in `data/processed/` as `dataset_v1`, `dataset_v2`, ... A version
  is never overwritten.
- Split into train / validation / test **by days**, stratified by class.
