"""Tests of the own hash table (scraper/hash_table.py)."""

import random

from hash_table import HashTable


def key(day, hour):
    return ("Tunja", f"2026-11-{day:02d} {hour:02d}:00")


def test_put_and_get():
    table = HashTable()
    table.put(key(13, 9), {"temperature_c": 15.0})
    assert table.get(key(13, 9)) == {"temperature_c": 15.0}
    assert table.contains(key(13, 9))
    assert len(table) == 1


def test_missing_key_returns_default():
    table = HashTable()
    assert table.get(key(1, 0)) is None
    assert table.get(key(1, 0), default="none") == "none"
    assert not table.contains(key(1, 0))


def test_put_replaces_an_existing_key():
    table = HashTable()
    table.put(key(13, 9), 15.0)
    table.put(key(13, 9), 14.0)  # a newer forecast for the same time
    assert table.get(key(13, 9)) == 14.0
    assert len(table) == 1


def test_remove():
    table = HashTable()
    table.put(key(13, 9), 15.0)
    assert table.remove(key(13, 9)) is True
    assert table.remove(key(13, 9)) is False
    assert len(table) == 0


def test_same_time_in_two_municipalities_are_different_keys():
    table = HashTable()
    table.put(("Tunja", "2026-11-13 09:00"), 15.0)
    table.put(("Samaca", "2026-11-13 09:00"), 13.0)
    assert table.get(("Tunja", "2026-11-13 09:00")) == 15.0
    assert table.get(("Samaca", "2026-11-13 09:00")) == 13.0


def test_colliding_keys_are_both_kept():
    # With only 16 buckets at the start, 12 keys must share some buckets
    table = HashTable()
    for hour in range(12):
        table.put(key(1, hour), hour)
    assert table.longest_bucket() >= 1
    assert [table.get(key(1, hour)) for hour in range(12)] == list(range(12))


def test_table_grows_and_keeps_every_key():
    table = HashTable()
    for day in range(1, 29):
        for hour in range(24):
            table.put(key(day, hour), (day, hour))
    assert len(table) == 28 * 24
    assert len(table.buckets) > HashTable.INITIAL_BUCKETS
    assert len(table) / len(table.buckets) <= HashTable.MAX_LOAD_FACTOR
    assert table.get(key(17, 5)) == (17, 5)
    assert len(table.items()) == 28 * 24


def test_hash_is_the_same_every_time():
    assert HashTable.hash_key(key(13, 9)) == HashTable.hash_key(key(13, 9))


def test_behaves_like_a_python_dictionary():
    """Random operations give the same result as Python's own dict."""
    generator = random.Random(1)
    table, reference = HashTable(), {}
    for _ in range(3000):
        k = key(generator.randint(1, 28), generator.randint(0, 23))
        action = generator.choice(["put", "put", "remove", "get"])
        if action == "put":
            value = generator.random()
            table.put(k, value)
            reference[k] = value
        elif action == "remove":
            assert table.remove(k) == (reference.pop(k, None) is not None)
        else:
            assert table.get(k) == reference.get(k)
    assert len(table) == len(reference)
    assert dict(table.items()) == reference
