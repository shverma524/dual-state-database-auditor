# Receipt reconciliation demo

This adds a tested SQLite laboratory beside the original PostgreSQL/Hardhat pipeline. It reuses the existing hashing/Merkle modules. Two local files simulate trust domains. This is a classroom prototype, not production isolation or established patentability.

## Run on Windows from the repository root

~~~powershell
.\.venv\Scripts\python.exe -m demo.server --port 18877
~~~

Or use python -m demo.server --port 18877 with any installed Python 3.11 or newer. Open http://127.0.0.1:18877. No extra packages, Docker or blockchain setup are required for this mode. If that port is occupied, use --port 18878 and change the browser address too. The original pipeline still uses README.md.

## Four minute demonstration

1. Save ID 1 with amount 250.00 and ID 2 with amount 100.00. Both are pending.
2. Click Anchor pending receipts. Inspect ID 1 to show the real leaf, sibling and root.
3. Save ID 1 with amount 300.00. Show PENDING_ANCHOR, then anchor and show VERIFIED.
4. Inject Rewrite row and database audit for ID 1. Show AUDIT_TAMPERED.
5. Try anchoring. Show ANCHOR_BLOCKED.

Fault injection really modifies the generated SQLite data. It never accesses PostgreSQL. A mismatch blocks later checkpoints intentionally. For a clean rehearsal stop with Ctrl+C, then run with a fresh directory:

~~~powershell
.\.venv\Scripts\python.exe -m demo.server --port 18877 --data data/presentation-2
~~~

Increment the directory name for each rehearsal. Do not delete original data to reset this demo.

## Reproduce validation

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m demo.experiments
~~~

The recorded suite passed 32 tests: 16 original cases and 16 receipt cases. Measurements use synthetic amounts and temporary databases. evidence/experiments.json contains actual local timings. evidence/live-api.json records actual HTTP requests and responses. Re-running experiments replaces the measurement file.

## Scope

The extension records a witness receipt before committing the business row and matching audit event. It distinguishes pending changes, mismatches, missing evidence and accepted deletions. It refuses another write to an inconsistent record and refuses a checkpoint over known disagreement.

The local witness is neither tamper-proof nor independently operated. The lab adds no signature or production authentication. A receipt records application acceptance, not business authorization. Full host compromise defeats the trust assumption. A crash can leave an orphan receipt that requires investigation. Checkpoints are manual. The original asynchronous worker was not integration tested here. Full verification scans history, so only Merkle path depth is logarithmic.

## Submission and originality

submission/ contains the novelty report, implementation report, pitch slides and presenter guide. Use the implementation category unless first-review outcome approval supports a different template. The proposed patent outcome remains conditional on institutional approval and prior-art assessment. Close prior art includes US20210377037A1 and US10261711B1. Do not claim a granted patent, worldwide novelty, zero overhead or production readiness.

Original source: https://github.com/shverma524/dual-state-database-auditor. Added files are demo/, tests/test_receipts.py and evidence/. Existing hashing and Merkle code is reused and attributed.
