"""Dashboard: prediction of the node next to the scraped forecast (R5).

Run from the repository root:
    python -m streamlit run scraper/dashboard.py

It only reads files; it never changes data:
- the forecast log written by scraper/forecast_scraper.py
- the predictions and readings written by scraper/node_listener.py
- the risk threshold in ml/config.yaml

The comparison itself (node class vs. forecast class) is in
scraper/comparison.py; this file only shows the results.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from comparison import compare
from forecast_scraper import DEFAULT_CONFIG, REPO_DIR, load_config, load_forecast_table

RECENT_HOURS = 48          # history shown in the temperature chart
RECENT_PREDICTIONS = 50    # predictions shown in the comparison table


def read_csv_if_exists(path):
    path = Path(path)
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def read_thresholds(config):
    """Risk thresholds from ml/config.yaml ([] while they are undecided)."""
    ml_config = yaml.safe_load(
        (REPO_DIR / config["paths"]["ml_config"]).read_text(encoding="utf-8"))
    return [float(t) for t in (ml_config["labeling"].get("thresholds_c") or [])]

def temperature_chart(data, thresholds):
    """Lines for the node sensors, points for the forecast, risk bands and thresholds."""
    colors = alt.Scale(domain=["Node BME280", "Node probe (DS18B20)", "Forecast (wttr.in)"],
                       range=["#1f77b4", "#2ca02c", "#d95f02"])
    # One fixed vertical range for every layer (the zones and rules must not stretch it)
    low_end = min([data["temperature"].min()] + list(thresholds)) - 1
    y_scale = alt.Scale(domain=[low_end, data["temperature"].max() + 1], nice=False)
    base = alt.Chart(data).encode(
        x=alt.X("time:T", title=None),
        y=alt.Y("temperature:Q", title="Temperature (°C)", scale=y_scale),
        color=alt.Color("source:N", scale=colors, title=None,
                        legend=alt.Legend(orient="top")))
    tooltip = [alt.Tooltip("time:T", title="Time", format="%Y-%m-%d %H:%M"),
               alt.Tooltip("source:N", title="Source"),
               alt.Tooltip("temperature:Q", title="°C", format=".2f")]
    # A gap of more than 2 hours (node off, or hours left out of the dataset) breaks the line
    data = data.sort_values(["source", "time"])
    data["segment"] = (data.groupby("source")["time"].diff() > pd.Timedelta(hours=2)) \
        .groupby(data["source"]).cumsum()
    base = base.properties(data=data)
    node = base.transform_filter(alt.datum.source != "Forecast (wttr.in)") \
        .mark_line(strokeWidth=2, interpolate="monotone").encode(detail="segment:N")
    forecast = base.transform_filter(alt.datum.source == "Forecast (wttr.in)") \
        .mark_point(size=90, filled=True, shape="diamond").encode(tooltip=tooltip)
    hover = base.transform_filter(alt.datum.source != "Forecast (wttr.in)") \
        .mark_circle(size=40, opacity=0).encode(tooltip=tooltip)
    layers = []
    if thresholds:  # shaded risk zones below each threshold + dashed lines
        low = min(thresholds)
        zones = pd.DataFrame({"start": [low_end], "end": [low]})
        layers.append(alt.Chart(zones).mark_rect(color="#c0392b", opacity=0.10, clip=True)
                      .encode(y=alt.Y("start:Q", scale=y_scale), y2="end:Q"))
        rules = pd.DataFrame({"value": thresholds})
        layers.append(alt.Chart(rules).mark_rule(strokeDash=[6, 4], color="#7f8c8d")
                      .encode(y=alt.Y("value:Q", scale=y_scale)))
    return alt.layer(*layers, node, hover, forecast).properties(height=380)


def main():
    st.set_page_config(page_title="Frost node - Tunja", layout="wide")
    st.title("Frost-risk node vs. regional forecast")

    config = load_config(os.environ.get("FROST_SCRAPER_CONFIG", DEFAULT_CONFIG))
    # Optional text shown at the top (for example to label a demo)
    if config.get("banner"):
        st.warning(config["banner"])
    thresholds = read_thresholds(config)
    table = load_forecast_table(config)  # hash table (municipality, time) -> forecast

    predictions = read_csv_if_exists(REPO_DIR / config["paths"]["node_predictions"])
    readings = read_csv_if_exists(REPO_DIR / config["paths"]["node_readings"])
    for frame in (predictions, readings):
        if not frame.empty:
            # "2026-11-12T21:30:00-05:00" -> local time without the offset
            frame["time"] = pd.to_datetime(frame["timestamp"].str.slice(0, 19))

    if thresholds:
        st.caption(f"Risk threshold(s) from ml/config.yaml: {thresholds} °C")
    else:
        st.warning("The risk threshold is not set in ml/config.yaml. The forecast "
                   "is shown, but it cannot be turned into a risk class yet.")

    # ---- 0. last reading of the node (live with the logger) ----
    st.header("Last reading of the node")
    if readings.empty:
        st.info("No readings yet. Run scraper/node_listener.py with the node connected.")
    else:
        last = readings.iloc[-1]
        columns = st.columns(5)
        columns[0].metric("Time", str(last["time"]))
        columns[1].metric("BME280 (°C)", f"{last['temperature_c']:.2f}")
        reference = last.get("reference_temperature_c")
        columns[2].metric("Probe (°C)", "–" if pd.isna(reference) else f"{reference:.2f}")
        columns[3].metric("Humidity (%)", f"{last['humidity_pct']:.1f}")
        columns[4].metric("Pressure (hPa)", f"{last['pressure_hpa']:.1f}")
        st.caption(f"{len(readings)} readings loaded")

    # ---- 1. last prediction of the node ----
    st.header("Last prediction of the node")
    if predictions.empty:
        st.info("No predictions yet. Run scraper/node_listener.py with the node "
                "running firmware/inference.")
    else:
        last = predictions.iloc[-1]
        columns = st.columns(3)
        columns[0].metric("Time", str(last["time"]))
        columns[1].metric("Predicted class", int(last["predicted_class"]))
        columns[2].metric("Probabilities (class 0; 1; ...)", str(last["probabilities"]))

    # ---- 2. regional forecast ----
    st.header(f"Forecast for {config['municipality']} (scraped)")
    forecast = pd.DataFrame(
        [{"forecast time": key[1], "temperature (C)": value["temperature_c"],
          "feels like (C)": value["feels_like_c"], "scraped at": value["scraped_at"]}
         for key, value in table.items() if key[0] == config["municipality"]])
    if forecast.empty:
        st.info("No forecast yet. Run scraper/forecast_scraper.py.")
    else:
        forecast["time"] = pd.to_datetime(forecast["forecast time"])
        forecast = forecast.sort_values("time")
        upcoming = forecast[forecast["time"] >= datetime.now()]
        st.caption(f"Last scrape: {forecast['scraped at'].max()} · "
                   f"{len(table)} forecast times stored")
        st.dataframe(upcoming.drop(columns="time"), hide_index=True)
        st.caption("The page only gives 09:00, 12:00, 18:00 and 21:00. The hours "
                   "of the daily minimum (before sunrise) are not available.")

    # ---- 3. when they do not agree ----
    st.header("Node vs. forecast")
    if predictions.empty or forecast.empty:
        st.info("Both node predictions and a forecast are needed to compare.")
    else:
        comparison = compare(predictions.tail(RECENT_PREDICTIONS), table, config, thresholds)
        counts = comparison["result"].value_counts()
        columns = st.columns(3)
        columns[0].metric("Agree", int(counts.get("agree", 0)))
        columns[1].metric("Disagree", int(counts.get("DISAGREE", 0)))
        columns[2].metric("Not comparable", int(len(comparison) - counts.get("agree", 0)
                                                 - counts.get("DISAGREE", 0)))
        disagreements = comparison[comparison["result"] == "DISAGREE"]
        if not disagreements.empty:
            st.subheader("Disagreements")
            st.dataframe(disagreements, hide_index=True)
        st.subheader(f"Last {len(comparison)} predictions")
        st.dataframe(comparison.iloc[::-1], hide_index=True)

    # ---- 4. recent temperature history ----
    st.header(f"Temperature, last {RECENT_HOURS} hours")
    # The window ends at the newest data (or now), so old captures can be shown too
    end = readings["time"].max() if not readings.empty else datetime.now()
    since = end - timedelta(hours=RECENT_HOURS)
    points = []  # long format: time, temperature, source
    if not readings.empty:
        recent = readings[readings["time"] >= since]
        points.append(pd.DataFrame({"time": recent["time"], "temperature": recent["temperature_c"],
                                    "source": "Node BME280"}))
        if "reference_temperature_c" in recent and recent["reference_temperature_c"].notna().any():
            points.append(pd.DataFrame({"time": recent["time"],
                                        "temperature": recent["reference_temperature_c"],
                                        "source": "Node probe (DS18B20)"}))
    if not forecast.empty:
        # forecast points inside the window, plus the next 24 hours
        recent = forecast[(forecast["time"] >= since) & (forecast["time"] <= end + timedelta(hours=24))]
        points.append(pd.DataFrame({"time": recent["time"],
                                    "temperature": recent["temperature (C)"],
                                    "source": "Forecast (wttr.in)"}))
    data = pd.concat(points).dropna() if points else pd.DataFrame()
    if data.empty:
        st.info("No temperature data in this period yet.")
    else:
        st.altair_chart(temperature_chart(data, thresholds), use_container_width=True)
        st.caption("Hover for values. Dashed lines are the risk thresholds of "
                   "ml/config.yaml; the red area is the risk class.")

    # Optional automatic refresh, for a live demo (scraper/config.yaml)
    refresh_seconds = int(config.get("refresh_seconds") or 0)
    if refresh_seconds > 0:
        time.sleep(refresh_seconds)
        st.rerun()


main()
