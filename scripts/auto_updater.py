from PyQt5.QtWidgets import  QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QMetaObject, Qt
from concurrent.futures import ThreadPoolExecutor
import time
from .threading import Signals
import re
import logging
import requests
import os
import subprocess


from pathlib import Path
from packaging import version

from .constants import (logging, APP_VERSION,
                        APP_NAME, APP_SHORT_NAME,
                        UPDATE_DOWNLOAD_FOLDER,
                        TNR_BMTB_SERVER)

class AutoUpdater:
    def get_update_available(self):
        return self.update_available

    def __init__(self, parent):
        self.parent = parent
        self.update_available = False
        self.latest_version = None
        self.download_url = None
        self.notes = ""

        UPDATE_DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    def _check(self, signal:Signals):
        try:
            signal.progress.emit("Checking for updates...")

            response = requests.post(
                f"{TNR_BMTB_SERVER}/check_updates",
                json={
                    "app_name": APP_NAME,
                    "app_version": APP_VERSION
                },
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            latest_version = data.get("latest_version", "")
            url = data.get("url", "")
            notes = data.get("notes", "")

            if not latest_version or not url:
                self.update_available = False
                signal.finished.emit()
                return False

            self.latest_version = latest_version
            self.download_url = url
            self.notes = notes

            if version.parse(latest_version) > version.parse(APP_VERSION):
                self.update_available = True
                logging.info(
                    f"Update available: {APP_VERSION} -> {latest_version}"
                )
                signal.finished.emit()
                return True

            self.update_available = False
            logging.info("Software is up to date")
            signal.finished.emit()
            return False

        except Exception as e:
            self.update_available = None
            logging.error(f"Update check failed: {e}")
            signal.finished.emit()
            return None


    def download_update(self, signal):
        if not self.download_url:
            raise RuntimeError("No update URL available")

        url = self.download_url
        filename = UPDATE_DOWNLOAD_FOLDER / url.split("/")[-1]

        try:
            signal.progress.emit("Downloading update...")

            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()

                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total:
                            percent = int(downloaded * 100 / total)
                            signal.progress.emit(percent)

            logging.info(f"Update downloaded: {filename}")

            return filename

        except Exception:
            if filename.exists():
                filename.unlink()

            raise

    def launch_installer(self, installer_path):
        logging.info(f"Launching installer: {installer_path}")

        subprocess.Popen(
            [str(installer_path), "/S"],
            close_fds=True
        )

        self.parent.close()