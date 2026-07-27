import re
from typing import Optional


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


def validate_username(user_name: str) -> str:
    if len(user_name) < 3:
        raise ValueError("Username must be at least 3 characters")
    return user_name


def normalize_admin_role(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized == "admin":
            return "admin"
        raise ValueError("Admin field must be empty or 'admin'")
    return None


def normalize_lock_status(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized == "lock":
            return "lock"
        raise ValueError("Lock field must be empty or 'lock'")
    return None
