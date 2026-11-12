"""Download hourly IDEAM observations for the UPTC Tunja station.

Source: Colombian open data portal (datos.gov.co), Socrata API.
This is PUBLIC SUPPORT DATA only. The main dataset of the project must be
captured with our own node (course requirement R4).

Run from the repository root:
    py ml/download_ideam_uptc.py

A variable is skipped if its CSV already exists, so the script never
overwrites data. To refresh a file, rename or move the old one first.
"""

import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.datos.gov.co/resource/{dataset_id}.json"
STATION_CODE = "2401500086"  # IDEAM automatic station: UPTC Tunja
PAGE_SIZE = 5000
MAX_ATTEMPTS = 6

# Folder where the CSV files are stored: <repo>/data/raw/public
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "public"

# Output file prefix -> dataset id in datos.gov.co.
# The prefixes are in Spanish because the files already downloaded use them.
DATASETS = {
    "temperatura": "sbwg-7ju4",  # air temperature
    "humedad": "uext-mhny",      # relative humidity
    "presion": "62tk-nxj5",      # atmospheric pressure
}


def request_json(url, params):
    """GET a URL and return the parsed JSON, or None if every attempt fails."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, timeout=90)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as error:
            wait_seconds = 3 * attempt
            print(f"  attempt {attempt}/{MAX_ATTEMPTS} failed "
                  f"({type(error).__name__}); retrying in {wait_seconds}s")
            time.sleep(wait_seconds)
    return None


def download(name, dataset_id):
    """Download every row of one variable, page by page, into a CSV file."""
    output_file = OUTPUT_DIR / f"{name}_uptc_tunja.csv"
    if output_file.exists():
        print(f"{name}: already exists, skipping")
        return

    rows = []
    offset = 0
    while True:
        page = request_json(BASE_URL.format(dataset_id=dataset_id), {
            "codigoestacion": STATION_CODE,
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$order": "fechaobservacion",
        })
        if page is None:
            print(f"{name}: download FAILED (the server closed the connection)")
            return
        if not page:  # an empty page means there are no more rows
            break
        rows += page
        offset += PAGE_SIZE

    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"{name}: {len(rows)} rows saved to {output_file}")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, dataset_id in DATASETS.items():
        download(name, dataset_id)
