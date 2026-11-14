"""Tests of the forecast parser and the node line parser.

The HTML below is a small hand-made page with the same structure as the real
one (a div with class "term-container" and a table drawn with characters).
The temperatures are test values, not a real forecast.
"""

from datetime import date

import pytest

import forecast_scraper
import node_listener

CONFIG = {
    "municipality": "Tunja",
    "period_hours": {"Morning": 9, "Noon": 12, "Evening": 18, "Night": 21},
}


def make_page(days, location="Tunja, Boyacá, Colombia"):
    """days: list of (header text, [four temperature cells])."""
    lines = ["Weather report: Tunja", ""]
    for header, cells in days:
        lines.append(f"┌──────┬──────┤  {header} ├──────┬──────┐")
        lines.append("│ Morning │ Noon │ Evening │ Night │")
        lines.append("│ " + " │ ".join(f"<span>x</span> {cell} °C" for cell in cells) + " │")
        lines.append("│ 10 km │ 10 km │ 10 km │ 10 km │")
        lines.append("└──────┴──────┴──────┴──────┘")
    lines.append(f"Location: {location} [5.5,-73.3]")
    return ('<html><body><div class="term-container">' + "\n".join(lines)
            + "</div><script>var x = 1;</script></body></html>")


def test_parses_four_periods_per_day():
    page = make_page([("Thu 12 Nov", ["+15(14)", "18", "+13(12)", "+11(10)"]),
                      ("Fri 13 Nov", ["16", "20", "13", "10"])])
    rows = forecast_scraper.parse_forecast(page, CONFIG, today=date(2026, 11, 12))

    assert len(rows) == 8
    assert rows[0] == {"municipality": "Tunja", "forecast_time": "2026-11-12 09:00",
                       "temperature_c": 15.0, "feels_like_c": 14.0}
    # Without "(feels like)" the two values are the same
    assert rows[1]["temperature_c"] == 18.0 and rows[1]["feels_like_c"] == 18.0
    assert [r["forecast_time"] for r in rows[4:]] == [
        "2026-11-13 09:00", "2026-11-13 12:00", "2026-11-13 18:00", "2026-11-13 21:00"]


def test_parses_negative_temperatures():
    page = make_page([("Sat 14 Nov", ["-2(-5)", "+9(8)", "0", "-1"])])
    rows = forecast_scraper.parse_forecast(page, CONFIG, today=date(2026, 11, 14))
    assert [r["temperature_c"] for r in rows] == [-2.0, 9.0, 0.0, -1.0]
    assert rows[0]["feels_like_c"] == -5.0


def test_year_is_taken_from_the_nearest_date():
    page = make_page([("Fri 1 Jan", ["5", "15", "8", "4"])])
    rows = forecast_scraper.parse_forecast(page, CONFIG, today=date(2026, 12, 31))
    assert rows[0]["forecast_time"] == "2027-01-01 09:00"


def test_rejects_a_page_for_another_place():
    page = make_page([("Thu 12 Nov", ["15", "18", "13", "11"])], location="Bogotá, Colombia")
    with pytest.raises(ValueError):
        forecast_scraper.parse_forecast(page, CONFIG, today=date(2026, 11, 12))


def test_rejects_a_page_with_a_different_layout():
    with pytest.raises(ValueError):
        forecast_scraper.parse_forecast("<html><body><p>maintenance</p></body></html>",
                                        CONFIG, today=date(2026, 11, 12))


def test_scrape_once_survives_a_failure(monkeypatch, tmp_path):
    """A failed download must be reported as False, not crash the scraper."""
    def broken_download(config):
        raise RuntimeError("no network")
    monkeypatch.setattr(forecast_scraper, "fetch_html", broken_download)
    config = dict(CONFIG, paths={"forecast_log": str(tmp_path / "log.csv")})
    assert forecast_scraper.scrape_once(config) is False
    assert not (tmp_path / "log.csv").exists()


def test_forecast_log_is_loaded_into_the_hash_table(tmp_path):
    config = dict(CONFIG, paths={"forecast_log": str(tmp_path / "log.csv")})
    older = [{"municipality": "Tunja", "forecast_time": "2026-11-13 09:00",
              "temperature_c": 15.0, "feels_like_c": 14.0}]
    newer = [{"municipality": "Tunja", "forecast_time": "2026-11-13 09:00",
              "temperature_c": 13.0, "feels_like_c": 12.0}]
    forecast_scraper.append_to_log(older, config)
    forecast_scraper.append_to_log(newer, config)

    table = forecast_scraper.load_forecast_table(config)
    assert len(table) == 1  # the newest scrape replaces the older one
    assert table.get(("Tunja", "2026-11-13 09:00"))["temperature_c"] == 13.0


# ------------------------------------------------------------ node lines

def test_node_reading_line():
    kind, row = node_listener.parse_line("STEP,2026-11-12T12:30:00-05:00,14.25,81.10,739.40,ok")
    assert kind == "reading"
    assert row == ["2026-11-12T12:30:00-05:00", "14.25", "81.10", "739.40"]


def test_node_prediction_line_with_two_and_three_classes():
    kind, row = node_listener.parse_line(
        "PREDICTION,2026-11-12T12:30:00-05:00,class=1,p0=0.200,p1=0.800")
    assert (kind, row) == ("prediction", ["2026-11-12T12:30:00-05:00", "1", "0.200;0.800"])
    _, row = node_listener.parse_line(
        "PREDICTION,2026-11-12T12:30:00-05:00,class=2,p0=0.1,p1=0.2,p2=0.7")
    assert row[1:] == ["2", "0.1;0.2;0.7"]


def test_other_node_lines_are_ignored():
    assert node_listener.parse_line("# STATUS model=ok") is None
    assert node_listener.parse_line("STEP,2026-11-12T12:30:00-05:00,nan,nan,nan,no_data") is None
    assert node_listener.parse_line("2026-11-12T12:31:00-05:00,14.2,81.0,739.4,ok") is None
