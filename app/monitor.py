
import json
import os
import time
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import DATABASE_URL
from app.verify import verify_record

POLL_SECONDS = int(os.getenv("MONITOR_POLL_SECONDS", "10"))
ALERT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "tamper_alerts.json",
)

# Failures that should create an integrity alert.
ALERT_STATUSES = {
    "TAMPER_DETECTED",
    "PROOF_FILE_INVALID",
    "PROOF_NOT_FOUND",
    "MERKLE_PROOF_FAILED",
    "NO_ONCHAIN_ROOT",
    "AUDIT_SNAPSHOT_MISSING",
}


def load_alerts():
    if not os.path.exists(ALERT_FILE):
        return []

    try:
        with open(ALERT_FILE, encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        logging.exception("Could not read alert history")
        return []


def save_alerts(alerts):
    os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)
    temporary_file = ALERT_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as file:
        json.dump(alerts, file, indent=2, default=str)

    os.replace(temporary_file, ALERT_FILE)


def get_record_ids():
    """Return IDs that exist now or have an anchored audit history."""
    with psycopg2.connect(
        DATABASE_URL, cursor_factory=RealDictCursor
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM financial_records
                UNION
                SELECT DISTINCT record_id AS id
                FROM audit_log
                WHERE table_name = 'financial_records'
                  AND anchored = TRUE
                ORDER BY id
            """)
            return [int(row["id"]) for row in cur.fetchall()]


def check_record(record_id):
    try:
        return verify_record(record_id)
    except Exception as exc:
        logging.exception("Verification failed for record %s", record_id)
        return {
            "status": "MONITOR_ERROR",
            "detail": str(exc),
        }


def scan_once():
    """Run one monitoring pass and save newly observed incidents."""
    alerts = load_alerts()

    # Reuse an incident key for an unchanged status on the same record.
    existing_keys = {
        (item["record_id"], item["status"])
        for item in alerts
        if item.get("active", True)
    }

    try:
        record_ids = get_record_ids()
    except Exception:
        logging.exception("Cannot query database during monitoring")
        return

    for record_id in record_ids:
        result = check_record(record_id)
        status = result.get("status", "UNKNOWN")

        # A verified, valid record clears its active incident.
        if status == "VALID":
            for item in alerts:
                if item.get("record_id") == record_id:
                    item["active"] = False
            continue

        # A missing row is only an alert if the latest anchored event
        # was not a DELETE. Legitimate deletions are expected.
        if status == "RECORD_NOT_FOUND":
            try:
                with psycopg2.connect(
                    DATABASE_URL, cursor_factory=RealDictCursor
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT operation
                            FROM audit_log
                            WHERE record_id = %s
                              AND table_name = 'financial_records'
                              AND anchored = TRUE
                            ORDER BY id DESC
                            LIMIT 1
                        """, (record_id,))
                        latest = cur.fetchone()
                if latest and latest["operation"] == "DELETE":
                    continue
                status = "UNEXPECTED_MISSING_RECORD"
            except Exception:
                logging.exception("Could not check deletion history")
                continue

        if status not in ALERT_STATUSES and status != "UNEXPECTED_MISSING_RECORD":
            continue

        key = (record_id, status)
        if key in existing_keys:
            continue

        alert = {
            "record_id": record_id,
            "status": status,
            "detail": result.get("detail", ""),
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        alerts.append(alert)
        existing_keys.add(key)

        logging.error(
            "INTEGRITY ALERT — record %s: %s — %s",
            record_id, status, alert["detail"]
        )

    save_alerts(alerts)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    logging.info("Tamper monitor started; polling every %s seconds", POLL_SECONDS)

    while True:
        scan_once()
        time.sleep(max(3, POLL_SECONDS))


if __name__ == "__main__":
    main()
