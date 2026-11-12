// I2C bus scanner: a wiring diagnostic tool for the frost-risk node.
//
// Every 5 seconds it tries every I2C address and prints the ones that answer.
// Expected devices: BME280 at 0x76 (or 0x77) and INA219 at 0x40.
// For 0x76 / 0x77 it also prints the chip ID: 0x60 = BME280, 0x58 = BMP280.

#include <Wire.h>

const int I2C_SDA_PIN = 8;
const int I2C_SCL_PIN = 9;
const uint8_t CHIP_ID_REGISTER = 0xD0;

// Reads one register of a device. Returns 0 if the read fails.
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

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
}

void loop() {
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
  delay(5000);
}
