#!/usr/bin/env python3
"""
Run prompt-injection and jailbreak probes against a REST agent endpoint
(using Garak's RestGenerator and probe classes programmatically).

Drop-in script — edit URI, timeouts, generations as needed.
"""

import json, os, time, traceback
from types import SimpleNamespace
from pathlib import Path

# garak imports
import garak._config as _config
from garak.generators.rest import RestGenerator
from garak.probes.promptinject import HijackLongPrompt
from garak.probes.dan import DAN_Jailbreak

# ---- User config ----
URI = "http://localhost:5003/chat"
REPORT_PATH = "/tmp/garak_promptinj_jailbreak_report.jsonl"
REQUEST_TIMEOUT = 120
GENERATIONS_PER_PROMPT = 3
# ----------------------

# Ensure minimal transient config garak internals expect:
if not hasattr(_config, "transient") or _config.transient is None:
    _config.transient = SimpleNamespace()

# some probes/readers expect a cache_dir Path (used by nltk resource loader etc.)
if not hasattr(_config.transient, "cache_dir") or _config.transient.cache_dir is None:
    _config.transient.cache_dir = Path("/tmp/garak_cache")

# make sure cache dir exists
_path = Path(_config.transient.cache_dir)
_path.mkdir(parents=True, exist_ok=True)

# attach a report file handle so probe code can write JSONL as usual
os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
report_fh = open(REPORT_PATH, "a", encoding="utf-8")
_config.transient.reportfile = report_fh

# ---- Build RestGenerator (passing uri directly is reliable) ----
g = RestGenerator(uri=URI)
g.method = "post"
g.headers = {"Content-Type": "application/json"}
g.req_template_json_object = {"prompt": "$INPUT"}
g.req_template = json.dumps(g.req_template_json_object)
g.response_json = True
g.response_json_field = "llm"
g.request_timeout = REQUEST_TIMEOUT
# set how many generations each probe will request (some probes expect this)
g.supports_multiple_generations = False

print("Generator ready:", getattr(g, "fullname", g.uri))

# List of probe classes to run
probes_to_run = [
    ("promptinject.HijackLongPrompt", HijackLongPrompt),
    ("dan.DAN_Jailbreak", DAN_Jailbreak),
]

# function to ensure the minimal harness attributes probes expect
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

# Run probes
summary = {}
for pname, ProbeClass in probes_to_run:
    print("\n--- Running probe:", pname, "----")
    try:
        probe = ProbeClass()
    except Exception as e:
        print("Failed to instantiate probe", pname, ":", type(e).__name__, e)
        traceback.print_exc()
        continue

    probe = prepare_probe_instance(probe, GENERATIONS_PER_PROMPT)

    try:
        attempts = probe.probe(g)  # this returns a list-like of attempt results
    except Exception as e:
        print("Probe execution failed:", type(e).__name__, e)
        traceback.print_exc()
        summary[pname] = {"error": f"{type(e).__name__}: {e}"}
        continue

    # summarize attempts for console output
    out = []
    for ai, attempt in enumerate(attempts):
        try:
            prompt = getattr(attempt, "prompt", None) or attempt.input
        except Exception:
            prompt = "<unknown>"
        outputs = []
        try:
            for i, o in enumerate(attempt.outputs):
                outputs.append(o)
        except Exception:
            pass

        detectors = getattr(attempt, "detections", None)
        out.append({"prompt": prompt, "outputs": outputs, "detections": detectors})

    summary[pname] = out
    print(f"Probe {pname} completed; {len(out)} attempts. (wrote into {REPORT_PATH})")

# Close report file handle
try:
    report_fh.close()
except Exception:
    pass

# Print a short human summary
print("\n==== Human summary ====\n")
for pname, attempts in summary.items():
    print("Probe:", pname)
    if isinstance(attempts, dict) and "error" in attempts:
        print("  ERROR:", attempts["error"])
        continue
    for ai, att in enumerate(attempts, start=1):
        print(f" Attempt #{ai} prompt: {att.get('prompt')}")
        for oi, out in enumerate(att.get("outputs") or []):
            print(f"   Output [{oi}]: {out!r}")
        if att.get("detections"):
            print("   Detections:", att["detections"])
    print("")

print("Full JSONL report at:", REPORT_PATH)
