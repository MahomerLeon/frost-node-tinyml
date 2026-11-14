# Data structures (R6)

Two data structures, both written for this project without a library.

## 1. Circular buffer, on the ESP32-S3

File: [firmware/inference/circular_buffer.h](../firmware/inference/circular_buffer.h)

**Purpose.** The model needs the readings of the last 3 hours: 6 steps of 30
minutes. Every 30 minutes a new step arrives and the oldest one is no longer
needed.

**How it works.** A fixed array of `n` slots and an index `head` that points
to the slot of the next reading. A new reading is written at `head`, and
`head` moves one position, going back to 0 after the last slot. When the
array is full, the new reading overwrites the oldest one.

| Operation | Time | Why |
|---|---|---|
| `push` (insert) | O(1) | one write and one index update |
| `get(i)` (i-th oldest) | O(1) | one index calculation |
| `size`, `isFull`, `clear` | O(1) | they only read or reset two integers |
| Memory | O(n), fixed | the array is sized at compile time, no dynamic memory |

**Alternative.** A plain array in which every new reading shifts the others
one position costs O(n) per insertion. A linked list has O(1) insertion but
needs dynamic memory, which on a microcontroller can fragment the heap, and
extra bytes for the links. With n = 6 the difference in time is small, but
the circular buffer has a constant, known cost and no allocation.

**Test.** `tests/test_circular_buffer.cpp` (runs on the PC).

## 2. Hash table, in the scraper and dashboard

File: [scraper/hash_table.py](../scraper/hash_table.py)

**Purpose.** The forecast is stored with the key (municipality, date and
hour). To validate a prediction of the node, the dashboard needs the forecast
of specific hours: it builds the key of each hour and looks it up.

**How it works.** A list of buckets; each bucket is a short list of
(key, value) pairs. The bucket of a key is `hash(key) % number of buckets`,
with an own hash function (polynomial rolling hash of the key text).
Collisions are solved by chaining: pairs with the same bucket number stay in
the same bucket. When the table holds more than 0.75 keys per bucket, the
number of buckets doubles.

| Operation | Average | Worst case | Why |
|---|---|---|---|
| `put`, `get`, `contains`, `remove` | O(1) | O(n) | only one bucket is examined; the worst case is every key in the same bucket |
| Growing the table | O(n), but rare | O(n) | amortized O(1) per insertion |
| Memory | O(n) | O(n) | one pair per key |

**Alternative.** With a list of pairs, each search checks the pairs one by
one: O(n). The dashboard does one lookup per node prediction and per hour of
the comparison window. For m lookups over n stored forecasts, the list costs
O(m · n) and the hash table O(m) on average. A sorted list with binary search
would cost O(log n) per search and O(n) per insertion.

**Test.** `tests/test_hash_table.py`, which also compares the table with a
Python dictionary over 3000 random operations.
