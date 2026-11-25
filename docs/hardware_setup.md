# Hardware setup: how to connect the node

Step-by-step wiring of the frost-risk node, with a software check after each
step. The connections are the ones of the project wiring diagram
([wiring_diagram_esp32s3.png](wiring_diagram_esp32s3.png)). The Raspberry Pi
Pico used for the R7 comparison is in section 10
([wiring_diagram_pico.png](wiring_diagram_pico.png)).

Follow the order. Connect one module, check it, and only then add the next
one: if something stops working, the last thing you connected is the cause.

## 1. Parts

| Part | Role |
|---|---|
| ESP32-S3 DevKitC-1 | main board |
| BME280 module | temperature, humidity, pressure (I2C) |
| INA219 module | measures the current and power of the node (I2C) |
| Temperature probe (only if it is a DS18B20) | reference temperature |
| Raspberry Pi Pico (RP2040) and its micro-USB data cable | smaller board for the R7 comparison (section 10) |
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

**This measurement was not done in the project.** Known problem of the steps
below: when the USB cable is connected again (step 4) the board restarts and,
10 seconds later, the benchmark runs again and **overwrites** the report saved
with the charger. The firmware has to keep the earlier report before this
procedure can work.

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

Check: the wiring scanner also looks for the probe.

```
arduino-cli compile --fqbn esp32:esp32:esp32s3 -u -p COM9 firmware/i2c_scan
arduino-cli monitor -p COM9 -c baudrate=115200
```

Expected, after the I2C lines:

```
# 1-Wire scan (DATA=GPIO4)
FOUND 1-Wire 28xxxxxxxxxxxxxx family=0x28 (DS18B20)
# 1-Wire devices found: 1
```

Family `0x28` confirms that the probe is a DS18B20. `devices found: 0` means
the data wire or the 4.7 kΩ resistor is missing; `CRC ERROR` usually means
a loose contact.

Then, with the logger loaded, the command `TEST` prints the probe reading,
and every row of the log has it in the column `reference_temperature_c`.

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

## 10. Raspberry Pi Pico (RP2040), for the R7 comparison

The Pico is not part of the field node. It runs the same model to show that
the ESP32-S3 is not oversized (R7).

**Both boards at the same time.** The Pico benchmark (latency, flash, RAM,
tensor arena) and its validation against the PC do not use any sensor. So
the Pico can be connected to the PC by its micro-USB cable, with nothing
else, while the ESP32-S3 keeps the sensors and its own USB cable. Each board
gets its own COM port. Diagram:
[wiring_diagram_both.png](wiring_diagram_both.png).

The sensors are **moved** to the Pico only to measure its power (the INA219
must be in its supply) or to run its `TEST` and `SAMPLE` commands. The same
BME280 or INA219 is never connected to both boards at once: that would put
two controllers on one I2C bus and join two 3.3 V supplies.

Diagram with the sensors on the Pico: [wiring_diagram_pico.png](wiring_diagram_pico.png).

On the Pico the pins are numbered 1 to 40 around the board (pin 1 is next to
the USB connector, on the side of the label `GP0`). The table gives both the
function label and the physical number; check them against the pinout printed
on the back of your board.

| From | Pico pin | Wire colour in the diagram |
|---|---|---|
| BME280 VCC, BME280 CSB, INA219 VCC | `3V3(OUT)`, pin 36 | red |
| BME280 GND, BME280 SDO, INA219 GND | `GND`, pin 38 | black |
| BME280 SDA, INA219 SDA | `GP4`, pin 6 | blue |
| BME280 SCL, INA219 SCL | `GP5`, pin 7 | yellow |
| Charger +5 V | INA219 `Vin+` | orange |
| INA219 `Vin-` | `VSYS`, pin 39 | orange |
| Charger GND | `GND`, pin 28 (any GND pin) | black |

Notes:

- **Never connect a sensor to `VBUS` (pin 40) or `VSYS` (pin 39).** Those
  carry up to 5 V. The sensors go to `3V3(OUT)`.
- The Pico accepts its supply on `VSYS` (from 1.8 to 5.5 V according to the
  Raspberry Pi Pico datasheet), so the 5 V of the charger goes there through
  the INA219. Do not connect the USB cable at the same time.
- The Pico has no `UART` / `USB` choice: it has one micro-USB connector, used
  for programming and for the serial port.

Check, with the USB cable connected and the charger disconnected:

```
arduino-cli compile --fqbn rp2040:rp2040:rpipico:flash=2097152_65536 --build-property "compiler.cpp.extra_flags=-include stdint.h" -u -p COM12 firmware/pico_benchmark
arduino-cli monitor -p COM12 -c baudrate=115200
```

Replace `COM12` with the port of the Pico (`arduino-cli board list`). The very
first upload may need the BOOTSEL method: unplug the Pico, hold the `BOOTSEL`
button, plug it in, release the button, and upload again. `firmware/pico_benchmark`
needs `model_data.h`, which is created by `python ml/convert_tflite.py`,
and the extra compiler option explained in `firmware/README.md`.

Type `STATUS`. Expected: `sensor=ok` and `power_meter=ok`. Type `TEST`.
Expected: `# TEST OK: the sensor is a BME280`.

Power measurement on the Pico is the same as on the ESP32-S3 (section 6):
set `RUN_BENCHMARK_AT_BOOT 1` in `firmware/pico_benchmark/config.h`, upload,
power the Pico through the INA219 for one minute, reconnect the USB cable and
type `LASTBENCH`.

None of these steps has been run on a real Pico yet.

## 11. Not defined yet

- **How the charger wires reach the INA219** (breakout or cut cable).
- **Field enclosure**: box, sun shield and the 1.5 m mounting height are in
  [capture_protocol.md](capture_protocol.md).
