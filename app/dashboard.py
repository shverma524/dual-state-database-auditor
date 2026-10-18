import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from app.config import DATABASE_URL
from app.verify import verify_record
import json
import os
import pandas as pd

st.set_page_config(page_title="Dual-State Auditor", page_icon="🔐", layout="centered")
st.title("Dual-State Database Auditor")
st.caption("PostgreSQL audit log → SHA-256 → Merkle tree → local blockchain anchor → record verification")


# Automatic integrity-alert panel
st.subheader("🚨 Active Integrity Alerts")

ALERT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "tamper_alerts.json",
)

@st.fragment(run_every=10)
def show_integrity_alerts():
    if not os.path.exists(ALERT_FILE):
        st.info("No alert history found yet.")
        return

    try:
        with open(ALERT_FILE, encoding="utf-8") as file:
            alerts = json.load(file)
    except (json.JSONDecodeError, OSError):
        st.warning("Could not read the alert history.")
        return

    active_alerts = [
        alert for alert in alerts
        if alert.get("active", True)
    ]

    if not active_alerts:
        st.success("No active integrity alerts.")
        return

    st.error(f"{len(active_alerts)} active integrity alert(s)")

    df = pd.DataFrame(active_alerts)
    columns = [
        column for column in
        ["record_id", "status", "detail", "detected_at"]
        if column in df.columns
    ]
    st.dataframe(df[columns], use_container_width=True)

show_integrity_alerts()


with st.expander("Create a test record"):
    with st.form("create_record"):
        account_id = st.text_input("Account ID", value="acc_demo")
        amount = st.number_input("Amount", min_value=0.0, value=250.00, step=10.0, format="%.2f")
        tx_type = st.selectbox("Transaction type", ["credit", "debit"])
        submitted = st.form_submit_button("Insert record")
    if submitted:
        try:
            with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO financial_records(account_id, amount, tx_type)
                           VALUES (%s, %s, %s)
                           RETURNING id""",
                        (account_id, amount, tx_type),
                    )
                    new_id = cur.fetchone()["id"]
            st.success(f"Created record ID {new_id}. Wait for the worker to anchor it before verifying.")
        except Exception as exc:
            st.error(f"Insert failed: {exc}")

record_id = st.number_input("Record ID to verify", min_value=1, step=1, value=1)
if st.button("Verify record", type="primary"):
    try:
        result = verify_record(int(record_id))
        status = result.get("status", "UNKNOWN")
        if status == "VALID":
            st.success(f"VALID — {result['detail']}")
        elif status == "TAMPER_DETECTED":
            st.error(f"TAMPER DETECTED — {result['detail']}")
        elif status in ("NOT_YET_ANCHORED",):
            st.warning(result["detail"])
        else:
            st.error(f"{status} — {result.get('detail', result)}")
        st.json(result)
    except Exception as exc:
        st.exception(exc)

st.subheader("Recent records")
try:
    with psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, account_id, amount, tx_type, created_at FROM financial_records ORDER BY id DESC LIMIT 20")
            rows = cur.fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)
except Exception as exc:
    st.info(f"Database not available yet: {exc}")
