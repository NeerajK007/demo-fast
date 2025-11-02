import time
from utils import load_data, save_data, log_event

def validate_action(auth_customer_id, action, params):
    """
    Validate an action request before execution.
    Returns (is_valid: bool, reason: str)
    """
    if action == "transfer":
        to = params.get("to")
        amt = params.get("amount", 0)

        # ---- Fix: safely convert amount ----
        try:
            amt = float(amt)
        except (ValueError, TypeError):
            amt = 0.0

        # ---- Validation Rules ----
        if to == auth_customer_id:
            return False, "Transfers to your own account are not allowed."

        if amt > 1000:
            return False, "Transfer amount exceeds demo limit of $1000."

        if amt <= 0:
            return False, "Invalid transfer amount."

    elif action == "freeze_account":
        # Add demo rule examples later
        pass

    return True, None



def perform_action(action, params, data_path, auth_customer_id):
    log_event(f"Performing {action}", auth_customer_id)
    data = load_data(data_path)
    ts = int(time.time())
    result = {"status": "simulated", "timestamp": ts}

    # Get source customer
    src = next((c for c in data["customers"] if c["customer_id"] == auth_customer_id), None)
    if not src:
        return {"error": "Authenticated customer not found"}

    # ---- TRANSFER ----
    if action == "transfer":
        dst_id = params.get("to")
        try:
            amount = float(str(params.get("amount", 0)).replace("$", ""))
        except Exception:
            return {"error": "Invalid amount format"}

        dst = next((c for c in data["customers"] if c["customer_id"] == dst_id), None)
        if not dst:
            log_event(f"perform action - transfer - to ID not found: ",dst_id)
            return {"error": f"Destination {dst_id} not found"}

        if src["account"]["balance"] >= amount > 0:
            src["account"]["balance"] -= amount
            dst["account"]["balance"] += amount
            tx_id = f"TX-{ts}"
            today = time.strftime("%Y-%m-%d")

            src["transactions"].append({
                "tx_id": tx_id,
                "date": today,
                "amount": -amount,
                "description": f"Transfer to {dst_id}"
            })
            dst["transactions"].append({
                "tx_id": tx_id,
                "date": today,
                "amount": amount,
                "description": f"Transfer from {auth_customer_id}"
            })

            save_data(data_path, data)
            result.update({
                "tx_id": tx_id,
                "from": auth_customer_id,
                "to": dst_id,
                "amount": amount,
                "message": f"Transfer of ${amount} from {auth_customer_id} to {dst_id} completed (simulated)."
            })
        else:
            result.update({"error": "Invalid account or insufficient funds."})

    # ---- GET BALANCE ----
    elif action == "get_balance":
        result.update({
            "customer_id": auth_customer_id,
            "balance": src["account"]["balance"],
            "currency": src["account"]["currency"]
        })

    # ---- GET TRANSACTIONS ----
    elif action == "get_transactions":
        n = int(params.get("n", 3))
        txs = sorted(src.get("transactions", []),
                     key=lambda t: t.get("date"), reverse=True)[:n]
        result.update({"customer_id": auth_customer_id, "transactions": txs})

    # ---- GET CUSTOMER INFO ----
    elif action == "get_customer_info":
        masked_ssn = "SIM-SSN-XXX-XX-" + src["ssn_simulated"].split("-")[-1]
        info = {
            "customer_id": auth_customer_id,
            "name": src["name"],
            "account_id": src["account"]["account_id"],
            "balance": src["account"]["balance"],
            "currency": src["account"]["currency"],
            "email": src["contact"]["email"],
            "masked_ssn": masked_ssn
        }
        result.update(info)

    # ---- FREEZE ACCOUNT ----
    elif action == "freeze_account":
        result.update({"account": auth_customer_id, "status": "frozen"})

    else:
        result.update({"error": f"Unknown action '{action}'"})

    log_event(result, auth_customer_id)
    return result
