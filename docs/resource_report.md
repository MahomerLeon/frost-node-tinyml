# Resource report (R7)

Status: **no final measurements yet.** The final numbers must be measured
with the real model (trained with a decided threshold and own data), and the
measurement must be repeatable during the presentation.

## How the measurements are taken

Everything comes from the `BENCHMARK` command of `firmware/inference`
(procedure in [firmware/README.md](../firmware/README.md); power in
[hardware_setup.md](hardware_setup.md), section 6).

| Metric | Unit | How it is obtained | Total used for the percentage |
|---|---|---|---|
| Program size | bytes, % | `ESP.getSketchSize()`; also printed by the compiler | program partition, and whole flash chip |
| Model size | bytes, % | length of the array in `model_data.h` | whole flash chip |
| Tensor arena | bytes, % | `interpreter->arena_used_bytes()` | arena reserved (`TENSOR_ARENA_BYTES`) |
| Heap, peak use | bytes, % | heap size minus `ESP.getMinFreeHeap()` | heap size |
| Stack, peak use | bytes, % | stack size minus the high-water mark of the loop task | stack of the loop task |
| Latency per inference | ms | `micros()` around each `Invoke()`, mean and standard deviation over 200 runs | — |
| CPU load | % | mean latency divided by the period between inferences (30 min) | — |
| Power | mA, mW | INA219 in series with the 5 V supply, averaged over 50 readings, idle and while running inferences without pause | — |
| Energy per inference | mJ | power while inferring × mean latency | — |

Limits of the method:

- The CPU load is an estimate from the latency, not a measurement with the
  profiling tools of the manufacturer SDK.
- The INA219 is before the 5 V pin, so power includes the losses of the
  voltage regulator of the board.
- Latency and power are measured with the CPU at 240 MHz and Wi-Fi off.

## Pipeline test (not a project result)

Measured on the board on 2026-11-12 with a **placeholder model** (20 inputs,
hidden layers of 16 and 8 units, 2 classes), trained with a placeholder
threshold only to check that the code and the measurement work.

| Metric | Value | Percentage |
|---|---|---|
| Latency, 200 runs | mean 0.050 ms, std 0.014 ms | — |
| Tensor arena | 876 bytes of 16 384 reserved | 5.35 % |
| Model | 3 152 bytes | 0.02 % of the 16 MB flash |
| Program | 418 896 bytes | 31.96 % of the 1 310 720 byte program partition; 2.50 % of the flash |
| Heap, peak use | 49 268 of 369 936 bytes | 13.32 % |
| Stack, power | not measured | — |

Same placeholder model, current firmware (flash storage and power meter
added), measured on 2026-11-17 without sensors:

| Metric | Value | Percentage |
|---|---|---|
| Latency, 200 runs | mean 0.050 ms, std 0.015 ms | — |
| Program | 471 664 bytes | 35.99 % of the program partition; 2.81 % of the flash |
| Heap, peak use | 52 192 of 369 488 bytes | 14.13 % |
| Stack, peak use | 2 528 of 8 192 bytes | 30.86 % |
| Power | not measured (no INA219 connected) | — |

## Final measurements

To fill in with the real model.

| Metric | Value | Percentage |
|---|---|---|
| Program size | | |
| Model size | | |
| Tensor arena | | |
| Heap, peak use | | |
| Stack, peak use | | |
| Latency (mean, std, runs) | | |
| CPU load | | |
| Power idle / inferring | | |
| Energy per inference | | |
| F1 on the device vs. float model | | |

## Not oversizing the device: ESP32-S3 vs. Raspberry Pi Pico

The course criterion: under 30 % of Flash and RAM with latency far below what
the application needs suggests trying a more limited device; over 80 %
suggests a larger one or more optimization.

The more limited board is a Raspberry Pi Pico (RP2040: two Cortex-M0+ cores,
264 KB SRAM, 2 MB flash, no Wi-Fi). The RP2040 core 6.3.2 runs it at 200 MHz
by default, as the benchmark reported; the Arduino option "CPU Speed" can set
another frequency if the comparison needs it. `firmware/pico_benchmark`
runs the same int8 model with the same `BENCHMARK` command and the same
report names, so the two reports can be put side by side. The benchmark needs
no sensor, so the Pico can run it while the ESP32-S3 keeps its sensors; the
INA219 is moved to the Pico only to measure its power (wiring in
[hardware_setup.md](hardware_setup.md), section 10).

Differences in how the two boards are measured:

- RAM: on the Pico the core reports the heap in use, not its peak, and the
  stack is not measured. Its percentage uses the 264 KB of SRAM.
- Flash: on the Pico the program size comes from the end address of the
  program in the flash (`__flash_binary_end`), over the 2 MB chip.
- Power: on the Pico the INA219 is in series with `VSYS` instead of `5V`.
- Wi-Fi: the Pico has none, so it could not set its clock by NTP or send
  data without a PC. That is a functional reason in favour of the ESP32-S3
  that does not depend on the measurements.

### Pipeline test on both boards (not a project result)

Measured on 2026-11-20 with the same **placeholder model** on both boards
(20 inputs, hidden layers of 16 and 8 units, 2 classes), both connected to
the PC at the same time. Power was not measured: the INA219 was not in the
supply path of either board.

| Metric | ESP32-S3 (240 MHz) | Raspberry Pi Pico (200 MHz) |
|---|---|---|
| Latency, 200 runs | mean 0.0504 ms, std 0.0161 ms | mean 0.0871 ms, std 0.0218 ms |
| Tensor arena used | 876 B (5.35 % of 16 384 B reserved) | 964 B (5.88 % of 16 384 B reserved) |
| Model | 3 152 B (0.02 % of 16 MB flash) | 3 152 B (0.15 % of 2 MB flash) |
| Program | 476 272 B (2.84 % of flash; 36.34 % of the program partition) | 155 800 B (7.43 % of flash) |
| RAM | heap peak 52 296 of 368 408 B (14.20 %) | heap in use 2 276 of 235 332 B (0.97 %) |
| Identical int8 output vs. PC | 100 of 100 (`VECTOR`), 50 of 50 (`WINDOW`) | 100 of 100 (`VECTOR`) |

The two programs are not equivalent: the ESP32-S3 firmware also reads the
sensors, logs to the flash and can use Wi-Fi, while the Pico firmware only
runs the benchmark. Compare the model rows (latency, tensor arena) directly,
and the program and RAM rows with that in mind.

### Final comparison

To fill in with the real model.

| Metric | ESP32-S3 | Raspberry Pi Pico |
|---|---|---|
| Program size (% of flash) | | |
| Model size | | |
| Tensor arena | | |
| RAM in use | | |
| Latency (mean, std) | | |
| Power idle / inferring | | |
| Energy per inference | | |
| Identical int8 output vs. PC (`validate_on_device.py`) | | |
