"""Hash table with separate chaining, written for this project (R6).

It stores the forecast with the key (municipality, date_time), for example
("Tunja", "2026-11-13 09:00") -> {"temperature_c": 15.0, ...}.

How it works
------------
The table is a list of "buckets". Each bucket is a small list of
(key, value) pairs. To find where a key lives:

    bucket number = hash(key) % number of buckets

Two different keys can get the same bucket number (a collision). With
separate chaining both pairs simply stay in the same bucket, one after the
other, and a search walks only through that one bucket.

Complexity (n = number of stored keys)
--------------------------------------
    put, get, contains, remove:  O(1) on average, O(n) in the worst case
                                 (all keys in one bucket).
    Memory:                      O(n).

The average stays O(1) because the table doubles its number of buckets when
it holds more than 0.75 keys per bucket, so buckets stay short. A resize
costs O(n), but it happens so rarely that the cost per insertion is still
O(1) on average ("amortized").

Compared with a list
--------------------
With a plain list of (key, value) pairs, finding one forecast means checking
the pairs one by one: O(n) per search. The dashboard looks up one forecast
for every node prediction and every hour of the comparison window, so with m
lookups the list costs O(m * n) and the hash table O(m) on average.
"""


class HashTable:
    """Dictionary-like table: key (municipality, date_time) -> value."""

    INITIAL_BUCKETS = 16
    MAX_LOAD_FACTOR = 0.75  # keys per bucket before the table grows

    def __init__(self):
        self.buckets = [[] for _ in range(self.INITIAL_BUCKETS)]
        self.count = 0

    @staticmethod
    def hash_key(key):
        """Own hash function: polynomial rolling hash of the key text.

        Each character changes the result (hash = hash * 31 + character
        code), so similar keys such as "... 09:00" and "... 12:00" land in
        different buckets. The result is always the same for the same key.
        """
        municipality, date_time = key
        text = f"{municipality.lower()}|{date_time}"
        value = 0
        for character in text:
            value = (value * 31 + ord(character)) % 4294967296  # keep 32 bits
        return value

    def _bucket_of(self, key):
        return self.buckets[self.hash_key(key) % len(self.buckets)]

    def put(self, key, value):
        """Insert a key, or replace its value if it already exists."""
        bucket = self._bucket_of(key)
        for position, (stored_key, _) in enumerate(bucket):
            if stored_key == key:
                bucket[position] = (key, value)
                return
        bucket.append((key, value))
        self.count += 1
        if self.count / len(self.buckets) > self.MAX_LOAD_FACTOR:
            self._grow()

    def get(self, key, default=None):
        """Return the value of a key, or default if the key is not stored."""
        for stored_key, value in self._bucket_of(key):
            if stored_key == key:
                return value
        return default

    def contains(self, key):
        return any(stored_key == key for stored_key, _ in self._bucket_of(key))

    def remove(self, key):
        """Delete a key. Returns True if it was stored."""
        bucket = self._bucket_of(key)
        for position, (stored_key, _) in enumerate(bucket):
            if stored_key == key:
                del bucket[position]
                self.count -= 1
                return True
        return False

    def items(self):
        """All (key, value) pairs, in no particular order. O(n)."""
        return [pair for bucket in self.buckets for pair in bucket]

    def __len__(self):
        return self.count

    def longest_bucket(self):
        """Length of the longest chain (1 means no collisions at all)."""
        return max(len(bucket) for bucket in self.buckets)

    def _grow(self):
        """Double the number of buckets and place every pair again. O(n)."""
        pairs = self.items()
        self.buckets = [[] for _ in range(2 * len(self.buckets))]
        for key, value in pairs:
            self._bucket_of(key).append((key, value))


if __name__ == "__main__":
    # Small self-test:  python scraper/hash_table.py
    table = HashTable()
    for hour in range(500):
        table.put(("Tunja", f"2026-11-{1 + hour // 24:02d} {hour % 24:02d}:00"), hour)
    table.put(("Tunja", "2026-11-01 00:00"), -1)  # replace an existing key
    assert len(table) == 500
    assert table.get(("Tunja", "2026-11-01 00:00")) == -1
    assert table.get(("tunja", "2026-11-03 05:00")) is None  # keys are exact
    assert table.get(("Tunja", "2026-11-03 05:00")) == 53
    assert table.remove(("Tunja", "2026-11-03 05:00")) and len(table) == 499
    assert not table.contains(("Tunja", "2026-11-03 05:00"))
    print(f"OK: {len(table)} keys in {len(table.buckets)} buckets, "
          f"longest chain {table.longest_bucket()}")
