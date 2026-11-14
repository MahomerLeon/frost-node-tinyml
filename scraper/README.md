# Forecast scraper, hash table and dashboard

Settings are in `config.yaml`. Run everything from the repository root with
the Python of the virtual environment.

| File | What it does |
|---|---|
| `forecast_scraper.py` | Scrapes the HTML forecast every `interval_minutes`, with retries and an error log (R5) |
| `hash_table.py` | Own hash table with chaining, key (municipality, date_time) -> forecast (R6) |
| `node_listener.py` | Saves the `PREDICTION` and `STEP` lines of the node to CSV files |
| `comparison.py` | Compares each node prediction with the forecast of its time window, using the hash table |
| `dashboard.py` | Streamlit dashboard: node prediction, forecast, disagreements, temperature history |

## Forecast source

`https://wttr.in/Tunja` (HTML). Chosen on 2026-11-12 after checking IDEAM:
IDEAM publishes its forecast only as JavaScript map applications and
downloadable bulletins, not as numbers in an HTML page.

Known limits of the source:

- It is not an official source, and no terms-of-use page or robots.txt was
  found for it.
- The page gives the temperature at 09:00, 12:00, 18:00 and 21:00 for three
  days. It does **not** give the hours before sunrise, when the daily minimum
  (and frost) usually happens. A node prediction made late at night often has
  no forecast value inside its 6 h window; the dashboard shows those cases as
  "no forecast in the window".

## How to run

```
python scraper/hash_table.py                 # self-test of the hash table
python scraper/forecast_scraper.py --once    # one scrape
python scraper/forecast_scraper.py           # scrape every interval, until Ctrl+C
python scraper/node_listener.py COM9         # node running firmware/inference
python -m streamlit run scraper/dashboard.py
```

Expected:

- self-test: `OK: 499 keys in 1024 buckets, longest chain ...`
- one scrape: `INFO saved 12 forecast values (...)` and new rows in
  `data/raw/forecast/forecast_log.csv`
- dashboard: a browser page at `http://localhost:8501`

Failures (no network, page layout changed) are retried `max_retries` times,
written to `data/raw/forecast/scraper_errors.log`, and the scraper keeps
running.

## Node predictions: CSV, not an endpoint

The node sends its predictions over the serial port and `node_listener.py`
appends them to `data/raw/node_live/predictions.csv`. An HTTP endpoint would
need Wi-Fi at the node and a server that is always on.

## Status

Tested on 2026-11-12: the scraper (real page, and a forced failure), the hash
table self-test, and the dashboard with the real forecast. The comparison
table was tested only with made-up node predictions and a placeholder
threshold in a temporary folder, because no real predictions or threshold
exist yet. `node_listener.py` (including the download of the predictions
stored in the node) was tested only with a simulated node, not with the real
one.
