# Automated tests

These tests need no board, no sensors and no network. They use small
hand-made inputs whose correct result is easy to check; none of the numbers
in them is project data or an agronomic threshold.

## Python tests

```
python -m pytest tests -q
```

Expected: `39 passed`.

| File | What it checks |
|---|---|
| `test_prepare_dataset.py` | Dew point formula; gaps filled only when short; window lags and the "next 6 h" minimum; windows with missing readings dropped; split by days without any day shared between train, val and test; the script stops when the threshold is missing |
| `test_hash_table.py` | Insert, replace, search, delete, collisions, growth, and the same behaviour as a Python dictionary over 3000 random operations |
| `test_comparison.py` | Which forecast values fall in the window after a prediction (also across midnight), the class rule, and the agree / disagree / not comparable results |
| `test_scraper.py` | HTML forecast parser (four periods per day, negative temperatures, year change, wrong place, changed layout); a failed download does not stop the scraper; the newest scrape wins in the hash table; parser of the lines sent by the node |

## Circular buffer test (C++, runs on the PC)

`firmware/inference/circular_buffer.h` has no Arduino code, so it can be
compiled on the PC. With g++ (for example from MSYS2):

```
g++ -std=c++17 -o test_circular_buffer tests/test_circular_buffer.cpp
./test_circular_buffer
```

Expected: `OK: all circular buffer checks passed`.

It checks the order of the readings (oldest to newest), overwriting of the
oldest reading, 1000 insertions in a row, the `valid` flag and `clear()`.

## What the tests do not cover

Training and conversion (they need a real dataset), the dashboard screen,
and everything that runs on the ESP32-S3 with the sensors.
