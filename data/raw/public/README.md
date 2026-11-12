# Public support data

These files are **support data only**. The main dataset of the project is the
one captured with our own node (`data/raw/node/`, course requirement R4).

Do not edit or delete these files. Scripts must read them and write their
results somewhere else.

## 1. IDEAM station UPTC Tunja (hourly)

| File | Variable | Unit |
|---|---|---|
| `temperatura_uptc_tunja.csv` | air temperature at 2 m | °C |
| `humedad_uptc_tunja.csv` | air humidity at 2 m | % |
| `presion_uptc_tunja.csv` | atmospheric pressure | hPa |

- Station code: `2401500086`
- Source: datos.gov.co (Socrata API), datasets `sbwg-7ju4` (temperature),
  `uext-mhny` (humidity) and `62tk-nxj5` (pressure)
- Downloaded on 2026-11-05 with `ml/download_ideam_uptc.py`
- Period covered: 2019-03-05 to 2026-11-03 (pressure: to 2026-11-04)
- The file names are in Spanish because that is how they were downloaded.

### Audit results

Produced by `ml/audit_ideam_data.py` on 2026-11-12. Run the script to see
the full report. Nothing has been cleaned yet: the CSV files are untouched.

Facts measured by the script:

- **Duplicates:** each file has 3 482 duplicated timestamps. The duplicated
  rows never disagree in value, so keeping one row per timestamp is safe.
- **Coverage:** after removing duplicates, about 63 % of the hours in the
  period have data (temperature 42 079, humidity 42 287, pressure 42 542 hours
  out of about 67 200).
- **Coverage by year (temperature):** 2019 95 %, 2020 93 %, 2021 69 %,
  2022 45 %, 2023 16 %, 2024 18 %, 2025 84 %, 2026 91 %.
- **Longest gaps (all three files):** 2023-03-17 to 2024-09-04 (537 days) and
  2021-10-05 to 2022-05-11 (217 days).
- **Complete hours:** 41 902 hours have the three variables at the same time.
- **Values:** no missing values; temperature 0.1 to 25.4 °C, humidity 14 to
  100 %, pressure 733.4 to 742.9 hPa.
- **Cold events:** no reading is at or below 0 °C. The coldest reading is
  0.1 °C (2023-01-29); the 1st percentile of the daily minimum is 3.1 °C.
  (0 °C is mentioned only as the freezing point of water; it is not the
  frost-risk threshold of the project, which is still undecided.)
- **Metadata change:** rows up to 2023-03-17 say municipality Samacá
  (5.4417, -73.5522); rows from 2024-09-04 say Tunja (5.5536, -73.3553). The
  station name, sensor descriptions and the pressure unit spelling
  (`HPa` / `hPa`) change at the same moment.
- **Humidity label:** all rows from 2024-09-04 describe the sensor as
  "HUMEDAD DEL SUELO A 1 m Ó MAS" (soil humidity) instead of
  "Humedad del aire 2 mt", with the same sensor code `0027`.

Interpretations (reasonable, but NOT verified with IDEAM):

- The metadata change looks like a correction of the catalog, not a move of
  the station: temperature, humidity and pressure have almost the same
  distribution before and after (mean pressure 738.7 vs 738.5 hPa).
- For the same reason the "soil humidity" description looks like a labeling
  error: the values behave like air humidity (mean 82.7 % before, 83.0 % after).
- The timestamps look like local time (UTC-5), not UTC: on average the coldest
  hour is 06:00 and the warmest is 15:00.

## 2. Topoclimatic Graph Dataset for Frost Prediction (Altiplano Cundiboyacense)

- File: `topoclimatic_graph_dataset_frost_prediction_v1.zip` (63 MB,
  **not tracked by git**, see `.gitignore`)
- Authors: Calderon Caro, Castaneda Sanchez, Branch Bedoya, Ballesteros Parra
- Version v1.0, released 2026-05-13, license CC BY 4.0
- DOI (as written in the `CITATION.cff` inside the zip):
  https://doi.org/10.5281/zenodo.20616866
- Contents: 30-minute series from 23 agricultural weather stations
  (temperature, relative humidity, dew point, radiation), frost labels
  (`frost_event`, `frost_warning_6h`) and graph products. See the `README.md`
  and `DATA_DICTIONARY.md` inside the zip.

If you clone the repository on another computer, download the zip again from
the DOI above and place it in this folder. Cite the dataset if it is used.
