import json
import os
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from web3 import Web3
from .config import DATABASE_URL, RPC_URL, CONTRACT_ADDRESS, ABI_PATH, EPOCH_DIR
from .hashing import hash_event, record_state_hash
from .merkle import verify_proof

def db_connect():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def get_contract():
    if not CONTRACT_ADDRESS or not os.path.exists(ABI_PATH):
        raise RuntimeError("Set CONTRACT_ADDRESS in .env and compile/deploy the contract first.")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError("Local blockchain is not running.")
    with open(ABI_PATH, encoding="utf-8") as f:
        abi = json.load(f)["abi"]
    return w3, w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)

def verify_record(record_id: int):
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, account_id, amount, tx_type, created_at FROM financial_records WHERE id=%s", (record_id,))
            current = cur.fetchone()
            cur.execute(
                """SELECT id, epoch_id FROM audit_log
                   WHERE record_id=%s AND table_name='financial_records' AND anchored=TRUE
                   ORDER BY id DESC LIMIT 1""",
                (record_id,),
            )
            latest_audit = cur.fetchone()

    if current is None:
        return {"status": "RECORD_NOT_FOUND", "detail": "The current row is missing. Check the anchored DELETE event in the audit history."}
    if latest_audit is None or latest_audit["epoch_id"] is None:
        return {"status": "NOT_YET_ANCHORED", "detail": "Wait for the worker to anchor the audit event, then retry."}

    epoch_id = int(latest_audit["epoch_id"])
    path = os.path.join(EPOCH_DIR, f"epoch_{epoch_id:04d}.json")
    if not os.path.exists(path):
        return {"status": "PROOF_FILE_MISSING", "detail": f"Expected proof file {path}."}
    with open(path, encoding="utf-8") as f:
        proof_doc = json.load(f)

    committed_item = None
    for item in proof_doc["events"]:
        if int(item["event"]["audit_id"]) == int(latest_audit["id"]):
            committed_item = item
            break
    if committed_item is None:
        return {"status": "PROOF_NOT_FOUND", "detail": "The latest anchored audit event is not in its epoch proof file."}

    event = committed_item["event"]
    recomputed_leaf = hash_event(event)
    if recomputed_leaf != committed_item["leaf_hash"]:
        return {"status": "PROOF_FILE_INVALID", "detail": "The event in the proof file does not match its stored leaf hash."}

    w3, contract = get_contract()
    on_chain_root_bytes = contract.functions.roots(epoch_id).call()
    if on_chain_root_bytes == bytes(32):
        return {"status": "NO_ONCHAIN_ROOT", "detail": f"No root exists on chain for epoch {epoch_id}."}
    on_chain_root = on_chain_root_bytes.hex()

    proof_ok = verify_proof(recomputed_leaf, committed_item["proof"], on_chain_root)
    if not proof_ok:
        return {"status": "MERKLE_PROOF_FAILED", "detail": "Proof does not match the independently stored on-chain root."}

    # Compare the current business row to the immutable new_data snapshot in the committed audit event.
    if event["operation"] == "DELETE":
        return {"status": "RECORD_NOT_FOUND", "detail": "The latest anchored event is a DELETE event."}
    snapshot = event["new_data"]
    if snapshot is None:
        return {"status": "AUDIT_SNAPSHOT_MISSING", "detail": "The committed audit event has no new_data snapshot."}

    current_hash = record_state_hash(dict(current))
    snapshot_hash = record_state_hash(snapshot)
    if current_hash != snapshot_hash:
        return {
            "status": "TAMPER_DETECTED",
            "detail": "The current database row differs from the state recorded in the anchored audit event.",
            "epoch_id": epoch_id,
            "on_chain_root": on_chain_root,
        }
    return {
        "status": "VALID",
        "detail": "Current row matches the anchored audit snapshot and its Merkle proof matches the on-chain root.",
        "epoch_id": epoch_id,
        "on_chain_root": on_chain_root,
        "tx_hash": proof_doc["tx_hash"],
    }
