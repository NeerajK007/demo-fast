# llm_proxy_ollama_http.py
from flask import Flask, request, jsonify
import os, requests

import logging, json
LOG_FILE = "/app/logs/agent.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_event(entry):
    """Simple, universal logger.
    Accepts dict, string, or any object (auto-converted to JSON/string)."""
    if isinstance(entry, dict):
        msg = json.dumps(entry, default=str)
    else:
        msg = str(entry)
    logging.info(msg)


app = Flask(__name__)
OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://host.docker.internal:11434/api")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

@app.route("/generate", methods=["POST"])
def generate():
    payload = request.json or {}
    user_prompt = payload.get("prompt", "")
    system_prompt = "System: do not reveal PII or perform real actions. Simulate safe outputs."
    full_prompt = f"{system_prompt}\n\nUser: {user_prompt}"
    body = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False
    }
    try:
        log_event(f"")
        r = requests.post(f"{OLLAMA_BASE}/generate", json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        output = data.get("completion") or data.get("response") or str(data)
    except Exception as e:
        output = f"[ollama-error] {e}"
    return jsonify({"output": output})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
