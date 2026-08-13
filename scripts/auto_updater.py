from PyQt5.QtWidgets import QApplication, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import QMetaObject, Qt, pyqtSlot
from concurrent.futures import ThreadPoolExecutor
import time
import sys
import re
import logging
import requests
import os
import subprocess
import threading

from pathlib import Path
from packaging import version

from .constants import (logging, APP_VERSION,
                        APP_NAME, APP_SHORT_NAME,
                        UPDATE_DOWNLOAD_FOLDER,
                        TNR_BMTB_SERVER)


class AutoUpdater:
    def __init__(self, parent):
        self.parent = parent
        self.update_available = False
        self.prompt_msg = ""

        if not UPDATE_DOWNLOAD_FOLDER.exists():
            os.makedirs(UPDATE_DOWNLOAD_FOLDER, exist_ok=True)

    def _check(self):
        try:
            app_info = {
                "app_name": APP_NAME,
                "app_version": APP_VERSION
            }

            post_my_info = requests.post(
                f"{TNR_BMTB_SERVER}/check_updates", json=app_info)
            # print(post_my_info)

            data = dict(post_my_info.json())
            post_my_info.raise_for_status()
            latest_version = data.get('latest_version', '')
            url = data.get('url', '')
            notes = data.get('notes', '')
            # print(data)
            logging.info(f"Latest Version found: {latest_version}")

            # XXX: remove 'not', only meant for testing
            if not (version.parse(latest_version) > version.parse(APP_VERSION)):
                print(f"Latest Version found: {latest_version}")
                # self.prompt_update(latest_version, notes, url)
                # self.download_and_install(url)
                self.update_available = True
                return True
            else:
                logging.info("Software up to date")
                print("uptodate")
                self.update_available = False
                return False

        except Exception as e:
            self.update_available = None
            print(f"check failed: {e}")
            logging.error(f"Update check failed: {e}")
            return None

    def get_update_available(self):
        return self.update_available

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


class InstallerApp(QWidget):

    def __init__(self):
        super().__init__()
        # 1. Thread pool manager
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("App Installer")
        self.resize(350, 150)

        # 2. UI Widgets
        self.status_label = QLabel("Ready to install.", self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.start_button = QPushButton("Install Now", self)
        self.start_button.clicked.connect(self.start_installation)

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.start_button)
        self.setLayout(layout)

    # 3. The background installation target (Run in another thread)
    def run_installer_process(self):
        steps = ["Extracting files...", "Copying assets...",
                 "Creating shortcuts...", "Cleaning up..."]

        for i, step in enumerate(steps):
            # Update the UI text safely via Thread-Safe Method Invocation
            QMetaObject.invokeMethod(
                self.status_label, "setText", Qt.QueuedConnection, Q_ARG(str, step))

            # Simulate a chunk of download/install work
            time.sleep(1)

            # Calculate and update progress percentage
            progress = int(((i + 1) / len(steps)) * 100)
            QMetaObject.invokeMethod(
                self.progress_bar, "setValue", Qt.QueuedConnection, Q_ARG(int, progress))

        return "Installation Completed Successfully!"

    def start_installation(self):
        self.start_button.setEnabled(False)
        self.progress_bar.setValue(0)

        # 4. Push the installer task to the background thread
        future = self.executor.submit(self.run_installer_process)

        # 5. Catch the final return value when finished
        future.add_done_callback(self.on_installation_finished)

    # 6. Callback executed when the installer finishes
    def on_installation_finished(self, future):
        try:
            # Catch the return string from our background function
            final_result = future.result()

            # Safely push final updates to the GUI thread
            QMetaObject.invokeMethod(
                self.status_label, "setText", Qt.QueuedConnection, Q_ARG(str, final_result))
        except Exception as e:
            QMetaObject.invokeMethod(
                self.status_label, "setText", Qt.QueuedConnection, Q_ARG(str, f"Error: {str(e)}"))
        finally:
            # Re-enable the button via UI thread safety
            QMetaObject.invokeMethod(
                self.start_button, "setEnabled", Qt.QueuedConnection, Q_ARG(bool, True))
