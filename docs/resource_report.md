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

The program has grown since then (flash storage, power meter). The size of
the current version is in `firmware/README.md`.

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

## Not oversizing the device

The course criterion: under 30 % of Flash and RAM with latency far below what
the application needs suggests trying a more limited device; over 80 %
suggests a larger one or more optimization. The comparison with the
Raspberry Pi Pico is pending: there is no firmware for it yet.
