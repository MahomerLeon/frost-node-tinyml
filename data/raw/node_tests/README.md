# Test logs of the node (not part of the dataset)

Logs recorded while testing the node. They are kept as evidence of the tests
but are **not** read by `ml/prepare_dataset.py`, which only reads
`data/raw/node/`.

| File | What it was |
|---|---|
| `node_log_20261120_134923.csv` | Indoor test at home (in Pirgua, but inside the house, so it does not represent the outdoor air) on 2026-11-20, 12:55 to 13:49. The node was unplugged from the PC and powered by a charger: it set its clock by NTP over Wi-Fi by itself and saved one reading every 5 minutes with no gaps (12 rows, all `ok`). BME280 minus probe: mean +0.09 °C, std 0.42 °C. Not a calibration. |
| `node_log_20261121_091808.csv` | **First night outdoors in Pirgua**, 2026-11-20 19:04 to 2026-11-21 08:59 (rows at 17:30 and 09:17 are indoors). The node worked without a PC: 170 rows, all `ok`, one every 5 minutes, clock set by NTP, no restarts. **But the BME280 was inside the electronics box** and only the DS18B20 probe was outside, so the BME280 temperature and humidity are those of the box air: about 4.4 °C warmer than the probe at night (std 0.4 °C) and about 60 % humidity instead of the about 80 % the outdoor air had at the probe temperature. Valid: the probe column (outdoor minimum 12.5 °C at 06:14) and the pressure. Not usable for the frost dataset. Chart: `docs/first_night_pirgua_2026-11-20.png`. |
| `node_log_20261120_135442.csv` | Full content of the node just before `CLEAR`: the same 12 rows plus two more indoor readings, 13:54:14 (regular) and 13:54:30 (taken after the board restarted when the serial port was opened). In that last row the probe reads 1.1 °C less than in the previous one while the BME280 barely changes; not explained yet. |
