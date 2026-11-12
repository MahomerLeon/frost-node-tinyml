// Circular buffer (ring buffer) with the most recent readings of the node.
// Own implementation, no library (course requirement R6).
//
// How it works: a fixed array of CAPACITY slots and an index "head" that
// points to the slot where the next reading will be written. When the array
// is full, the new reading overwrites the oldest one, and head moves forward
// (wrapping to 0 at the end). Nothing is ever shifted or copied.
//
// Complexity (n = CAPACITY = number of readings in the 3 h window):
//   push()   O(1) time: one write and one index update.
//   get(i)   O(1) time: one index calculation.
//   size(), isFull(), clear()   O(1) time.
//   Memory   O(n), fixed at compile time: no dynamic allocation, so the RAM
//            use is known in advance and cannot fragment the heap.
//
// Alternative: a plain array where every new reading shifts the others one
// position costs O(n) per insertion. With n = 6 the difference is small in
// absolute time, but the circular buffer keeps the cost constant if the
// window or the sampling rate grows.

#pragma once

struct Reading {
  float temperatureC;
  float humidityPct;
  float pressureHpa;
  bool valid;  // false when no sensor reading was available for that step
};

template <int CAPACITY>
class CircularBuffer {
 public:
  // Adds a reading. If the buffer is full, the oldest one is overwritten.
  void push(const Reading &reading) {
    items[head] = reading;
    head = (head + 1) % CAPACITY;
    if (count < CAPACITY) {
      count++;
    }
  }

  // Returns reading number i, where 0 is the oldest and size() - 1 the newest.
  const Reading &get(int i) const {
    int oldest = (head - count + CAPACITY) % CAPACITY;
    return items[(oldest + i) % CAPACITY];
  }

  int size() const { return count; }
  bool isFull() const { return count == CAPACITY; }

  void clear() {
    head = 0;
    count = 0;
  }

 private:
  Reading items[CAPACITY];
  int head = 0;   // slot where the next reading will be written
  int count = 0;  // number of readings stored (0..CAPACITY)
};
