from PyQt5.QtWidgets import (
    QDialog, QMessageBox, QProgressBar, QLabel, QVBoxLayout, QPushButton
)
from PyQt5.QtCore import Qt, QCoreApplication
from PyQt5.QtWidgets import QDialog, QProgressBar, QLabel, QVBoxLayout
from PyQt5.QtWidgets import QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget
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

from .constants import (TNR_BMTB_WEBPAGE, logging, APP_VERSION,
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
        self.installer_path = UPDATE_DOWNLOAD_FOLDER / \
            f"{APP_SHORT_NAME}_Latest.exe"

    def _check(self, signal: Signals):
        try:

            # signal.progress.emit("started")
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

    def cleanup_cancelled_download(self):
        if self.installer_path.exists():
            self.installer_path.unlink(missing_ok=True)

    def download_update(self, signal: Signals):
        if not self.download_url:
            raise RuntimeError("No update URL available")


        url = str(self.download_url)
        if url.strip():
            self.installer_path = UPDATE_DOWNLOAD_FOLDER / url.split("/")[-1]

        if self.installer_path.exists():
            try:
                if self.launch_installer() is None:
                    print("Incomplete download or another error")
                    print("Trying to start auto download")
            except Exception as e:
                print(e)
                pass

        try:
            signal.progress.emit("Started")

            with requests.get(url, stream=True, timeout=30) as response:
                response.raise_for_status()

                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(self.installer_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total:
                            percent = int(downloaded * 100 / total)
                            signal.update_percent.emit(percent)

            logging.info(f"Update downloaded: {self.installer_path}")
            signal.finished.emit()

            return self.installer_path

        except Exception:
            self.delete_installer_path()
            raise

    def delete_installer_path(self):
        if self.installer_path.exists():
            self.installer_path.unlink()
            print(f"Deleted {self.installer_path}")

    def launch_installer(self, installer_path=""):
        try:
            if installer_path:
                self.installer_path = installer_path
            logging.info(f"Launching installer: {self.installer_path}")

            subprocess.Popen(
                [str(self.installer_path)],
                close_fds=True
            )
            self.parent.close()
            return True

        except OSError:
            print("We need to manually get the update to the user.")
            import webbrowser

            def go_manually():
                print("Opening browser")
                try:
                    self.parent.inform_user("Opening Browser for Manual Update")
                except Exception:
                    pass

                webbrowser.open_new_tab(TNR_BMTB_WEBPAGE)
                self.delete_installer_path()

            question: QMessageBox = self.parent.ask_question("Auto Update failed","The Automatic Update failed. Would you like to go to the website to manually download and update?")
            yes = question.addButton("Yes", question.ButtonRole.YesRole)
            no = question.addButton("No, Later", question.ButtonRole.NoRole)
            yes.clicked.connect(go_manually)
            question.exec()
            return False
        
        except Exception as e:
            print(e)
            return
        


class ProgressDialog(QDialog):
    def __init__(self, signal: Signals, parent=None):
        super().__init__(parent=parent)

        self.setWindowTitle("Processing")
        self.setFixedSize(350, 160)

        self.cancelled = False
        self.signal = signal

        self.status = QLabel("Starting...")
        self.status.setAlignment(Qt.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        self.percent = QLabel("0%")
        self.percent.setAlignment(Qt.AlignCenter)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.percent)
        layout.addWidget(self.cancel_button)

    def update_progress(self, percent, status="Processing..."):
        self.progress.setValue(percent)
        self.percent.setText(f"{percent}%")
        self.status.setText(status)

        QCoreApplication.processEvents()

    def cancel(self):
        self.cancelled = True
        self.status.setText("Cancelling...")
        self.signal.update_cancelled.emit()
        self.cancel_button.setEnabled(False)
