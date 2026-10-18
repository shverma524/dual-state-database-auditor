import json
import os
import time
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from web3 import Web3
from .config import DATABASE_URL, RPC_URL, CONTRACT_ADDRESS, BATCH_SIZE, POLL_SECONDS, IDLE_FLUSH_SECONDS, EPOCH_DIR, ABI_PATH
from .hashing import event_payload, hash_event
from .merkle import build_tree

def connect_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_contract():
    if not CONTRACT_ADDRESS:
        raise RuntimeError("CONTRACT_ADDRESS is empty. Deploy the contract and set it in .env.")
    if not os.path.exists(ABI_PATH):
        raise RuntimeError(f"Contract ABI not found at {ABI_PATH}. Run npm install/compile first.")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to local chain at {RPC_URL}. Is 'npx hardhat node' running?")
    with open(ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)["abi"]
    return w3, w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

def fetch_unanchored(limit):
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, table_name, record_id, operation, old_data, new_data, changed_at
                   FROM audit_log WHERE anchored=FALSE ORDER BY id LIMIT %s""",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]

def anchor_batch(rows, epoch_id, w3, contract):
    events = [event_payload(row) for row in rows]
    leaves = [hash_event(event) for event in events]
    root, proofs = build_tree(leaves)

    account = w3.eth.accounts[0]  # Hardhat's first local funded account; local demo only.
    tx_hash = contract.functions.submitRoot(epoch_id, bytes.fromhex(root)).transact({"from": account})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"Blockchain transaction failed for epoch {epoch_id}")

    proof_file = os.path.join(EPOCH_DIR, f"epoch_{epoch_id:04d}.json")
    os.makedirs(EPOCH_DIR, exist_ok=True)
    proof_doc = {
        "epoch_id": epoch_id,
        "root": root,
        "tx_hash": receipt.transactionHash.hex(),
        "events": [
            {"event": event, "leaf_hash": leaves[i], "proof": proofs[i]}
            for i, event in enumerate(events)
        ],
    }
    temp_file = proof_file + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(proof_doc, f, indent=2)
    os.replace(temp_file, proof_file)

    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO epoch_anchors
                   (epoch_id, first_audit_id, last_audit_id, leaf_count, merkle_root, tx_hash)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (epoch_id, rows[0]["id"], rows[-1]["id"], len(rows), root, receipt.transactionHash.hex()),
            )
            cur.execute(
                "UPDATE audit_log SET anchored=TRUE, epoch_id=%s WHERE id = ANY(%s)",
                (epoch_id, [int(row["id"]) for row in rows]),
            )
    print(f"Anchored epoch {epoch_id}: {len(rows)} events, root={root}, tx={receipt.transactionHash.hex()}")

def main():
    w3, contract = get_contract()
    epoch_id = 0
    with connect_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(epoch_id), -1) + 1 AS next_epoch FROM epoch_anchors")
            epoch_id = int(cur.fetchone()["next_epoch"])

    pending = []
    last_new_event = time.monotonic()
    print("Worker running. It batches audit events and anchors each Merkle root.")
    while True:
        room = max(BATCH_SIZE - len(pending), 1)
        rows = fetch_unanchored(room)
        if rows:
            already = {int(r["id"]) for r in pending}
            newly_added = [r for r in rows if int(r["id"]) not in already]
            if newly_added:
                pending.extend(newly_added)
                last_new_event = time.monotonic()

        should_flush = bool(pending) and (
            len(pending) >= BATCH_SIZE or time.monotonic() - last_new_event >= IDLE_FLUSH_SECONDS
        )
        if should_flush:
            # IDs are ordered; a partial batch is flushed after an idle interval.
            batch = pending[:BATCH_SIZE]
            try:
                anchor_batch(batch, epoch_id, w3, contract)
                epoch_id += 1
                pending = pending[len(batch):]
            except Exception as exc:
                print(f"ERROR anchoring batch; will retry in {POLL_SECONDS}s: {exc}")
                time.sleep(POLL_SECONDS)
        else:
            time.sleep(POLL_SECONDS)

if __name__ == "__main__":
    main()
