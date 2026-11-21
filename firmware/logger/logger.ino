// Data logger firmware for the frost-risk node (ESP32-S3 DevKitC-1).
//
// Every SAMPLE_INTERVAL_MINUTES it reads the BME280 and the reference probe
// (DS18B20, optional) and appends one CSV row to a file in the flash memory
// (LittleFS):
//   timestamp_iso,temperature_c,humidity_pct,pressure_hpa,
//   reference_temperature_c,status
// status is "ok" or "sensor_error" and refers to the BME280. The program
// never stops on a sensor failure: the row is saved as sensor_error and the
// sensor is retried later. A missing probe only writes nan in its column.
//
// Serial commands (one per line, 115200 baud):
//   SETTIME <epoch>  set the clock (seconds since 1970-01-01 UTC)
//   STATUS           rows saved, free space, current time, sensor state
//   DUMP             print the whole CSV file
//   CLEAR            delete all saved rows
//   TEST             check the sensor chip ID (0x60 BME280, 0x58 BMP280)
//                    and whether the reference probe answers
//   SAMPLE           take one extra reading right now
//   HELP             list the commands
//
// Lines starting with "#" are messages for humans. Every other line printed
// by the node is a CSV row.
//
// This firmware only logs data. It does not run the model.

#include <Wire.h>
#include <LittleFS.h>
#include <sys/time.h>
#include <Adafruit_BME280.h>

#include "config.h"

#if USE_REFERENCE_PROBE
#include <OneWire.h>
#include <DallasTemperature.h>
OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature probe(&oneWire);
#endif

#if USE_WIFI_NTP
#include <WiFi.h>
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "USE_WIFI_NTP is 1 but secrets.h is missing: copy secrets.example.h to secrets.h and write your Wi-Fi name and password, or set USE_WIFI_NTP to 0 in config.h"
#endif
#endif

// Chip identification register of Bosch sensors and its known values
const uint8_t CHIP_ID_REGISTER = 0xD0;
const uint8_t CHIP_ID_BME280 = 0x60;  // temperature + humidity + pressure
const uint8_t CHIP_ID_BMP280 = 0x58;  // temperature + pressure, NO humidity

// Any date before this one means "the clock was never set"
// (1577836800 = 2020-01-01 00:00:00 UTC).
const time_t EARLIEST_VALID_EPOCH = 1577836800;

const unsigned long SAMPLE_INTERVAL_MS = SAMPLE_INTERVAL_MINUTES * 60UL * 1000UL;

Adafruit_BME280 bme;
bool sensorReady = false;
bool storageReady = false;
unsigned long rowsSaved = 0;
unsigned long lastSampleMs = 0;
String commandLine = "";

// ---------------------------------------------------------------- clock ----

bool isClockSet() {
  return time(nullptr) >= EARLIEST_VALID_EPOCH;
}

void setClock(time_t epoch) {
  struct timeval now = {epoch, 0};
  settimeofday(&now, nullptr);
}

// Writes the local time as ISO 8601, for example 2026-11-12T21:30:00-05:00
String currentTimestamp() {
  if (!isClockSet()) {
    return "TIME_NOT_SET";
  }
  time_t localEpoch = time(nullptr) + UTC_OFFSET_SECONDS;
  struct tm parts;
  gmtime_r(&localEpoch, &parts);
  char text[20];
  strftime(text, sizeof(text), "%Y-%m-%dT%H:%M:%S", &parts);
  return String(text) + UTC_OFFSET_TEXT;
}

#if USE_WIFI_NTP
// Connects to Wi-Fi, asks an NTP server for the time and turns Wi-Fi off.
void syncClockWithNtp() {
  Serial.println("# Connecting to Wi-Fi for NTP...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(250);
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("# WARNING: no Wi-Fi. Use SETTIME <epoch> instead.");
  } else {
    configTime(0, 0, NTP_SERVER, NTP_SERVER_2, NTP_SERVER_3);  // clock in UTC
    start = millis();
    while (!isClockSet() && millis() - start < NTP_TIMEOUT_MS) {
      delay(250);
    }
    if (isClockSet()) {
      Serial.println("# Clock set by NTP");
    } else {
      Serial.println("# WARNING: NTP did not answer. Use SETTIME <epoch>.");
    }
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
}
#endif

// --------------------------------------------------------------- sensor ----

// Reads the chip ID at the BME280 address. Returns 0 if nobody answers.
uint8_t readChipId() {
  Wire.beginTransmission(BME280_I2C_ADDRESS);
  Wire.write(CHIP_ID_REGISTER);
  if (Wire.endTransmission() != 0) {
    return 0;
  }
  Wire.requestFrom(BME280_I2C_ADDRESS, (uint8_t)1);
  if (Wire.available() < 1) {
    return 0;
  }
  return Wire.read();
}

// Test mode: reports which sensor is connected. Returns true for a BME280.
bool testSensor() {
  uint8_t chipId = readChipId();
  Serial.print("# TEST chip ID at 0x");
  Serial.print(BME280_I2C_ADDRESS, HEX);
  Serial.print(": 0x");
  Serial.println(chipId, HEX);
  if (chipId == CHIP_ID_BME280) {
    Serial.println("# TEST OK: the sensor is a BME280");
    return true;
  }
  if (chipId == CHIP_ID_BMP280) {
    Serial.println("# TEST FAIL: the sensor is a BMP280. It has NO humidity.");
  } else if (chipId == 0) {
    Serial.println("# TEST FAIL: no sensor answers. Check the wiring.");
  } else {
    Serial.println("# TEST FAIL: unknown chip. A BME280 must answer 0x60.");
  }
  return false;
}

// Tries to start the BME280. Safe to call again after a failure.
void startSensor() {
  sensorReady = false;
  if (readChipId() != CHIP_ID_BME280) {
    return;
  }
  if (!bme.begin(BME280_I2C_ADDRESS, &Wire)) {
    return;
  }
  // Forced mode: the sensor measures only when asked and sleeps the rest of
  // the time. This avoids self-heating, which would bias the temperature.
  bme.setSampling(Adafruit_BME280::MODE_FORCED,
                  Adafruit_BME280::SAMPLING_X1,   // temperature
                  Adafruit_BME280::SAMPLING_X1,   // pressure
                  Adafruit_BME280::SAMPLING_X1,   // humidity
                  Adafruit_BME280::FILTER_OFF);
  sensorReady = true;
}

bool isInRange(float value, float minimum, float maximum) {
  // A NaN value fails both comparisons, so it is reported as invalid.
  return value >= minimum && value <= maximum;
}

// Reads the reference probe. Returns NAN if it is disabled or does not answer.
float readReferenceC() {
#if USE_REFERENCE_PROBE
  probe.requestTemperatures();  // waits for the conversion (up to 0.75 s)
  float value = probe.getTempCByIndex(0);
  // DEVICE_DISCONNECTED_C (-127) means no probe. 85.0 is the value a DS18B20
  // returns after power-on before any real conversion, so it is not trusted.
  if (value == DEVICE_DISCONNECTED_C || value == 85.0f ||
      !isInRange(value, -55.0f, 125.0f)) {
    return NAN;
  }
  return value;
#else
  return NAN;
#endif
}

// Test mode for the probe: how many 1-Wire temperature probes answer.
void testProbe() {
#if USE_REFERENCE_PROBE
  probe.begin();  // searches the 1-Wire bus again
  int count = probe.getDeviceCount();
  Serial.print("# TEST reference probes on GPIO");
  Serial.print(ONE_WIRE_PIN);
  Serial.print(": ");
  Serial.println(count);
  if (count == 0) {
    Serial.println("# TEST probe not found: check the wiring and the 4.7 kOhm resistor");
  } else {
    Serial.print("# TEST probe reading (C): ");
    Serial.println(readReferenceC(), 2);
  }
#else
  Serial.println("# TEST reference probe disabled (USE_REFERENCE_PROBE 0)");
#endif
}

// -------------------------------------------------------------- storage ----

unsigned long countSavedRows();

// Creates the CSV file with its header if it does not exist.
// If the file was written by an older firmware with other columns:
//   - with no data rows, it is simply started again with the new header;
//   - with data rows, it is kept untouched and a warning asks to download it
//     (DUMP) and then empty it (CLEAR), so no data is lost.
void createLogFileIfMissing() {
  if (LittleFS.exists(LOG_FILE_PATH)) {
    File file = LittleFS.open(LOG_FILE_PATH, FILE_READ);
    String header = file ? file.readStringUntil('\n') : String("");
    if (file) {
      file.close();
    }
    header.trim();
    if (header == LOG_FILE_HEADER) {
      return;
    }
    if (countSavedRows() > 0) {
      Serial.println("# WARNING: the log has the columns of an older firmware.");
      Serial.println("# Download it with DUMP, then send CLEAR to start the new format.");
      return;
    }
    LittleFS.remove(LOG_FILE_PATH);
  }
  File file = LittleFS.open(LOG_FILE_PATH, FILE_WRITE);
  if (file) {
    file.println(LOG_FILE_HEADER);
    file.close();
  }
}

// Counts the data rows already in the file (the header is not counted).
unsigned long countSavedRows() {
  File file = LittleFS.open(LOG_FILE_PATH, FILE_READ);
  if (!file) {
    return 0;
  }
  unsigned long lines = 0;
  while (file.available()) {
    if (file.read() == '\n') {
      lines++;
    }
  }
  file.close();
  return lines > 0 ? lines - 1 : 0;
}

bool appendRow(const String &row) {
  File file = LittleFS.open(LOG_FILE_PATH, FILE_APPEND);
  if (!file) {
    return false;
  }
  size_t written = file.println(row);
  file.close();
  return written > 0;  // 0 means the flash is full
}

// ------------------------------------------------------------- sampling ----

void takeSample() {
#if USE_WIFI_NTP
  // The Wi-Fi may come back later than the node (for example after a power
  // cut), so while the clock is not set, try NTP again before each reading.
  if (!isClockSet()) {
    syncClockWithNtp();
  }
#endif
  float temperatureC = NAN;
  float humidityPct = NAN;
  float pressureHpa = NAN;

  if (!sensorReady) {
    startSensor();  // the sensor may have been connected after boot
  }
  if (sensorReady && bme.takeForcedMeasurement()) {
    temperatureC = bme.readTemperature();
    humidityPct = bme.readHumidity();
    pressureHpa = bme.readPressure() / 100.0f;  // Pa -> hPa
  }

  bool valid =
      isInRange(temperatureC, MIN_VALID_TEMPERATURE_C, MAX_VALID_TEMPERATURE_C) &&
      isInRange(humidityPct, MIN_VALID_HUMIDITY_PCT, MAX_VALID_HUMIDITY_PCT) &&
      isInRange(pressureHpa, MIN_VALID_PRESSURE_HPA, MAX_VALID_PRESSURE_HPA);
  if (!valid) {
    sensorReady = false;  // start the sensor again before the next reading
  }

  float referenceC = readReferenceC();

  String row = currentTimestamp() + "," +
               String(temperatureC, 2) + "," +
               String(humidityPct, 2) + "," +
               String(pressureHpa, 2) + "," +
               String(referenceC, 2) + "," +
               (valid ? "ok" : "sensor_error");
  Serial.println(row);

  // A row without a real date cannot be assigned to a day, so it is not saved.
  if (!isClockSet()) {
    Serial.println("# WARNING: clock not set, row NOT saved. Send SETTIME <epoch>.");
    return;
  }
  if (!storageReady) {
    Serial.println("# WARNING: flash storage not available, row NOT saved.");
    return;
  }
  if (appendRow(row)) {
    rowsSaved++;
  } else {
    Serial.println("# WARNING: could not write the row (flash full?).");
  }
}

// ------------------------------------------------------------- commands ----

void printStatus() {
  Serial.print("# STATUS rows_saved=");
  Serial.println(rowsSaved);
  if (storageReady) {
    Serial.print("# STATUS flash_used_bytes=");
    Serial.println(LittleFS.usedBytes());
    Serial.print("# STATUS flash_free_bytes=");
    Serial.println(LittleFS.totalBytes() - LittleFS.usedBytes());
  } else {
    Serial.println("# STATUS flash storage NOT available");
  }
  Serial.print("# STATUS time=");
  Serial.println(currentTimestamp());
  Serial.print("# STATUS sensor=");
  Serial.println(sensorReady ? "ok" : "not_ready");
  Serial.print("# STATUS sample_interval_minutes=");
  Serial.println(SAMPLE_INTERVAL_MINUTES);
}

void dumpLogFile() {
  Serial.println("# DUMP BEGIN");
  File file = LittleFS.open(LOG_FILE_PATH, FILE_READ);
  if (file) {
    while (file.available()) {
      Serial.write(file.read());
    }
    file.close();
  }
  Serial.println("# DUMP END");
}

void clearLogFile() {
  LittleFS.remove(LOG_FILE_PATH);
  createLogFileIfMissing();
  rowsSaved = 0;
  Serial.println("# CLEAR done: all rows deleted");
}

void runCommand(String line) {
  line.trim();
  if (line.length() == 0) {
    return;
  }
  String upper = line;
  upper.toUpperCase();

  if (upper.startsWith("SETTIME ")) {
    long long epoch = atoll(line.substring(8).c_str());
    if (epoch < EARLIEST_VALID_EPOCH) {
      Serial.println("# ERROR: SETTIME needs seconds since 1970, e.g. SETTIME 1794000000");
      return;
    }
    setClock((time_t)epoch);
    Serial.print("# SETTIME done: ");
    Serial.println(currentTimestamp());
  } else if (upper == "STATUS") {
    printStatus();
  } else if (upper == "DUMP") {
    dumpLogFile();
  } else if (upper == "CLEAR") {
    clearLogFile();
  } else if (upper == "TEST") {
    testSensor();
    testProbe();
  } else if (upper == "SAMPLE") {
    takeSample();  // extra reading right now, useful to test without waiting
  } else if (upper == "HELP") {
    Serial.println("# Commands: SETTIME <epoch>, STATUS, DUMP, CLEAR, TEST, SAMPLE, HELP");
  } else {
    Serial.print("# ERROR: unknown command: ");
    Serial.println(line);
  }
}

// Collects the characters typed on the serial port until the end of the line.
void readSerialCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      runCommand(commandLine);
      commandLine = "";
    } else if (commandLine.length() < 64) {
      commandLine += c;
    }
  }
}

// ----------------------------------------------------------------- main ----

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(1000);  // give the serial port time to open
  Serial.println("# Frost node - data logger firmware");

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  if (testSensor()) {
    startSensor();
  }
  testProbe();  // also starts the probe library

  // true = format the flash partition the first time it is used
  storageReady = LittleFS.begin(true);
  if (storageReady) {
    createLogFileIfMissing();
    rowsSaved = countSavedRows();
  } else {
    Serial.println("# ERROR: could not start LittleFS. Rows will not be saved.");
  }

#if USE_WIFI_NTP
  syncClockWithNtp();
#endif

  printStatus();
  Serial.print("# Columns: ");
  Serial.println(LOG_FILE_HEADER);

  // Take the first sample immediately instead of waiting a full interval
  lastSampleMs = millis() - SAMPLE_INTERVAL_MS;
}

void loop() {
  readSerialCommands();

  // millis() subtraction keeps working when millis() overflows (~49 days)
  if (millis() - lastSampleMs >= SAMPLE_INTERVAL_MS) {
    lastSampleMs += SAMPLE_INTERVAL_MS;
    takeSample();
  }
  delay(10);
}
