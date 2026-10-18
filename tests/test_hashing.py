import hashlib
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from app.hashing import (
    canonical_json,
    hash_event,
    record_state_hash,
    sha256_hex,
)


class HashingTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            "id": 1,
            "account_id": "acc_demo",
            "amount": Decimal("250.00"),
            "tx_type": "credit",
            "created_at": datetime(2026, 10, 18, tzinfo=timezone.utc),
        }

    def test_sha256_known_vector(self):
        self.assertEqual(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223"
            "b00361a396177a9cb410ff61f20015ad",
        )

    def test_canonical_json_sorts_keys(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), '{"a":1,"b":2}')

    def test_canonical_json_rejects_decimal(self):
        with self.assertRaises(TypeError):
            canonical_json({"amount": Decimal("12.50")})

    def test_canonical_json_rejects_nan(self):
        with self.assertRaises(ValueError):
            canonical_json({"amount": float("nan")})

    def test_event_hash_is_deterministic(self):
        event = {
            "audit_id": 7,
            "table_name": "financial_records",
            "record_id": 4,
            "operation": "INSERT",
            "old_data": None,
            "new_data": {"id": 4, "amount": 250.0},
            "changed_at": "2026-10-18T00:00:00+00:00",
        }
        self.assertEqual(hash_event(event), hash_event(dict(event)))

    def test_equivalent_money_formats_hash_identically(self):
        original = record_state_hash(self.record)
        for amount in ("250", "250.0", "250.00", "250.000"):
            with self.subTest(amount=amount):
                self.assertEqual(
                    original,
                    record_state_hash({**self.record, "amount": Decimal(amount)}),
                )

    def test_excess_money_precision_is_rejected(self):
        with self.assertRaises(ValueError):
            record_state_hash({**self.record, "amount": Decimal("250.001")})

    def test_non_finite_money_is_rejected(self):
        for amount in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    record_state_hash({**self.record, "amount": Decimal(amount)})

    def test_changed_amount_changes_hash(self):
        self.assertNotEqual(
            record_state_hash(self.record),
            record_state_hash({**self.record, "amount": Decimal("251.00")}),
        )

    def test_changed_record_fields_change_hash(self):
        original = record_state_hash(self.record)
        changes = [
            {"id": 2},
            {"account_id": "another_account"},
            {"tx_type": "debit"},
            {"created_at": datetime(2026, 10, 19, tzinfo=timezone.utc)},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(
                    original,
                    record_state_hash({**self.record, **change}),
                )


if __name__ == "__main__":
    unittest.main()
