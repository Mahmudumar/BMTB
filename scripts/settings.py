import customtkinter as ctk
import tkinter as tk
import tkinter.messagebox as tkmsg
from tkinter import simpledialog
import os
import json

from scripts.constants import (
    APP_NAME, APP_VERSION, PASS_FILE, APP_ICON, SETTINGS_FILE,
    TNR_BMTB_SERVER
)
from scripts.utils import askstring, clear_all_notes
from scripts.feedback_collection import FeedbackAPI
from scripts.license_manager import LicenseManager
from scripts.auto_updater import AutoUpdater


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"request_password": False}
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


class SettingsWindow(ctk.CTkToplevel):
    """Settings GUI window styled like NCH preferences with shared styles."""

    def __init__(self, parent, cipher):
        super().__init__(parent)
        self.title(f"Settings")
        self.geometry("450x450")
        self.wm_iconbitmap(APP_ICON)
        self.resizable(False, False)
        self.transient(parent)

        self.cipher = cipher
        self.parent = parent
        self.settings = load_settings()
        self.feedback_manager = FeedbackAPI(self)
        self.license_manager = LicenseManager(self)
        self.updater = AutoUpdater(self, False, True)

        # --- Theme palette ---
        self.colors = {
            "bg": "#2b2b2b",
            "fg": "#f0f0f0",
            "accent": "#3c3f41",
            "danger": "#a33",
            "danger_hover": "#c44"
        }

        # --- Shared styles ---
        self.styles = {
            "label": {"bg": self.colors["bg"], "fg": self.colors["fg"], "font": ("Segoe UI", 11)},
            "section": {"bg": self.colors["bg"],
                        "fg": self.colors["fg"],
                        "relief": "groove",
                        "font": ("Segoe UI", 11, "bold")},
            "button": {"bg": self.colors["accent"],
                       "fg": self.colors["fg"],
                       "activebackground": "#555",
                       "activeforeground": "#fff",
                       "relief": "flat", "bd": 1,
                       "font": ("Segoe UI", 11), "padx": 8, "pady": 4},
            "check": {"bg": self.colors["bg"],
                      "fg": self.colors["fg"],
                      "selectcolor": self.colors["bg"],
                      "activebackground": self.colors["bg"],
                      "activeforeground": self.colors["fg"],
                      "font": ("Segoe UI", 11)}
        }

        self.configure(bg=self.colors["bg"])

        # --- Section builder ---
        def make_section(title):
            frame = tk.LabelFrame(self, text=title, **self.styles["section"])
            frame.pack(fill="x", padx=15, pady=10, ipady=5)
            return frame

        # Password section
        pass_frame = make_section("Password")
        tk.Button(pass_frame, text="Change Password", command=self.change_password,
                  **self.styles["button"]).pack(anchor="w", padx=10, pady=5)

        #

        # Security section
        sec_frame = make_section("Security")
        self.startup_lock_var = tk.BooleanVar(
            value=self.settings.get("request_password", False))
        tk.Checkbutton(
            sec_frame, text="Request password at startup",
            variable=self.startup_lock_var, command=self.toggle_startup_lock,
            **self.styles["check"]
        ).pack(anchor="w", padx=10, pady=5)

        # Notes section
        notes_frame = make_section("Notes Management")
        tk.Button(notes_frame, text="Clear All Notes", command=self.confirm_clear_all,
                  bg=self.colors["danger"], fg="white",
                  activebackground=self.colors["danger_hover"], activeforeground="white",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=10, pady=5)

        # Feedback section
        fb_frame = make_section("Feedback and Help")
        tk.Button(fb_frame, text="Give Feedback", command=self.feedback_collect,
                  **self.styles["button"]).pack(anchor="w", padx=10, pady=5)

        purchase_bt = tk.Button(fb_frame,
                                text=f"Purchase {APP_NAME}",
                                command=self.start_license,
                                **self.styles["button"])
        purchase_bt.pack(anchor="w", padx=10, pady=5)
        if self.license_manager.is_premium_user():
            purchase_bt.config(state="disabled")
            
        update_bt = tk.Button(fb_frame,
                                text=f"Check for Updates",
                                command=self.check_updates,
                                **self.styles["button"])
        update_bt.pack(anchor="w", padx=10, pady=5)

        # Bottom buttons
        btn_frame = tk.Frame(self, bg=self.colors["bg"])
        btn_frame.pack(side="bottom", fill="x", pady=10)

        tk.Button(btn_frame, text="OK", width=10, command=self.destroy,
                  **self.styles["button"]).pack(side="right", padx=10)
        tk.Button(btn_frame, text="Cancel", width=10, command=self.destroy,
                  **self.styles["button"]).pack(side="right")

        self.after(2000, self.wake_server_up)

    # ----- Logic unchanged -----
    def wake_server_up(self):
        from .utils import connected_to_server
        connected_to_server(TNR_BMTB_SERVER)

    def toggle_startup_lock(self):
        if self.startup_lock_var.get():
            new_pass = askstring(
                "Set Password", "Enter a new password:", show="*")
            if not new_pass:
                tkmsg.showinfo("Info", "Password setup cancelled.")
                self.startup_lock_var.set(False)
                return
            recovery = askstring(
                "Recovery Code", "Enter a recovery code (save it safely):", show="*")
            if not recovery:
                tkmsg.showinfo("Info", "Recovery setup cancelled.")
                self.startup_lock_var.set(False)
                return
            with open(PASS_FILE, "w") as f:
                f.write(self.cipher.pass_hash(new_pass) + "\n")
                f.write(self.cipher.pass_hash(recovery))
            self.settings["request_password"] = True
            save_settings(self.settings)
            tkmsg.showinfo("Info", "Password protection enabled.")
        else:
            self.settings["request_password"] = False
            save_settings(self.settings)
            tkmsg.showinfo("Info", "Password request at startup disabled.")

    def feedback_collect(self, event=None):
        self.feedback_manager.start()

    def start_license(self, event=None):
        self.license_manager._show_license_window(self.parent)

    def check_updates(self, event=None):
        self.updater.check_update_and_prompt()

    def confirm_clear_all(self):
        answer = askstring(
            "Confirm Clear All",
            "Type 'YES' to delete ALL notes permanently:"
        )
        if answer and answer.strip().upper() == "YES":
            clear_all_notes()
            self.parent.notes.clear()
            self.parent.refresh_list()
            self.parent.title_entry.delete(0, "end")
            self.parent.textbox.delete("1.0", "end")
            self.parent.current_index = None
            tkmsg.showinfo("Success", "All notes deleted successfully!")

    def verify_current_password(self):
        if not os.path.exists(PASS_FILE):
            tkmsg.showerror("Error", "No password set yet.")
            return False
        entered = askstring(
            "Verify Password", "Enter current password (or recovery code):", show="*")
        if entered is None:
            return False
        with open(PASS_FILE, "r") as f:
            stored_hash = f.readline().strip()
        if self.cipher.pass_hash(entered) == stored_hash:
            return True
        else:
            tkmsg.showerror("Error", "Incorrect password.")
            return False

    def change_password(self):
        if not self.verify_current_password():
            return
        new_pass = askstring("New Password", "Enter new password:", show="*")
        if not new_pass:
            tkmsg.showinfo("Info", "Password change cancelled.")
            return
        with open(PASS_FILE, "w") as f:
            f.write(self.cipher.pass_hash(new_pass))
        tkmsg.showinfo("Info", "Password changed successfully.")
