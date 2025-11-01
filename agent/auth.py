import base64
from utils import load_data

def validate_token(header_token, data_path):
    """
    Validate Authorization: Basic <base64>
    Returns (customer_dict, error_msg)
    """
    if not header_token:
        return None, "Missing Authorization header"

    parts = header_token.split()
    if len(parts) != 2 or parts[0].lower() != "basic":
        return None, "Invalid Authorization format"

    token = parts[1].strip()
    data = load_data(data_path)

    for c in data["customers"]:
        if c.get("auth_token_b64") == token:
            return c, None

    return None, "Invalid or unknown token"
