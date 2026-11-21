// Settings of the data logger firmware.
// Change values here, not inside logger.ino.

#pragma once

#include <Arduino.h>

// ---- Sensor (I2C) ----
const int I2C_SDA_PIN = 8;
const int I2C_SCL_PIN = 9;
const uint8_t BME280_I2C_ADDRESS = 0x76;

// ---- Sampling ----
// Minutes between two readings. Starting value, to be confirmed in the data
// capture protocol (R4).
const unsigned long SAMPLE_INTERVAL_MINUTES = 5;

// ---- Serial port ----
const unsigned long SERIAL_BAUD_RATE = 115200;

// ---- Clock ----
// How the node gets the date and time:
//   0 = serial command "SETTIME <epoch>" (sent by ml/serial_dump.py)
//   1 = NTP over Wi-Fi. Needs a file secrets.h with the Wi-Fi name and
//       password: copy secrets.example.h to secrets.h and edit it.
//       secrets.h is listed in .gitignore and must never be committed.
// In both cases SETTIME still works, and the internal clock of the ESP32
// keeps the time between readings. The clock is LOST on reset or power loss.
#define USE_WIFI_NTP 1

// Three NTP servers: if the first does not answer, the others are used.
const char NTP_SERVER[] = "pool.ntp.org";
const char NTP_SERVER_2[] = "time.google.com";
const char NTP_SERVER_3[] = "time.cloudflare.com";
const unsigned long WIFI_TIMEOUT_MS = 15000;
// On the home network the first answer took 16.5 s (measured 2026-11-20),
// so the node waits up to 30 s.
const unsigned long NTP_TIMEOUT_MS = 30000;

// Local time zone used to write the timestamps (Colombia: UTC-5, no DST).
// Both values must describe the same offset.
const long UTC_OFFSET_SECONDS = -5 * 3600;
const char UTC_OFFSET_TEXT[] = "-05:00";

// ---- Reference temperature probe (DS18B20 on 1-Wire, optional) ----
// Used only to calibrate the BME280 (see docs/capture_protocol.md); the
// model does not use it. If no probe answers, the column is written as nan.
// Set to 0 to stop reading it.
#define USE_REFERENCE_PROBE 1
const int ONE_WIRE_PIN = 4;

// ---- Storage ----
// status refers to the BME280 only; the probe has its own column.
const char LOG_FILE_PATH[] = "/log.csv";
const char LOG_FILE_HEADER[] =
    "timestamp_iso,temperature_c,humidity_pct,pressure_hpa,reference_temperature_c,status";

// ---- Valid ranges ----
// Measurement limits of the BME280 taken from its datasheet. A reading
// outside them is a sensor failure. These are NOT agronomic thresholds.
const float MIN_VALID_TEMPERATURE_C = -40.0f;
const float MAX_VALID_TEMPERATURE_C = 85.0f;
const float MIN_VALID_HUMIDITY_PCT = 0.0f;
const float MAX_VALID_HUMIDITY_PCT = 100.0f;
const float MIN_VALID_PRESSURE_HPA = 300.0f;
const float MAX_VALID_PRESSURE_HPA = 1100.0f;
