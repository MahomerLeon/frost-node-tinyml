// Wiring check for the frost-risk node.
//
// Every 5 seconds it lists:
// 1. The I2C devices that answer on SDA=GPIO8 / SCL=GPIO9.
//    Expected: INA219 at 0x40 and BME280 at 0x76 (or 0x77).
//    For 0x76 / 0x77 it also prints the chip ID: 0x60 = BME280, 0x58 = BMP280.
// 2. The 1-Wire devices on GPIO4 (the reference temperature probe).
//    The first byte of a 1-Wire address is the "family code", which tells
//    the kind of chip: 0x28 = DS18B20.

#include <Wire.h>
#include <OneWire.h>

const int I2C_SDA_PIN = 8;
const int I2C_SCL_PIN = 9;
const int ONE_WIRE_PIN = 4;
const uint8_t CHIP_ID_REGISTER = 0xD0;

OneWire oneWire(ONE_WIRE_PIN);

// Reads one register of an I2C device. Returns 0 if the read fails.
uint8_t readRegister(uint8_t address, uint8_t reg) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission() != 0) {
    return 0;
  }
  Wire.requestFrom(address, (uint8_t)1);
  if (Wire.available() < 1) {
    return 0;
  }
  return Wire.read();
}

const char *familyName(uint8_t family) {
  switch (family) {
    case 0x28: return "DS18B20";
    case 0x10: return "DS18S20 or DS1820 (older model)";
    case 0x22: return "DS1822";
    default: return "unknown 1-Wire device";
  }
}

void scanI2c() {
  Serial.println("# I2C scan (SDA=GPIO8, SCL=GPIO9)");
  int found = 0;
  for (uint8_t address = 0x08; address <= 0x77; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      found++;
      Serial.print("FOUND 0x");
      Serial.print(address, HEX);
      if (address == 0x76 || address == 0x77) {
        Serial.print(" chip_id=0x");
        Serial.print(readRegister(address, CHIP_ID_REGISTER), HEX);
      }
      Serial.println();
    }
  }
  Serial.print("# devices found: ");
  Serial.println(found);
}

void scanOneWire() {
  Serial.println("# 1-Wire scan (DATA=GPIO4)");
  uint8_t address[8];
  int found = 0;
  oneWire.reset_search();
  while (oneWire.search(address)) {
    found++;
    Serial.print("FOUND 1-Wire ");
    for (int i = 0; i < 8; i++) {
      if (address[i] < 0x10) {
        Serial.print("0");
      }
      Serial.print(address[i], HEX);
    }
    // The last byte is a checksum of the other seven
    bool valid = OneWire::crc8(address, 7) == address[7];
    Serial.print(" family=0x");
    Serial.print(address[0], HEX);
    Serial.print(" (");
    Serial.print(familyName(address[0]));
    Serial.println(valid ? ")" : ") CRC ERROR: check the wiring");
  }
  Serial.print("# 1-Wire devices found: ");
  Serial.println(found);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
}

void loop() {
  scanI2c();
  scanOneWire();
  delay(5000);
}
