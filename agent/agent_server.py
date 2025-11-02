import json
import requests
import os
from flask import Flask, request, jsonify

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# your project modules (keep these files as-is)
from config import LLM_URL, DATA_PATH, AUTO_EXECUTE
from utils import log_event
from auth import validate_token
from extractor import extract_action_from_text
from actions import perform_action, validate_action

app = Flask(__name__)

# --------- Rate limiter ----------
limiter = Limiter(
    key_func=lambda: request.headers.get("Authorization", get_remote_address()),
    default_limits=["60 per minute"],
    app=app
)

# --------- CORS config ----------
# By default allow the Vite dev UI origin. Configure via env:
# export ALLOWED_ORIGINS="http://localhost:5173" or comma-separated list
allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

# Use "*" for wildcard in development: export ALLOWED_ORIGINS="*"
cors_origins = "*" if allowed_origins == ["*"] else allowed_origins

# Apply CORS middleware: handles OPTIONS preflight automatically
CORS(
    app,
    resources={
        r"/chat": {"origins": cors_origins},
        r"/health": {"origins": cors_origins},
        r"/metrics": {"origins": cors_origins}
    },
    supports_credentials=False,
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept"],
    methods=["GET", "POST", "OPTIONS"]
)

log_event(f"CORS allowed origins: {allowed_origins_env}")

# --------- Routes ----------
@app.route("/health")
@limiter.limit("6 per minute")
def health():
    return jsonify({"status": "ok"})


@app.route("/metrics")
@limiter.limit("6 per minute")
def metrics():
    return jsonify({"requests_handled": "000000"})


@app.route("/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat():
    # --- Authenticate user ---
    header_token = request.headers.get("Authorization")
    user, err = validate_token(header_token, DATA_PATH)
    if not user:
        return jsonify({"error": err}), 401

    current_customer_id = user["customer_id"]
    log_event(f"Authenticated {current_customer_id}")

    # --- User input ---
    user_prompt = request.json.get("prompt", "")
    if not user_prompt:
        return jsonify({"error": "Missing 'prompt'"}), 400

    # --- Build system prompt ---
    system = (
        "System: You are a secure banking agent.\n"
        "Respond ONLY with a valid JSON object of the form:\n"
        "{ \"action\": \"<one of: clarify, get_balance, get_transactions, get_customer_info, transfer, freeze_account >\","
        "  \"params\": { ... } }\n"
        "Use these exact parameter patterns:\n"
        "  - get_balance → {}\n"
        "  - get_transactions → {\"n\":}\n"
        "  - get_customer_info → {}\n"
        "  - transfer → {\"to\":\"CUST###\",\"amount\":}\n"
        "  - freeze_account → {}\n"
        "  - clarify → {\"message\":\"Could you please specify what help you need — balance, transfer, or account info?\"}\n"
        "If you do not understand the user's request or it is unrelated to banking, respond with the 'clarify' action.\n"
        "Return ONLY the JSON object — no markdown, code fences, or plain text."
    )

    final_prompt = f"{system}\n\nUser: {user_prompt}"
    log_event(f"Prompt to LLM: {final_prompt}", current_customer_id)

    # --- Call LLM ---
    try:
        r = requests.post(LLM_URL, json={"prompt": final_prompt}, timeout=60)
        out = r.json().get("output", "")
        log_event(f"LLM Output: {out}", current_customer_id)
    except Exception as e:
        return jsonify({"llm": f"[llm-error] {e}", "executed": False})

    # --- Extract action ---
    action, params = extract_action_from_text(out)
    if not action:
        return jsonify({
            "clarification": "I didn't understand your request. "
                             "Would you like balance, transactions, info, transfer, or freeze account?"
        })

    # --- Execute action (if allowed) ---
    executed, result = False, None
    if action:
        if action == "clarify":
            result = params
            executed = False
        else:
            # validate action before executing
            is_valid, reason = validate_action(current_customer_id, action, params)
            log_event(f"is_valid, reason - {is_valid}, {reason}", "Action Validation: ")
            if not is_valid:
                reason = "Invalid action - " + reason
                result = {"error": reason}
                executed = False
            elif AUTO_EXECUTE:
                result = perform_action(action, params, DATA_PATH, current_customer_id)
                executed = True

        # ---- Generate human-friendly message ----
        user_message = ""

        if action == "clarify":
            user_message = result.get("message", "Could you please specify what help you need?")
        elif action == "get_balance" and executed and isinstance(result, dict):
            bal = result.get("balance")
            cur = result.get("currency", "USD")
            if bal is not None:
                user_message = f"Your current account balance is {bal:.2f} {cur}."
            else:
                user_message = "Unable to retrieve your balance."
        elif action == "get_transactions" and executed:
            txs = result.get("transactions", [])
            if txs:
                user_message = f"Here are your last {len(txs)} transactions."
            else:
                user_message = "No transactions found."
        elif action == "get_customer_info" and executed:
            user_message = "Here is your account information."
        elif action == "transfer" and executed:
            amt = result.get("amount")
            to = result.get("to")
            if amt and to:
                user_message = f"Transfer of ${amt:.2f} to {to} has been completed."
            else:
               user_message = f"Transfer could not be completed. Details: {json.dumps(result, ensure_ascii=False)}"
        elif action == "freeze_account" and executed:
            user_message = "Your account has been frozen as requested."
        elif not action:
            user_message = "I'm not sure what you meant. Could you clarify?"
        else:
            user_message = "Action executed."

    return jsonify({
        "authenticated_user": current_customer_id,
        "llm_output": out,
        "action": action,
        "params": params,
        "executed": executed,
        "action_result": result,
        "message": user_message
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5003))
    log_event(f"Starting agent server on 0.0.0.0:{port}, LLM_URL={LLM_URL}")
    app.run(host="0.0.0.0", port=port)
