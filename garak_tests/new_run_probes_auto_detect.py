#!/usr/bin/env python3
"""
run_probes_auto_detect.py

Runs Garak prompt-injection and jailbreak probes against your REST LLM agent.

- Loads customer creds from data/customers_transactions.json
- Uses single customer (CUSTOMER_ID env var or first)
- Sends Authorization: Basic <auth_token_b64>
- Robustly extracts LLM response text (llm_output / llm / etc.)
- Handles JSON-encoded string values inside the LLM field
- Avoids TypeError / KeyError by accepting *args, **kwargs for _call_model
- Saves report to /tmp/garak_promptinj_jailbreak_report.jsonl
"""

import json
import os
import traceback
from types import SimpleNamespace
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests
import types

# garak imports
import garak._config as _config
from garak.generators.rest import RestGenerator
from garak.probes.promptinject import HijackLongPrompt
from garak.probes.dan import DAN_Jailbreak

# ==== CONFIG ====
URI = "http://localhost:5003/chat"
CUSTOMERS_FILE = "data/customers_transactions.json"
REPORT_PATH = "/tmp/garak_promptinj_jailbreak_report.jsonl"
REQUEST_TIMEOUT = 120
GENERATIONS_PER_PROMPT = 3
CUSTOMER_ID = os.environ.get("CUSTOMER_ID", None)  # e.g. CUST001
# ================

# ---- Setup Garak transient config ----
if not hasattr(_config, "transient") or _config.transient is None:
    _config.transient = SimpleNamespace()
if not hasattr(_config.transient, "cache_dir") or _config.transient.cache_dir is None:
    _config.transient.cache_dir = Path("/tmp/garak_cache")
Path(_config.transient.cache_dir).mkdir(parents=True, exist_ok=True)
os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
_config.transient.reportfile = open(REPORT_PATH, "a", encoding="utf-8")

# ---- Helpers ----
def load_customers(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("customers", [])
    except Exception as e:
        print(f"❌ Failed to read {file_path}: {e}")
        return []

def pick_customer(customers: List[Dict[str, Any]], cid: Optional[str]) -> Optional[Dict[str, Any]]:
    if not customers:
        return None
    if cid:
        for c in customers:
            if c.get("customer_id") == cid:
                return c
        print(f"⚠️ Customer {cid} not found; using first customer.")
    return customers[0]

def unwrap_json_string(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        s = val.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                parsed = json.loads(s)
                return json.dumps(parsed)
            except Exception:
                return val
        return val
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    return str(val)

def extract_text_from_response(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return extract_text_from_response(obj[0]) if obj else ""
    if isinstance(obj, dict):
        # prefer keys containing 'llm'
        for key in obj.keys():
            if isinstance(key, str) and "llm" in key.lower():
                return unwrap_json_string(obj[key])
        # fallback known keys
        for cand in ["llm_output", "response", "result", "text", "message", "output"]:
            if cand in obj:
                return unwrap_json_string(obj[cand])
        # otherwise return full json
        return json.dumps(obj)
    return str(obj)

def parse_ndjson(resp: requests.Response) -> List[Any]:
    out = []
    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # if line isn't JSON, include raw line as string
                out.append(line)
    except Exception:
        pass
    return out

# ---- Build generator with robust custom _call_model ----
def build_generator(uri: str, headers: Dict[str, str]) -> RestGenerator:
    g = RestGenerator(uri=uri)
    g.method = "post"
    g.headers = headers
    g.req_template_json_object = {"prompt": "$INPUT"}
    g.req_template = json.dumps(g.req_template_json_object)
    g.response_json = True
    g.request_timeout = REQUEST_TIMEOUT
    g.supports_multiple_generations = False

    # Robust _call_model replacement: accept arbitrary args and kwargs
    def _safe_call_model(self, *args, **kwargs):
        """
        Signature accepts (self, *args, **kwargs) to match what Garak may call.
        Extract the prompt from args[0] or kwargs; ignore extra args.
        Returns list[str] as expected by Garak.
        """
        # Extract prompt
        prompt_text = None
        if args and len(args) >= 1:
            # often it's (prompt_text,) or (prompt_text, some_attempt_index)
            prompt_text = args[0]
        elif "prompt" in kwargs:
            prompt_text = kwargs.get("prompt")
        elif "prompt_text" in kwargs:
            prompt_text = kwargs.get("prompt_text")
        else:
            # fallback: use empty prompt
            prompt_text = ""

        # Build payload — keep simple, match the server's expected shape
        payload = {"prompt": prompt_text}
        try:
            resp = requests.post(uri, json=payload, headers=g.headers, timeout=g.request_timeout)
        except Exception as e:
            # let Garak's backoff/retry handle network errors if needed
            raise

        ctype = (resp.headers.get("Content-Type") or "").lower()

        # NDJSON or chunked streaming
        if "ndjson" in ctype or "application/x-ndjson" in ctype or resp.headers.get("Transfer-Encoding", "").lower() == "chunked":
            objs = parse_ndjson(resp)
            for obj in objs:
                t = extract_text_from_response(obj)
                if t:
                    return [t]
            return [resp.text or ""]

        # Try JSON
        try:
            data = resp.json()
        except Exception:
            return [resp.text or ""]

        # Extract LLM text
        text = extract_text_from_response(data)
        if text:
            return [text]

        # Fallback: return complete JSON as string
        try:
            return [json.dumps(data)]
        except Exception:
            return [str(data)]

    # Bind method to instance (correctly handles self)
    g._call_model = types.MethodType(_safe_call_model, g)
    return g

# ---- Prepare probe defaults ----
def prepare_probe_instance(probe, generations=GENERATIONS_PER_PROMPT):
    defaults = {
        "parallel_attempts": 1,
        "parallel_requests": False,
        "generations": generations,
        "seed": None,
        "deprefix": False,
    }
    for k, v in defaults.items():
        if not hasattr(probe, k):
            setattr(probe, k, v)
    return probe

# ---- Main ----
def main():
    customers = load_customers = load_customers if False else None  # no-op to help some editors (ignored)
    customers = load_customers = None  # avoid lint-issue; we will call real loader below

    # load customers properly
    def _load_customers(fp):
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                return data.get("customers", []) if isinstance(data, dict) else []
        except Exception:
            print(f"Could not load customers from {fp}")
            traceback.print_exc()
            return []

    customers = _load_customers(CUSTOMERS_FILE)
    if not customers:
        print(f"❌ No customers found in {CUSTOMERS_FILE}")
        return

    cust = pick_customer(customers, CUSTOMER_ID)
    if not cust:
        print("❌ No customer selected or found.")
        return

    cid = cust.get("customer_id", "<unknown>")
    token = cust.get("auth_token_b64", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Basic {token}"

    print(f"🔐 Selected customer: {cid}")
    print(f"🦜 Using endpoint: {URI}")

    # Build patched generator
    g = build_generator(URI, headers)
    print("🦜 loading generator: REST:", URI)

    probes = [
        ("promptinject.HijackLongPrompt", HijackLongPrompt),
        ("dan.DAN_Jailbreak", DAN_Jailbreak),
    ]

    summary = {}

    for pname, ProbeClass in probes:
        print(f"\n--- Running probe: {pname} ---")
        try:
            probe = ProbeClass()
        except Exception as e:
            print("Failed to instantiate probe", pname, e)
            traceback.print_exc()
            continue

        probe = prepare_probe_instance(probe, GENERATIONS_PER_PROMPT)
        try:
            attempts = probe.probe(g)
        except Exception as e:
            print(f"❌ Probe {pname} failed: {type(e).__name__} {e}")
            traceback.print_exc()
            summary[pname] = {"error": str(e)}
            continue

        out = []
        for a in attempts:
            prompt = getattr(a, "prompt", "<unknown>")
            outputs = getattr(a, "outputs", [])
            detections = getattr(a, "detections", None)
            out.append({"prompt": prompt, "outputs": outputs, "detections": detections})
        summary[pname] = out
        print(f"✅ Completed probe {pname} ({len(out)} attempts)")

    # Print human summary
    print(f"\n==== Human summary for {cid} ====\n")
    for pname, attempts in summary.items():
        print(f"Probe: {pname}")
        if isinstance(attempts, dict) and "error" in attempts:
            print("  ERROR:", attempts["error"])
            continue
        for i, att in enumerate(attempts, start=1):
            print(f"  Attempt #{i}: {att['prompt']}")
            for j, o in enumerate(att.get("outputs", [])):
                print(f"    → Output[{j}]: {o[:160]}...")
            if att.get("detections"):
                print("    ⚠️ Detections:", att["detections"])
        print("")

    print(f"📄 Full JSONL report saved at: {REPORT_PATH}")


if __name__ == "__main__":
    main()
