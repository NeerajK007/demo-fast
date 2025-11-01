import json
import re
from utils import log_event

ALLOWED_ACTIONS = {
    "get_balance",
    "get_transactions",
    "get_customer_info",
    "transfer",
    "freeze_account"
}

def extract_action_from_text(text):
    """Extracts the intended action and parameters from LLM output.
    Safely handles clarify responses and prevents false action detection.
    """
    clean = text.replace("```json", "").replace("```", "").strip()

    # --- Case 1: Direct JSON ---
    try:
        obj = json.loads(clean)
        if "action" in obj:
            act = str(obj["action"]).strip().lower()
            params = obj.get("params", {})

            # Explicitly handle clarify
            if act == "clarify":
                log_event("Detected clarify action (explicit JSON).")
                return "clarify", params

            if act in ALLOWED_ACTIONS:
                return act, params
            else:
                log_event(f"Rejected unknown action: {act}")
                return None, {}
    except Exception:
        pass

    # --- Case 2: Embedded JSON in text ---
    m = re.search(r"\{.*\"action\".*\}", clean)
    if m:
        try:
            j = json.loads(m.group(0))
            act = str(j.get("action", "")).strip().lower()
            params = j.get("params", {})

            if act == "clarify":
                log_event("Detected clarify action (embedded JSON).")
                return "clarify", params

            if act in ALLOWED_ACTIONS:
                return act, params
        except Exception:
            pass

    # --- Case 3: Keyword fallback (only if no clarify) ---
    t = text.lower()

    # Prevent misclassification of clarification messages
    if '"clarify"' in t or 'clarify' in t:
        return "clarify", {
            "message": "Could you please specify what help you need — balance, transfer, or account info?"
        }

    # --- Heuristic fallback detection ---
    if "balance" in t:
        return "get_balance", {}
    if "transaction" in t:
        return "get_transactions", {"n": 3}
    if "info" in t or "detail" in t:
        return "get_customer_info", {}
    if "transfer" in t:
        amt_match = re.search(r"\$?(\d+(?:\.\d+)?)", t)
        amount = float(amt_match.group(1)) if amt_match else 0.0
        dest = re.search(r"cust\d{3}", t)
        to = dest.group(0).upper() if dest else "UNKNOWN"
        return "transfer", {"to": to, "amount": amount}
    if "freeze" in t:
        return "freeze_account", {}

    return None, {}
