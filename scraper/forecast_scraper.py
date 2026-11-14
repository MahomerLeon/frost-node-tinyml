"""Periodic HTML scraper of the temperature forecast for Tunja (R5).

Every interval_minutes it downloads the HTML page configured in
scraper/config.yaml, extracts the forecast temperatures and appends them to
a CSV log. It keeps running after a failure: failures are retried, written
to an error log, and the next scrape happens at the normal time.

Run from the repository root:
    python scraper/forecast_scraper.py          # runs until Ctrl+C
    python scraper/forecast_scraper.py --once   # one scrape, then exit

The page shows, for three days, the temperature of four moments of the day
(Morning, Noon, Evening, Night). It does NOT show the hours between 21:00 and
09:00, when the daily minimum usually happens.
"""

import argparse
import csv
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

from hash_table import HashTable

REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.yaml"

LOG_COLUMNS = ["scraped_at", "municipality", "forecast_time",
               "temperature_c", "feels_like_c"]

# "┤  Thu 12 Nov ├"  -> day 12, month Nov
DAY_HEADER = re.compile(r"┤\s+\w{3} (\d{1,2}) (\w{3})\s+├")
# "+15(14) °C" -> 15 and 14 ;  "18 °C" -> 18 ;  "-2(-5) °C" -> -2 and -5
TEMPERATURE = re.compile(r"([+-]?\d+)(?:\(([+-]?\d+)\))?\s*°C")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load_config(path=DEFAULT_CONFIG):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def fetch_html(config):
    """Download the page, retrying on failure. Raises if every attempt fails."""
    last_error = None
    for attempt in range(1, config["max_retries"] + 1):
        try:
            response = requests.get(config["url"],
                                    headers={"User-Agent": config["user_agent"]},
                                    timeout=config["timeout_seconds"])
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as error:
            last_error = error
            logging.warning("attempt %d/%d failed: %s",
                            attempt, config["max_retries"], error)
            if attempt < config["max_retries"]:
                time.sleep(config["retry_wait_seconds"])
    raise RuntimeError(f"download failed after {config['max_retries']} attempts: {last_error}")


def year_of(day, month, today):
    """The page has no year: choose the one that puts the date nearest today."""
    candidates = [date(year, month, day)
                  for year in (today.year - 1, today.year, today.year + 1)]
    return min(candidates, key=lambda d: abs((d - today).days)).year


def parse_forecast(html, config, today=None):
    """Extract the forecast from the HTML page.

    Returns a list of dictionaries with municipality, forecast_time
    ("YYYY-MM-DD HH:MM", local time), temperature_c and feels_like_c.
    Raises ValueError if the page does not look as expected.
    """
    today = today or date.today()
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="term-container")
    if container is None:
        raise ValueError("forecast block not found (the page layout changed?)")
    lines = container.get_text().split("\n")

    municipality = config["municipality"]
    if not any(line.startswith("Location:") and municipality in line for line in lines):
        raise ValueError(f"the page is not for {municipality}")

    hours = list(config["period_hours"].values())  # Morning, Noon, Evening, Night
    rows = []
    current_day = None
    for line in lines:
        header = DAY_HEADER.search(line)
        if header:
            day, month = int(header.group(1)), MONTHS.index(header.group(2)) + 1
            current_day = date(year_of(day, month, today), month, day)
            continue
        if current_day is None or "°C" not in line:
            continue
        cells = [cell for cell in line.split("│") if "°C" in cell]
        if len(cells) != len(hours):
            continue  # not the row with the four periods
        for hour, cell in zip(hours, cells):
            match = TEMPERATURE.search(cell)
            if not match:
                raise ValueError(f"temperature not understood: {cell.strip()!r}")
            temperature = float(match.group(1))
            feels_like = float(match.group(2)) if match.group(2) else temperature
            rows.append({
                "municipality": municipality,
                "forecast_time": f"{current_day.isoformat()} {hour:02d}:00",
                "temperature_c": temperature,
                "feels_like_c": feels_like,
            })
        current_day = None  # one temperature row per day

    if not rows:
        raise ValueError("no forecast values found (the page layout changed?)")
    return rows


def append_to_log(rows, config):
    """Append the scraped values to the CSV log (creates it if missing)."""
    log_file = REPO_DIR / config["paths"]["forecast_log"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    is_new = not log_file.exists()
    scraped_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(log_file, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LOG_COLUMNS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow({"scraped_at": scraped_at, **row})


def load_forecast_table(config):
    """Load the CSV log into a hash table: (municipality, time) -> forecast.

    The log is in chronological order, so when the same forecast time was
    scraped several times, the newest value replaces the older ones.
    """
    table = HashTable()
    log_file = REPO_DIR / config["paths"]["forecast_log"]
    if not log_file.exists():
        return table
    with open(log_file, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            key = (row["municipality"], row["forecast_time"])
            table.put(key, {
                "temperature_c": float(row["temperature_c"]),
                "feels_like_c": float(row["feels_like_c"]),
                "scraped_at": row["scraped_at"],
            })
    return table


def scrape_once(config):
    """One complete scrape. Returns True on success; never raises."""
    try:
        rows = parse_forecast(fetch_html(config), config)
        append_to_log(rows, config)
        logging.info("saved %d forecast values (%s to %s)", len(rows),
                     rows[0]["forecast_time"], rows[-1]["forecast_time"])
        return True
    except Exception as error:  # the scraper must keep running after any failure
        logging.error("scrape failed: %s", error)
        return False


def setup_logging(config):
    """Messages go to the screen; warnings and errors also go to a file."""
    error_file = REPO_DIR / config["paths"]["error_log"]
    error_file.parent.mkdir(parents=True, exist_ok=True)
    to_file = logging.FileHandler(error_file, encoding="utf-8")
    to_file.setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), to_file])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--once", action="store_true", help="scrape once and exit")
    args = parser.parse_args()
    config = load_config(args.config)
    setup_logging(config)

    if args.once:
        raise SystemExit(0 if scrape_once(config) else 1)

    interval = config["interval_minutes"] * 60
    logging.info("scraping %s every %d minutes. Stop with Ctrl+C.",
                 config["url"], config["interval_minutes"])
    try:
        while True:
            scrape_once(config)
            time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("stopped by the user")


if __name__ == "__main__":
    main()
