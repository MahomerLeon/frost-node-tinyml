# Resource report (R7)

Status: **ESP32-S3 measured with the final model on 2026-11-25** (see Final
measurements). Power was not measured, and the Pico was only measured with the
placeholder model.

## How the measurements are taken

Everything comes from the `BENCHMARK` command of `firmware/inference`
(procedure in [firmware/README.md](../firmware/README.md)).

**Power and energy were not measured**: the board could not be powered through
the INA219. No consumption figure is reported or estimated.

| Metric | Unit | How it is obtained | Total used for the percentage |
|---|---|---|---|
| Program size | bytes, % | `ESP.getSketchSize()`; also printed by the compiler | program partition, and whole flash chip |
| Model size | bytes, % | length of the array in `model_data.h` | whole flash chip |
| Tensor arena | bytes, % | `interpreter->arena_used_bytes()` | arena reserved (`TENSOR_ARENA_BYTES`) |
| Heap, peak use | bytes, % | heap size minus `ESP.getMinFreeHeap()` | heap size |
| Stack, peak use | bytes, % | stack size minus the high-water mark of the loop task | stack of the loop task |
| Latency per inference | ms | `micros()` around each `Invoke()`, mean and standard deviation over 200 runs | — |
| CPU cycles per inference | cycles | cycle counter of the core around each `Invoke()` (`ESP.getCycleCount()` on the ESP32-S3, `rp2040.getCycleCount64()` on the Pico), mean over 200 runs | — |
| Throughput | inferences/s | 1000 divided by the mean latency in ms | — |
| CPU load | % | mean latency divided by the period between inferences (30 min) | — |

Limits of the method:

- The CPU load is an estimate from the latency, not a measurement with the
  profiling tools of the manufacturer SDK. The CPU cycles come from the
  hardware cycle counter (measured on the ESP32-S3 with the final model; not
  on the Pico).
- Latency is measured with the CPU at 240 MHz and Wi-Fi off.

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

ESP32-S3 with the final model (dataset v1, 3 classes, 20 inputs), `BENCHMARK`
command on 2026-11-25, board powered by the PC.

| Metric | Value | Percentage |
|---|---|---|
| Program size | 476 480 bytes | 36.35 % of the program partition; 2.84 % of the flash |
| Model size | 3 160 bytes | 0.02 % of the 16 MB flash |
| Tensor arena | 876 bytes of 16 384 reserved | 5.35 % |
| Heap, peak use | 52 984 of 368 408 bytes | 14.38 % |
| Stack, peak use | 2 388 of 8 192 bytes | 29.15 % |
| Latency (mean, std, runs) | 0.0528 ms, 0.0138 ms, 200 runs | — |
| CPU cycles per inference | 13 509 (240 MHz) | — |
| Throughput | 18 952 inferences/s | — |
| CPU load | one inference every 30 min | 0.000003 % |
| Power and energy | not measured | — |

The `BENCHMARK` power lines read about 0 mA because the board was powered by
the PC, not through the INA219; they are not a measurement.

On-device check (`ml/validate_on_device.py`, same day):

| Check | Same class as the PC | Identical int8 output | Largest difference |
|---|---|---|---|
| 100 quantized test vectors (`VECTOR`) | 100 of 100 | 95 of 100 | 6 units |
| 50 raw test windows (`WINDOW`) | 50 of 50 | 48 of 50 | 2 units |

Macro F1 of the node on the 100 vectors: 0.851. They are 88 of class 0, 11 of
class 1 and 1 of class 2, a small sample; the F1 of the whole test split is
0.683 (`ml/models/metrics_v1_int8.json`).

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
no sensor, so the Pico can run it while the ESP32-S3 keeps its sensors.

Differences in how the two boards are measured:

- RAM: on the Pico the core reports the heap in use, not its peak, and the
  stack is not measured. Its percentage uses the 264 KB of SRAM.
- Flash: on the Pico the program size comes from the end address of the
  program in the flash (`__flash_binary_end`), over the 2 MB chip.
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

Only the ESP32-S3 column was measured with the final model; the Pico was not
measured again.

| Metric | ESP32-S3 | Raspberry Pi Pico |
|---|---|---|
| Program size (% of flash) | | |
| Model size | | |
| Tensor arena | | |
| RAM in use | | |
| Latency (mean, std) | | |
| Power and energy | not measured | not measured |
| Identical int8 output vs. PC (`validate_on_device.py`) | | |
