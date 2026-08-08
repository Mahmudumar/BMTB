import re
import logging
import requests
import os
import subprocess
import threading

from pathlib import Path
from packaging import version


from PyQt5.QtWidgets import QMessageBox

from .constants import (logging, APP_VERSION,
                        APP_NAME, APP_SHORT_NAME,
                        UPDATE_DOWNLOAD_FOLDER,
                        UPDATE_INFO_URL)


class AutoUpdater:
    def __init__(self, parent, auto_install=True, show_if_up_to_date=False):
        self.parent = parent
        self.auto_install = auto_install
        self.show_uptodate = show_if_up_to_date

        if not UPDATE_DOWNLOAD_FOLDER.exists():
            os.makedirs(UPDATE_DOWNLOAD_FOLDER, exist_ok=True)

    def check_update_background(self):
        """Run version check in background thread
          SILENTLY by default."""
        threading.Thread(target=self._check, daemon=True).start()

    def check_update_and_prompt(self):
        self.auto_install = False  # prompt before starting update
        self.check_update_background()

    def _check(self):
        try:
            resp = requests.get(UPDATE_INFO_URL)
            resp.raise_for_status()
            data = resp.json()
            latest_version = data['latest_version']
            url = data['url']
            notes = data.get('notes', "")
            logging.info(f"Latest Version found: {latest_version}")

            if (version.parse(latest_version) > version.parse(APP_VERSION)):
                logging.info(f"Latest Version found: {latest_version}")
                if self.auto_install:
                    self.download_and_install(url)
                else:
                    self.prompt_update(latest_version, notes, url)
            else:
                logging.info("Software up to date")
                QMessageBox.information(None,
                                        "Up to Date", f"Your {APP_NAME} is up to date")
        except Exception as e:
            logging.error(f"Update check failed: {e}")

    def prompt_update(self, latest_version, notes, url):
        """Ask user for update, non-blocking."""

        msg = (f"{APP_NAME} v{latest_version} is "
               "available.\nDo you want to update now?")

        QMessageBox.information(None, f"{APP_NAME} Update", msg)
        self.download_and_install(url)

    def download_and_install(self, url):
        """Download installer with optional progress hook."""
        filename = os.path.join(UPDATE_DOWNLOAD_FOLDER, url.split("/")[-1])
        try:
            r = requests.get(url, stream=True)
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0

            with open(filename, 'wb') as f:
                logging.info("Downloading update")
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            # Run installer
            subprocess.Popen([filename, "/S"], shell=True)

            logging.info(f"Finished installation: '{filename}'")
        except Exception as e:
            logging.error(f"Update failed: '{e}'")

            # Delete if failed to avoid bloatware.
            if os.path.exists(filename):
                os.remove(filename)

    def delete_prev_versions(self, APP_VERSION):
        current_folder = Path(__file__).parent
        new_version_detected = False

        # Check if the new version is installed
        for file in current_folder.iterdir():
            if not file.is_file():
                continue

            match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", file.name)
            if match:
                file_version = version.parse(match.group(1))
                if file_version == version.parse(APP_VERSION):
                    new_version_detected = True
                    break

        # If the new version is confirmed, delete older versions
        if new_version_detected:
            for file in current_folder.iterdir():
                if not file.is_file():
                    continue

                match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", file.name)
                if match:
                    file_version = version.parse(match.group(1))
                    if (file_version < version.parse(APP_VERSION)):
                        try:
                            file.unlink()
                            logging.info(f"Deleted old version: {file.name}")
                        except Exception as e:
                            logging.error(f"Failed to delete {file.name}: {e}")
        else:
            logging.info("New version not detected. No files deleted.")
