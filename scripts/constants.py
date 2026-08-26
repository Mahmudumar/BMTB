# constants.py
from logging.handlers import RotatingFileHandler
import os
import json
import uuid
import logging
from pathlib import Path


__all__ = [
    "NOTES_DB", "NOTES_FOLDER",
    "RECOVERY_FILE", "PASS_FILE",
    "DATA_FOLDER", "LOGS_FILE",
    "BMA_DOWNLOAD_LINK", "APP_NAME",
    "APP_VERSION", "APP_ICON", "APP_PHOTO"
]

# --- License Management ---
PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnBOjHCBqpuw6de8jvHwv
T9VEdHmVOAxIQMIYjRtJnrhYSwFeN8YpWODDk6mPqOJMsGDApN/oJG4fqNW9NvTr
p3dz0SoU/1tZFMqX7WOqo0EaUiViOzCw3MFe83nnP4OW418+TLcivXlUFvUefxJi
VZ+liHmTPqWIJe1rW596h4yRtzgiTZKFLsvsg1Te6ngSHdwCTSSdcqR6QhQQkYzP
tzsNrK+dDT/IpbPOQ4yniByxqtHFhgXRrvoGZLUyxRetKsTvcfImirYL9rTS8ga3
o2blCB3/0uiqcqq1KaOFwmnEhzh+zGBEecgm23ot3AQlq9VMkSRQBmPLVTjJW3pH
lQIDAQAB
-----END PUBLIC KEY-----

"""


# --- App Info ---
APP_NAME = "Thought Book"
# for now, manually change
# the version to match the
# update.json and the deploy.
APP_VERSION = "2.1.0"
APP_SHORT_NAME = "BMTB"


# --- Helper Functions ---
# Always have this in other BM apps
def resource_path(relative_path="") -> Path:
    """Return absolute path to resource (works for dev & PyInstaller)."""
    try:
        # will run when Deployed
        base_path = Path("_internal") / "data" / relative_path
        if not base_path.exists():
            raise TypeError
    except TypeError:
        # Means it is run in debug mode
        base_path = Path(__file__).resolve().parent.parent

    return base_path


# --- Main Folders ---
MAIN_FOLDER = Path(__file__).resolve().parent.parent


# --- Images & Icons ---
IMGS_FOLDER = resource_path() / "imgs"
APP_ICON = IMGS_FOLDER / "logo.ico"
APP_PHOTO = IMGS_FOLDER / "logo.png"


# --- Data Storage (always under %APPDATA%/BM) ---
DATA_FOLDER = Path(os.getenv("APPDATA", "")) / "BM"
NOTES_FOLDER = DATA_FOLDER / APP_NAME
# Only create folders if they do not exist (avoid unnecessary disk operations)
if not NOTES_FOLDER.exists():
    NOTES_FOLDER.mkdir(parents=True)

HIDDEN_FOLDER = NOTES_FOLDER / f".{APP_SHORT_NAME.lower()}"
if not HIDDEN_FOLDER.exists():
    HIDDEN_FOLDER.mkdir(parents=True)


# --- Files ---
# Hidden files
LICENSE_FILE = HIDDEN_FOLDER / "license.json"
ID_FILE = HIDDEN_FOLDER / "config.json"
EMAIL_ID_FILE = HIDDEN_FOLDER / "email_config.json"
LICENSE_MESSAGE_FILE = HIDDEN_FOLDER / "license_msg.json"


# For updates system
DEPLOY_INFO_PATH = HIDDEN_FOLDER / "deploy.info"


NOTES_DB = NOTES_FOLDER / "BMTbnotes.db"
RECOVERY_FILE = NOTES_FOLDER / "recovery.key"
PASS_FILE = NOTES_FOLDER / "pass.pass"
FB_PATH = NOTES_FOLDER / "feedbacks.json"
SETTINGS_FILE = NOTES_FOLDER / "settings.json"
LOGS_FILE = NOTES_FOLDER / "app.log"


# --- Logging ---
# Use RotatingFileHandler to prevent slow startup from large log files
handler = RotatingFileHandler(LOGS_FILE, maxBytes=1_000_000, backupCount=3)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[handler]
)


def write_json_file(file, contents={}):
    """Must be in json"""
    try:

        with open(file, "w") as w:
            json.dump(contents, w)
    except Exception as e:
        logging.error(e)


def read_json_file(file):
    """Must be in json"""
    try:

        with open(file, "r") as r:
            contents = dict(json.load(r))

        return contents
    except Exception as e:
        logging.error(e)
        raise e


def read_txt_file(file):
    """Must be string"""
    with open(file, "r") as r:
        contents = r.read()
    return contents


def write_txt_file(file, contents=""):
    """Must be string"""
    with open(file, "r") as w:
        w.write(contents)
    return


def get_device_id(config_file):
    """Returns a persistent unique ID for this device/app install."""
    if os.path.exists(config_file):
        try:
            data = read_json_file(config_file)
            if "device_id" in data:
                return data["device_id"]
        except Exception:
            pass  # if file corrupted, regenerate

    # Generate new UUID and save it
    device_id = str(uuid.uuid4())
    write_json_file(config_file, {"device_id": device_id})
    # TODO: also save in reg
    return device_id


# --- Freemium specification files functionality ---

# This is the unique id for
# the app on each individual
# installation of bmtb
# config for unique device id

LICENSE_AMOUNT = 10_000
LICENSE_MESSAGE = f"""\
Welcome to {APP_NAME}!
You are currently using the free version.\n
Unlock the full version to enjoy:\n
    • Unlimited Notes
    • Autolock your thought book when you forget and leave thought book open.

To activate, please paste your License Key below.

If you don’t have a license yet, click below to purchase one.
"""
MAX_NOTE_AMOUNT = 100
PREMIUM_FEATURES = ["unlimited_notes", "autolock"]
MAX_REMINDER_ABOUT_UPGRADE = 3


# AutoUpdater
UPDATE_DOWNLOAD_FOLDER = Path(os.path.join(
    os.path.expanduser("~"), f"{APP_SHORT_NAME}_updates"))


# --- External Links ---
BMA_DOWNLOAD_LINK = "https://github.com/Mahmudumar/BMA/releases/latest"
BMTB_DOWNLOAD_LINK = "https://github.com/tech-naija-rise/BMTB/releases/latest"
BMTB_DOWNLOAD_LINK2 = "https://tech-naija-rise.github.io/BMTB_webpage/"

BMTB_FEEDBACK_SERVER = "https://feedback-server-tnr.onrender.com/feedback"
TNR_BMTB_SERVER = "https://feedback-server-tnr.onrender.com"
# TNR_BMTB_SERVER_TEST = "http://localhost:5555"


if __name__ == "__main__":
    print(f"Main folder: {MAIN_FOLDER}")
    print(f"Data folder: {DATA_FOLDER}")
    print(f"Device ID: {get_device_id(ID_FILE)}")
    print(f"App version: {APP_VERSION}")
    print(f"App ICON: {APP_ICON}")
    pass
