from decimal import Decimal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from .config import DATABASE_URL

app = FastAPI(title="Dual-State Database API", version="1.0.0")

def connect():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

class RecordIn(BaseModel):
    account_id: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(ge=0, max_digits=15, decimal_places=2)
    tx_type: str

    def validate_tx_type(self):
        if self.tx_type not in ("credit", "debit"):
            raise ValueError("tx_type must be 'credit' or 'debit'")

@app.get("/health")
def health():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")

@app.post("/records", status_code=201)
def create_record(record: RecordIn):
    if record.tx_type not in ("credit", "debit"):
        raise HTTPException(status_code=422, detail="tx_type must be 'credit' or 'debit'")
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO financial_records(account_id, amount, tx_type)
                       VALUES (%s, %s, %s)
                       RETURNING id, account_id, amount, tx_type, created_at""",
                    (record.account_id, record.amount, record.tx_type),
                )
                row = dict(cur.fetchone())
        return row
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/records/{record_id}")
def get_record(record_id: int):
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, account_id, amount, tx_type, created_at FROM financial_records WHERE id=%s",
                (record_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found")
    return dict(row)

@app.get("/epochs")
def list_epochs():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM epoch_anchors ORDER BY epoch_id")
            rows = cur.fetchall()
    return [dict(r) for r in rows]
