from jsonschema import validate, ValidationError
import re

from extractor import ALLOWED_ACTIONS

LLM_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["action", "params"],
    "properties": {
        "action": {"type": "string", "enum": list(ALLOWED_ACTIONS)},
        "params": {"type": "object"}
    },
    "additionalProperties": False
}

def validate_llm_output(obj):
    try:
        validate(instance=obj, schema=LLM_RESPONSE_SCHEMA)
        return True, None
    except ValidationError as e:
        return False, str(e)

def risk_score_from_text(text):
    reasons, score = [], 0
    if "ignore" in text.lower():
        score += 40
        reasons.append("System override attempt")
    if re.search(r"ssn|social security", text, re.I):
        score += 50
        reasons.append("Possible PII access attempt")
    if "execute" in text.lower():
        score += 20
        reasons.append("Execution-style language")
    return score, reasons

def conservative_intent_check(user_prompt, parsed_action):
    text = user_prompt.lower()
    if "balance" in text and parsed_action != "get_balance":
        return False, "User asked about balance but parsed action differs"
    if "transfer" in text and parsed_action != "transfer":
        return False, "Transfer intent mismatch"
    return True, None
