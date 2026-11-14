# Hardware setup: how to connect the node

Step-by-step wiring of the frost-risk node, with a software check after each
step. The connections are the ones of the project wiring diagram
([wiring_diagram_esp32s3.png](wiring_diagram_esp32s3.png)).

Follow the order. Connect one module, check it, and only then add the next
one: if something stops working, the last thing you connected is the cause.

## 1. Parts

| Part | Role |
|---|---|
| ESP32-S3 DevKitC-1 | main board |
| BME280 module | temperature, humidity, pressure (I2C) |
| INA219 module | measures the current and power of the node (I2C) |
| Temperature probe (only if it is a DS18B20) | reference temperature |
| Breadboard and jumper wires | connections |
| USB-C **data** cable | programming and serial port |
| 5 V wall charger (or power bank) | power for the power measurement and the field |
| 4.7 kΩ resistor | pull-up of the DS18B20 data line |

The modules must have their pin headers soldered. A header that is only
pushed through the holes does not make reliable contact.

## 2. Rules before connecting anything

1. **Disconnect the power** (USB cable and charger) every time you move a wire.
2. **The sensors work at 3.3 V.** Connect their VCC to the pin labelled `3V3`,
   never to `5V`.
3. **5 V only travels one path:** charger → INA219 → pin `5V` of the board.
4. **Never connect the PC and the charger at the same time.** To program,
   only the USB cable. To measure power, only the charger through the INA219.
5. **Trust the labels printed on the board**, not the position of a pin in a
   drawing. Boards from different makers place the pins differently.

## 3. The board

The DevKitC-1 has two USB-C connectors:

| Label on the board | Use |
|---|---|
| `UART` (sometimes `COM`) | **Use this one.** Programming and serial monitor. |
| `USB` | Native USB of the chip. Not used in this project. |

Pins used (labels printed next to the pins):

| Label | Function in this project |
|---|---|
| `3V3` | 3.3 V output for the sensors |
| `GND` | ground (the board has several; they are all the same) |
| `8` | I2C data (SDA) |
| `9` | I2C clock (SCL) |
| `4` | data of the DS18B20 probe |
| `5V` | 5 V input when the node is powered from the charger |

Check the board alone first. Connect it to the PC with the `UART` connector
and run:

```
arduino-cli board list
```

Expected: a new port of type `Serial Port (USB)`, for example `COM9`. If no
port appears, the cable is charge-only or the driver of the USB-serial chip
(CH343 or CP2102) is missing. The examples below use `COM9`.

## 4. Step 1: BME280

| BME280 pin | Board pin | Wire colour in the diagram |
|---|---|---|
| VCC (or VIN) | `3V3` | red |
| GND | `GND` | black |
| SDA | `8` | blue |
| SCL | `9` | yellow |
| CSB | `3V3` (selects I2C mode) | red |
| SDO | `GND` (selects address 0x76) | black |

Some modules have only four pins (VCC, GND, SCL, SDA). In that case there is
nothing to connect for CSB and SDO.

Check:

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/i2c_scan
arduino-cli monitor -p COM9 -c baudrate=115200
```

Expected, repeated every 5 seconds:

```
# I2C scan (SDA=GPIO8, SCL=GPIO9)
FOUND 0x76 chip_id=0x60
# devices found: 1
```

| What you see | Meaning | What to do |
|---|---|---|
| `chip_id=0x60` | it is a real BME280 | continue |
| `chip_id=0x58` | it is a BMP280: it has **no humidity** | the project needs a BME280; replace the module |
| `FOUND 0x77` | the module uses the other address | connect SDO to `GND`, or set `BME280_I2C_ADDRESS = 0x77` in both `config.h` files |
| `# devices found: 0` | the sensor does not answer | see section 9 |

Stop the monitor with Ctrl+C.

## 5. Step 2: INA219, I2C side

The INA219 shares the same two I2C wires as the BME280. On a breadboard, put
both SDA wires in the same row as pin `8`, and both SCL wires in the same row
as pin `9`.

| INA219 pin | Board pin | Wire colour in the diagram |
|---|---|---|
| VCC | `3V3` | red |
| GND | `GND` | black |
| SDA | `8` (same row as the BME280 SDA) | blue |
| SCL | `9` (same row as the BME280 SCL) | yellow |

Leave `Vin+` and `Vin-` unconnected for now.

Check: open the monitor again (the scanner is still loaded).

```
arduino-cli monitor -p COM9 -c baudrate=115200
```

Expected:

```
FOUND 0x40
FOUND 0x76 chip_id=0x60
# devices found: 2
```

`0x40` is the INA219. If the BME280 disappeared when you added the INA219,
the two modules are sharing a wrong row: check SDA and SCL again.

## 6. Step 3: INA219, power side

This step is only needed to measure the consumption of the node (R7). For
data capture and inference the node can simply be powered by USB.

The INA219 measures the current that flows **through** it, from `Vin+` to
`Vin-`. It is placed in series in the 5 V line that feeds the board:

```
charger +5 V ──> INA219 Vin+        INA219 Vin- ──> board pin 5V
charger GND  ─────────────────────────────────────> board pin GND
```

| From | To | Wire colour in the diagram |
|---|---|---|
| Charger +5 V | INA219 `Vin+` | orange |
| INA219 `Vin-` | Board pin `5V` | orange |
| Charger GND | Board pin `GND` | black |

To reach the two wires of the charger you need a USB breakout board or a USB
cable with the wires exposed. This part is not specified in the project
documents: **before connecting, confirm with a multimeter which wire is +5 V
and which is GND.** Reversed polarity can damage the board.

Because the INA219 sits before the `5V` pin, it measures everything the board
takes, including the losses of its voltage regulator. Say so in the report.

When the board is powered from the PC (USB cable), no current flows through
the INA219 and it reads about zero. That is normal.

### Measuring power

No PC is connected during the measurement, so the benchmark must start by
itself and save its result:

1. In `firmware/inference/config.h` set `#define RUN_BENCHMARK_AT_BOOT 1`.
2. With the USB cable connected (charger disconnected), upload the sketch:

   ```
   arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/inference
   ```

3. Disconnect the USB cable. Connect the charger through the INA219.
   Wait one minute: the benchmark starts 10 seconds after power-on and saves
   its report in the flash memory.
4. Disconnect the charger. Connect the USB cable again, open the monitor and
   type `LASTBENCH`.

Expected: the saved report, including lines such as
`BENCHMARK,power_idle_mw,...`, `BENCHMARK,power_inference_mw,...` and
`BENCHMARK,energy_per_inference_mj,...`. If it says
`power not measured: INA219 not found`, check step 2.

5. Set `RUN_BENCHMARK_AT_BOOT` back to `0` and upload again, so the node does
   not repeat the benchmark at every start.

This procedure has been written and compiles, but it has **not been run on
the board yet**.

## 7. Step 4: temperature probe (only if it is a DS18B20)

Connect it only after confirming on its label or packaging that the probe is
a DS18B20. Another kind of probe needs different wiring.

| Probe wire | Board pin | Wire colour in the diagram |
|---|---|---|
| Red | `3V3` | red |
| Black | `GND` | black |
| Yellow (data) | `4` | green |

Add the 4.7 kΩ resistor between the data wire (pin `4`) and `3V3`. Without
it the probe does not answer.

There is no firmware yet that reads the probe, so there is no software check
for this step.

## 8. Using the node once it is wired

Logger (builds the own dataset), with the USB cable connected:

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/logger
arduino-cli monitor -p COM9 -c baudrate=115200
```

Type `TEST`. Expected: `# TEST OK: the sensor is a BME280`. Then set the
clock and download the readings with `python ml/serial_dump.py COM9`. The
commands of each firmware are listed in [firmware/README.md](../firmware/README.md).

In the field the node can be powered by the charger or a power bank on the
`UART` connector. Without Wi-Fi the clock is lost on every power cut, and
readings are not saved until the clock is set again: see the notes on the
clock in the firmware README.

## 9. Troubleshooting

| Symptom | Things to check, in this order |
|---|---|
| No serial port appears | USB cable is charge-only; cable is in the `USB` connector instead of `UART`; driver of the USB-serial chip missing |
| `# devices found: 0` | VCC really on `3V3` and GND on `GND`; SDA on `8` and SCL on `9` (not swapped); headers soldered; wires firmly in the breadboard; on a long breadboard, the power rails may be split in the middle |
| Only one of the two modules is found | the missing module's SDA/SCL are not in the same rows as pins `8` and `9` |
| `chip_id=0x58` | the module is a BMP280, not a BME280 |
| The board resets or gets hot | disconnect at once; look for VCC connected to `5V` or a short between `3V3` and `GND` |
| INA219 reads about 0 mA | the board is powered by the PC, or `Vin+` / `Vin-` are not in series with the supply |
| Negative current | `Vin+` and `Vin-` are swapped |

## 10. Not defined yet

- **Raspberry Pi Pico** (comparison for R7): no firmware or wiring has been
  defined for it.
- **How the charger wires reach the INA219** (breakout or cut cable).
- **Field enclosure**: box, sun shield and the 1.5 m mounting height are in
  [capture_protocol.md](capture_protocol.md).
