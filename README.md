# Receipt reconciliation upgrade

See DEMO_GUIDE.md for the tested SQLite demo. Run python -m demo.server --port 18877 and open http://127.0.0.1:18877. Original pipeline instructions follow.

# Dual-State Relational Database â€” End-to-End MVP

This project demonstrates a dual-state database auditing pipeline:

**PostgreSQL records â†’ trigger-based audit log â†’ SHA-256 event hashes â†’ Merkle tree and proofs â†’ local blockchain root anchoring â†’ independent verification â†’ tamper detection.**

This is an educational minimum viable product (MVP). Zero-knowledge proofs, public testnet deployment, and split-share anchoring are future extensions, not implemented features. The local Hardhat blockchain is a demonstration anchor, not an independently operated production blockchain.

## Requirements

Install:

- Docker Desktop (macOS/Windows) or Docker Engine with Docker Compose (Linux)
- Node.js 20 or 22, including npm
- Python 3.11
- Git

Check your installations:

```bash
docker --version
docker compose version
node --version
npm --version
python3 --version
```

## First-time setup

Run the following commands from the project root.

### 1. Create the Python environment

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

The supplied `.env.example` contains local demonstration settings. Keep your actual `.env` file private and never commit it.

### 2. Start PostgreSQL

From the project root:

```bash
docker compose up -d
docker compose ps
```

Wait until the PostgreSQL service is healthy. The schema in `db/init.sql` is automatically applied when PostgreSQL initializes a new data volume. If the database volume already exists, Docker does not automatically rerun the initialization script.

**Security note:** The Compose configuration uses fixed demonstration credentials. Do not use these credentials or this configuration as-is in production.

### 3. Install and compile the smart contract

```bash
cd blockchain
npm install
npm run compile
```

### 4. Start the local blockchain

From the `blockchain` directory, run:

```bash
npx hardhat node
```

Keep this terminal running. The local node uses the RPC endpoint `http://127.0.0.1:8545`.

### 5. Deploy the contract

Open a second terminal and run:

```bash
cd ~/Desktop/dual_state_project
source .venv/bin/activate
cd blockchain
npm run deploy:local
```

Copy the `CONTRACT_ADDRESS=0x...` value printed by the deployment script.

Add the actual address to the project-root `.env` file:

```dotenv
CONTRACT_ADDRESS=0xYourActualDeployedAddress
```

Replace the example with the address printed by your deployment. Do not include quotation marks.

**Important:** Restarting the local Hardhat node resets its blockchain state. Deploy the contract again and update `.env` after restarting the node.

## Start the Python processes

Keep PostgreSQL and the Hardhat node running. Start each process in a separate terminal from the project root. Activate `.venv` in each terminal.

### Terminal A â€” API

```bash
uvicorn app.api:app --reload --port 8000
```

API documentation: http://127.0.0.1:8000/docs

### Terminal B â€” Asynchronous anchor worker

```bash
python -m app.worker
```

The worker processes audit events and anchors batches to the local blockchain.

### Terminal C â€” Auditor dashboard

```bash
streamlit run app/dashboard.py
```

Dashboard: http://localhost:8501

### Terminal D â€” Optional integrity monitor

```bash
python -m app.monitor
```

The monitor periodically checks record integrity and logs detected incidents. Its local alert history is stored in `data/tamper_alerts.json`. It does not send email or external notifications.

## Run the unit tests

From the project root, with the Python virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

The current test suite covers hashing and Merkle proof validation. A passing unit-test suite does not, by itself, verify the complete database-to-blockchain workflow.

## Demo sequence

### 1. Insert a record

Use the dashboard or the API documentation at `/docs` to submit a `POST /records` request with this JSON body:

```json
{
  "account_id": "acc_demo",
  "amount": "250.00",
  "tx_type": "credit"
}
```

### 2. Wait for anchoring

Wait approximately 5â€“10 seconds for a small batch to flush and anchor. A batch of 16 audit events reaches the configured batch size, but actual timing depends on the worker and environment.

### 3. Verify the record

Use the dashboard to verify the record. A successfully verified, unchanged record should show `VALID` when its proof and anchor are available.

### 4. Test tamper detection â€” demo database only

**Warning:** The following steps modify database data. Use only a disposable local demo database, never real or production data.

Connect to PostgreSQL:

```bash
docker exec -it dualstate-postgres psql -U postgres -d ledger_db
```

At the `ledger_db=#` prompt, identify a demo record ID and inspect its current amount:

```sql
SELECT id, account_id, amount
FROM financial_records
ORDER BY id;
```

For an ordinary update test, change a demo record's amount:

```sql
UPDATE financial_records
SET amount = 999999.00
WHERE id = YOUR_DEMO_RECORD_ID;
```

Replace `YOUR_DEMO_RECORD_ID` with the actual numeric ID, then exit with:

```sql
\q
```

This ordinary update creates a new audit event. After the event is anchored, the new state may verify as valid because the change was logged and anchored.

To demonstrate detection of an **unlogged edit**, use a disposable database and a separate test record. Disabling the trigger requires sufficient database privileges:

```sql
ALTER TABLE financial_records
DISABLE TRIGGER financial_records_audit_trigger;

UPDATE financial_records
SET amount = 999999.00
WHERE id = YOUR_DEMO_RECORD_ID;

ALTER TABLE financial_records
ENABLE TRIGGER financial_records_audit_trigger;
```

Replace the placeholder with the actual numeric ID. Re-enable the trigger immediately after the update, and exit using `\q`. Verify the record afterward. If the modified state differs from the latest anchored snapshot and the relevant proof and anchor remain intact, the verifier should detect the mismatch.

Do not use this procedure on production data. If an operation fails while the trigger is disabled, check the trigger state and re-enable it before continuing.

## Important implementation notes and limitations

- The worker flushes incomplete batches after the configured `IDLE_FLUSH_SECONDS`.
- Merkle proofs record sibling direction so proof verification can reconstruct the correct root.
- The verifier checks a record against its audit snapshot, Merkle proof, and on-chain root.
- Epoch proof files are stored under `data/epochs/`. Keep them available for verification and back them up separately from PostgreSQL.
- The local Hardhat chain and the local proof files are not independent security boundaries if the same attacker can modify all of them.
- A restarted local Hardhat node loses its previous chain state. This setup is intended for demonstrations, not permanent evidence.
- `DELETE` operations are audited. A deleted record may be reported as not found; the monitor distinguishes expected deletions from unexpected missing records when anchored history is available.
- The monitor records incidents locally. Email and external alert delivery are not implemented.
- The supplied database credentials are for local development only. Do not use real financial or personal data.
- Zero-knowledge circuits, proof generation and verification, public testnet deployment, and split-share storage are outside the current implementation scope.

## Project status

This repository demonstrates the core database-auditing and local blockchain-anchoring workflow. Unit tests cover selected hashing and Merkle proof cases; complete integration, performance, scalability, and fault-recovery testing should be performed separately before making production-readiness claims.

