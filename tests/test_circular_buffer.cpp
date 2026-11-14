// Host test of firmware/inference/circular_buffer.h.
//
// The circular buffer is plain C++ with no Arduino code, so it can be
// compiled and tested on the PC, without the board:
//
//   g++ -std=c++17 -o test_circular_buffer tests/test_circular_buffer.cpp
//   ./test_circular_buffer
//
// It prints "OK" and returns 0 when every check passes.

#include <cstdio>
#include <cstdlib>

#include "../firmware/inference/circular_buffer.h"

int failures = 0;

void check(bool condition, const char *description) {
  if (!condition) {
    std::printf("FAILED: %s\n", description);
    failures++;
  }
}

Reading makeReading(float temperature) {
  return {temperature, 80.0f, 739.0f, true};
}

int main() {
  CircularBuffer<6> buffer;  // 6 steps = the 3 h window

  // ---- empty buffer ----
  check(buffer.size() == 0, "a new buffer is empty");
  check(!buffer.isFull(), "a new buffer is not full");

  // ---- filling it ----
  for (int i = 0; i < 4; i++) {
    buffer.push(makeReading(i));
  }
  check(buffer.size() == 4, "size counts the readings pushed");
  check(!buffer.isFull(), "4 of 6 is not full");
  check(buffer.get(0).temperatureC == 0, "get(0) is the oldest reading");
  check(buffer.get(3).temperatureC == 3, "get(size - 1) is the newest reading");

  buffer.push(makeReading(4));
  buffer.push(makeReading(5));
  check(buffer.isFull(), "6 of 6 is full");

  // ---- overwriting the oldest ----
  buffer.push(makeReading(6));  // 0 is overwritten
  buffer.push(makeReading(7));  // 1 is overwritten
  check(buffer.size() == 6, "size never exceeds the capacity");
  bool ordered = true;
  for (int i = 0; i < 6; i++) {
    ordered = ordered && buffer.get(i).temperatureC == i + 2;
  }
  check(ordered, "after overwriting, readings are 2,3,4,5,6,7 oldest to newest");

  // ---- many wrap-arounds ----
  for (int i = 8; i < 1000; i++) {
    buffer.push(makeReading(i));
  }
  check(buffer.get(0).temperatureC == 994, "oldest is correct after 1000 pushes");
  check(buffer.get(5).temperatureC == 999, "newest is correct after 1000 pushes");

  // ---- the valid flag travels with the reading ----
  buffer.push({0.0f, 0.0f, 0.0f, false});
  check(!buffer.get(5).valid, "an invalid reading stays marked as invalid");
  check(buffer.get(4).valid, "the previous reading is still valid");

  // ---- clear ----
  buffer.clear();
  check(buffer.size() == 0 && !buffer.isFull(), "clear empties the buffer");
  buffer.push(makeReading(42));
  check(buffer.get(0).temperatureC == 42, "the buffer works again after clear");

  // ---- capacity of one ----
  CircularBuffer<1> single;
  single.push(makeReading(1));
  single.push(makeReading(2));
  check(single.size() == 1 && single.get(0).temperatureC == 2,
        "a buffer of capacity 1 keeps only the newest reading");

  if (failures == 0) {
    std::printf("OK: all circular buffer checks passed\n");
    return EXIT_SUCCESS;
  }
  std::printf("%d check(s) failed\n", failures);
  return EXIT_FAILURE;
}
