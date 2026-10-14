import hashlib
from datetime import datetime
from flask import session, render_template

from app_v2.config import Config, AppState

TABLE_CLASS = Config.TABLE_CLASS

def hashPassword(password):
    return hashlib.sha256(password.encode()).hexdigest()

def formatLocalTime(timestamp):
    if str(timestamp).isdigit():
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp)

def formatId(entity_type, id_value):
    prefix = Config.ID_PREFIXES[entity_type]
    return prefix + str(int(id_value)).zfill(3)

def parseId(id_value):
    id_str = str(id_value).strip().upper()
    for prefix in Config.ID_PREFIXES.values():
        if id_str.startswith(prefix):
            num_part = id_str[len(prefix):]
            if num_part.isdigit():
                return int(num_part)
    return int(id_str)

def isFormattedId(value):
    id_str = str(value).strip().upper()
    for prefix in Config.ID_PREFIXES.values():
        if id_str.startswith(prefix):
            num_part = id_str[len(prefix):]
            if num_part.isdigit():
                return True
    return False

def isLegacyRecord(stored_hash):
    stored_hash = str(stored_hash).strip()
    return stored_hash.startswith("uploads/") or stored_hash.startswith("uploads\\")

def mustBeRole(role, login_template, msg="Please login first"):
    if session.get("role") != role:
        return render_template(login_template, msg=msg)
    return None

def escapeHtml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def isTextContent(file_name, plain_bytes):
    name = str(file_name).lower()
    if name.endswith(".txt") or name in ("record_text.txt", "prescription_text.txt"):
        return True
    text = plain_bytes.decode("utf-8", errors="replace")
    if len(text) == 0:
        return False
    printable = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    return printable / len(text) > 0.85
