import json
import logging
import os

LOG_FILE = "/app/logs/agent.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_event(entry, customer_id=None):
    """Universal structured logger."""
    prefix = f"[{customer_id}] " if customer_id else ""
    if isinstance(entry, dict):
        msg = json.dumps(entry, default=str)
    else:
        msg = str(entry)
    logging.info(prefix + msg)

def load_data(data_path):
    with open(data_path, "r") as f:
        return json.load(f)

def save_data(data_path, data):
    with open(data_path, "w") as f:
        json.dump(data, f, indent=2)
