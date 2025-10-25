import requests
import os
import subprocess
import threading

from packaging import version

import customtkinter as ctk
from tkinter import messagebox as tkmsg

from .constants import (logging, APP_VERSION,
                        APP_NAME, APP_SHORT_NAME,
                        UPDATE_DOWNLOAD_FOLDER,
                        UPDATE_INFO_URL)


class AutoUpdater:
    def __init__(self, parent, auto_install=True):
        self.parent = parent
        self.auto_install = auto_install
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
            resp = requests.get(UPDATE_INFO_URL, timeout=5)
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
                if not self.auto_install:
                    tkmsg.showinfo("Up to Date",f"Your {APP_NAME} is up to date")

        except Exception as e:
            # Silent fail for background updates
            logging.error(f"Update check failed: {e}")

    def prompt_update(self, latest_version, notes, url):
        """Ask user for update, non-blocking."""
        msg = (f"{APP_NAME} v{latest_version} is "
               "available.\nDo you want to update now?")
        if tkmsg.askyesno(f"{APP_SHORT_NAME} Update", msg):
            self.download_and_install(url, show_progress=True)

    def download_and_install(self, url, show_progress=False):
        """Download installer with optional progress hook."""
        filename = os.path.join(UPDATE_DOWNLOAD_FOLDER, url.split("/")[-1])
        try:
            r = requests.get(url, stream=True)
            total_size = int(r.headers.get('content-length', 0))
            downloaded = 0

            if show_progress:
                # Create a top-level window for progress
                from .utils import center_window
                progress_window = ctk.CTkToplevel(self.parent)
                progress_window.title("Downloading Update")
                progress_window.geometry("400x100")
                try:
                    center_window(progress_window, 400,100)
                    progress_window.transient(self.parent)
                    progress_window.lift()
                except:
                    pass
                progress_label = ctk.CTkLabel(
                    progress_window, text="Downloading... This might take a few minutes.")
                progress_label.pack(pady=10)
                progress_bar = ctk.CTkProgressBar(progress_window, width=350)
                progress_bar.set(0)
                progress_bar.pack(pady=10)

            with open(filename, 'wb') as f:
                logging.info("Downloading update")
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        if show_progress:
                            # Update progress bar
                            progress_bar.set(downloaded / total_size)
                            progress_window.update()  # refresh GUI
            if show_progress:
                progress_window.destroy()  # close progress window

            # Run installer
            subprocess.Popen([filename, "/S"], shell=True)
            # self.parent.destroy()  # Close app to allow installer
            if show_progress:
                tkmsg.showinfo(("Successfully installed "
                            f"{APP_SHORT_NAME} Updates"),
                            ("You can always restart the app to install"
                            " updates"))
            logging.info(f"Finished installation: '{filename}'")
        except Exception as e:
            logging.error(f"Update failed: '{e}'")
            if show_progress:
                tkmsg.showerror(
                    f"{APP_SHORT_NAME} Update", f"Update failed")
                
            # Delete to avoid bloatware.
            if os.path.exists(filename):
                os.remove(filename)
