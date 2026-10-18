import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/ledger_db",
)
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "").strip()
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))
POLL_SECONDS = float(os.getenv("POLL_SECONDS", "2"))
IDLE_FLUSH_SECONDS = float(os.getenv("IDLE_FLUSH_SECONDS", "5"))
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOCH_DIR = os.path.join(ROOT_DIR, "data", "epochs")
ABI_PATH = os.path.join(ROOT_DIR, "blockchain", "artifacts", "contracts", "AnchorRegistry.sol", "AnchorRegistry.json")
