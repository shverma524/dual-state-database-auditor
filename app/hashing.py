import hashlib
import json
from decimal import Decimal, InvalidOperation


def canonical_json(value) -> str:
    """Stable, standards-compliant JSON encoding for hash inputs."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def event_payload(row: dict) -> dict:
    """Select immutable audit-event fields; exclude anchor metadata."""
    return {
        "audit_id": int(row["id"]),
        "table_name": row["table_name"],
        "record_id": int(row["record_id"]),
        "operation": row["operation"],
        "old_data": row["old_data"],
        "new_data": row["new_data"],
        "changed_at": (
            row["changed_at"].isoformat()
            if hasattr(row["changed_at"], "isoformat")
            else str(row["changed_at"])
        ),
    }


def hash_event(event: dict) -> str:
    return sha256_hex(canonical_json(event).encode("utf-8"))


def record_state_hash(record: dict) -> str:
    """Hash a row consistently; reject invalid monetary precision."""
    try:
        amount = Decimal(str(record["amount"]))
        if not amount.is_finite():
            raise ValueError("Amount must be finite")

        normalized_amount = amount.quantize(Decimal("0.01"))
        if amount != normalized_amount:
            raise ValueError("Amount cannot have more than two decimal places")

        normalized = {
            "id": int(record["id"]),
            "account_id": record["account_id"],
            "amount": format(normalized_amount, "f"),
            "tx_type": record["tx_type"],
            "created_at": (
                record["created_at"].isoformat()
                if hasattr(record["created_at"], "isoformat")
                else str(record["created_at"])
            ),
        }
    except InvalidOperation as exc:
        raise ValueError("Invalid monetary amount") from exc

    return sha256_hex(canonical_json(normalized).encode("utf-8"))
