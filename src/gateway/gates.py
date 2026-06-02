import hmac
from typing import Optional

MAX_PAYLOAD_BYTES = 1024 * 1024

def authenticate_handshake(
        token: Optional[str],
        auth: dict,
) -> dict:
    mode = auth.get("mode", "token")

    if mode == "none":
        return {"ok": True, "role": "user", "method": "none"}

    if mode == "token":
        if not token:
            return {"ok": False, "reason": "token_required"}
        expected = auth.get("token", "")
        if not hmac.compare_digest(token, expected):
            return {"ok": False, "reason": "invalid_token"}
        return {"ok": True, "role": "user", "method": "token"}

    if mode == "password":
        if not token:
            return {"ok": False, "reason": "password_required"}
        expected = auth.get("password", "")
        if not hmac.compare_digest(token, expected):
            return {"ok": False, "reason": "invalid_password"}
        return {"ok": True, "role": "user", "method": "password"}

    return {"ok": False, "reason": f"unknown_auth_mode:{mode}"}

def authorize_gateway_method(
        method: str,
        auth: dict,
        descriptor: Optional[dict] = None,
) -> Optional[dict]:
    if not auth.get("ok"):
        return {"code": "UNAUTHORIZED", "message": "Authentication required"}

    if descriptor is None:
        return None

    required_role = descriptor.get("required_role")
    if required_role and auth.get("role") != required_role:
        return {"code": "FORBIDDEN", "message": "Insufficient role"}

    required_scopes = descriptor.get("required_scopes")
    if required_scopes:
        auth_scopes = auth.get("scopes", [])
        if not all(s in auth_scopes for s in required_scopes):
            return {"code": "FORBIDDEN", "message": "Missing required scopes"}

    return None

def validate_payload_size(
        data: str,
        max_bytes: int = MAX_PAYLOAD_BYTES,
) -> dict:
    size = len(data.encode("utf-8"))
    if size <= max_bytes:
        return {"ok": True, "size": size}
    return {"ok": False, "size": size}