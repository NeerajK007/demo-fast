import os

# Required environment vars
REQUIRED_ENV = ["LLM_URL", "DATA_PATH"]
missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
if missing:
    raise EnvironmentError(f"Missing required env vars: {missing}")

LLM_URL = os.environ["LLM_URL"]
DATA_PATH = os.environ["DATA_PATH"]

# Execution flags
AUTO_EXECUTE = os.environ.get("AUTO_EXECUTE", "true").lower() == "true"
RED_TEAM_MODE = os.environ.get("RED_TEAM_MODE", "false").lower() == "true"

# Risk tuning (future use)
RISK_THRESHOLD = int(os.environ.get("RISK_THRESHOLD", "40"))
