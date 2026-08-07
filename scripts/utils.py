import requests
import re
import hashlib
import os
from .constants import (RECOVERY_FILE, logging,)
import winreg

def set_user_env_var(name, value):
    reg_path = r"Environment"
    reg_key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        reg_path,
        0,
        winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(reg_key, name, 0, winreg.REG_SZ, value)
    winreg.CloseKey(reg_key)
    logging.info(f"[+] User variable '{name}' set to '{value}'")

def set_recovery_key(code: str):
    hashed = hashlib.sha256(code.encode('utf-8')).hexdigest()
    with open(RECOVERY_FILE, 'w') as f:
        f.write(hashed)

def verify_recovery_key(code: str) -> bool:
    if not os.path.exists(RECOVERY_FILE):
        return False
    entered_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()
    with open(RECOVERY_FILE, 'r') as f:
        stored_hash = f.readline().strip()
    return entered_hash == stored_hash

def count_words_in_string(text):
    words = re.findall(r'\b\w+\b', text)
    return len(words)

def has_internet():
    try:
        requests.get("https://www.google.com", timeout=3)
        return True
    except Exception:
        return False

def connected_to_server(url):
    try:
        logging.info(f"Attempting to connect to server at '{url}'")
        response = requests.get(url, timeout=60)

        if 200 <= response.status_code < 300:
            logging.info("Connected to server successfully!")
            return True
        else:
            logging.warning(
                f"Server responded with status code: {response.status_code}")
            return False

    except requests.Timeout:
        logging.error("Connection timed out.")
        return False
    except requests.ConnectionError:
        logging.error("Failed to connect to server.")
        return False
    except requests.RequestException as e:
        logging.error(f"An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    pass