"""This is a script that allows the user to send
feedback or feature requests to the developer

The feedback window will be launched from the settings class



This is a subapp that will be installed together with every BM
app so that the process of feedback collection is easier


"""

from datetime import datetime
import json
import os
import re
import threading
import pathlib
import time
from tkinter.simpledialog import askstring
import customtkinter as ctk
import requests

from .constants import (EMAIL_ID_FILE, logging,
                        FB_PATH, LOGS_FILE,
                        APP_NAME,
                        BMTB_FEEDBACK_SERVER,
                        APP_ICON, read_json_file, write_json_file)
from .utils import has_internet
import tkinter.messagebox as tkmsg


class FeedbackAPI:
    def __init__(self, parent=None) -> None:
        """Collect feedback from offline and when the user
        gets online, then just send it to the developer through
        email.

        But inform the user that you will be checking when they
        get online so that the feedback can be sent.
        """
        self.parent = parent

        # Automatically check for internet in the background
        # and send feedback if there is any saved
        # otherwise, just end thread
        threading.Thread(name="Background internet check",
                         target=self.check_periodically,
                         daemon=True).start()

    def get_saved(self):
        """Return list of locally saved feedbacks."""
        if os.path.exists(FB_PATH):
            with open(FB_PATH, "r") as r:
                try:
                    return json.load(r)
                except json.JSONDecodeError:
                    return []
        return []

    def start(self):
        self.window = ctk.CTkToplevel()
        self.window.wm_transient(self.parent)
        self.window.wm_title(f"{APP_NAME} - Give feedback")
        self.window.wm_iconbitmap(APP_ICON)
        self.window.wm_protocol("WM_DELETE_WINDOW", self.on_close)

        self.help = ctk.CTkLabel(
            self.window, text="Report Issues, suggest feedback, or provide general feedback here")
        self.help.pack()

        self.credentials_frame = ctk.CTkFrame(self.window)
        self.credentials_frame.pack(fill="x", expand=True)

        self.editor_frame = ctk.CTkFrame(self.window)
        self.editor_frame.pack(side="top",
                               pady=10, expand=True, fill="both")

        self.name_entry = ctk.CTkEntry(
            self.credentials_frame, placeholder_text="Your Full Name (Optional)")
        self.name_entry.pack(expand=1, fill="x")

        self.email_entry = ctk.CTkEntry(
            self.credentials_frame,
            placeholder_text="We need your email to notify you if we have a fix.")
        self.email_entry.pack(expand=1, fill="x")

        self.textbox = ctk.CTkTextbox(
            self.editor_frame, undo=True, wrap=ctk.WORD)
        self.textbox.pack(fill="both", expand=True, pady=5)

        self.actions_frame = ctk.CTkFrame(self.window)
        self.actions_frame.pack(fill="x", expand=True)

        self.send_btn = ctk.CTkButton(
            self.actions_frame, width=30, text="Send Feedback",
            command=self.save_or_send)
        self.send_btn.pack(side="right", padx=5)

        self.cancel_btn = ctk.CTkButton(self.actions_frame,
                                        width=30,
                                        text="Cancel",
                                        fg_color="#555555",
                                        command=self.on_close)
        self.cancel_btn.pack(side="right", padx=5)

        self.helper = ctk.CTkLabel(
            self.actions_frame,
            text_color="orange")
        self.helper.pack(pady=10)
        self.helper.configure(text="")
        # self.window.wait_window()

        # Fill the email automatically
        self.auto_fill()

    def auto_fill(self):
        """Make it easy for user to continuously focus on 
        the feedback and not on the email filling"""
        self.email_name = self.email_entry.get().strip()
        if os.path.exists(EMAIL_ID_FILE):
            self.email_name = read_json_file(EMAIL_ID_FILE)["user_email"]
            logging.error(f"Using stored email: {self.email_name}")
            self.email_entry.insert('0',self.email_name)

    def validate_email(self, email):
            return bool(re.match(
                r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                email))

    def _validate(self):
        """Validate user input and return feedback data."""
        self.user_name = self.name_entry.get().strip()
        self.email_name = self.email_entry.get().strip()
        self.body = self.textbox.get("1.0", "end-1c").strip()

        self.data = {
            "APP_NAME": APP_NAME,
            "user_name": self.user_name,
            "follow_up": self.email_name,
            "user_feedback": self.body,
            "timestamp": datetime.now().strftime("%d-%m-%Y, %H:%M:%S"),
            "user_app_log": self.get_app_log()
        }
        if self.validate_email(self.email_name):
                    write_json_file(
                    EMAIL_ID_FILE, {"user_email": self.email_name})

        if not self.body:
            tkmsg.showerror("Fields required",
                            "Your feedback is required")
            logging.info("Validation failed: empty name or feedback")
            return self.data, False

        return self.data, True

    def get_app_log(self):
        """Return the last 100 lines of the app log file."""
        log_path = pathlib.Path(LOGS_FILE)
        if log_path.exists():
            try:
                with open(log_path, "r") as lf:
                    lines = lf.readlines()
                    return "".join(lines[-10:])  # Return last 5 lines
            except Exception as e:
                logging.error(f"Error reading log file: {e}")
                return "Could not read log file."
        return "Log file does not exist."

    def connected_to_server(self, url=BMTB_FEEDBACK_SERVER):
        from .utils import connected_to_server
        connected_to_server(BMTB_FEEDBACK_SERVER)

    def send_feedback(self, data={}, url=BMTB_FEEDBACK_SERVER):
        """This function is called from the GUI and
        as long as there is internet, it usually works well"""

        if not data:
            self.data = self._validate()[0]
        else:
            self.data = data

        try:
            r = requests.post(
                url, json=self.data, timeout=10)

            if (200 <= r.status_code < 300):
                logging.info("Feedback sent to server!")
                return True
            elif r.status_code == 503:
                logging.error("Server is down temporarily")
                return None
            else:
                logging.error(
                    "Feedback not sent or server "
                    "returned error check "
                    "logs of server")
                return False
        except Exception as e:
            logging.error(f"Error sending feedback: {e}")
            return False

    def save_or_send(self):
        threading.Thread(
            target=self._save_or_send,
            name="Feedback save or send",
            daemon=True).start()

    def _save_or_send(self):
        """Save this feedback locally for sending later
        or send it right now through email.
        """
        if self._validate()[1]:  # type: ignore
            self.helper.configure(
                text="Processing... Please don't close this window")
            if has_internet():
                
                s = self.send_feedback()
                if s:
                    self.helper.configure(
                        text="Sent feedback.", text_color="#10f910")
                    tkmsg.showinfo("Feedback sent",
                                   "Thank you for your feedback!")
                    self.on_close()
                elif s is None:
                    self.helper.configure(
                        text="There's a problem on our end. "
                        "Will retry later.",
                        text_color="#ff2525")
                    logging.error("Server error, will save feedback locally.")

                    self.save_locally()

                    tkmsg.showwarning(
                        "Server error occured",
                        "There's a problem on our end. "
                        "We'll save your feedback locally "
                        "and try to send it later."
                    )
                    self.on_close()

            else:
                # locally store feedback because offline
                logging.error("No connection, will save feedback locally.")
                self.helper.configure(
                    text="You are currently offline. Saving locally...")
                self.save_locally()
                tkmsg.showinfo(
                    "Feedback will be saved for later",
                    "You are offline now. We've saved "
                    "your feedback and will send it when "
                    "you are online.")
                self.on_close()

            self.on_close()

    def on_close(self):
        """what to do before closing"""
        self.window.after(500, self.window.destroy)

    def save_locally(self, data={}):
        """Append the latest feedback to 
        the end of the list then save it in a json

        Best way is to read the contents, then append and rewrite
        """
        if not data:
            self.data = self._validate()[0]
        else:
            self.data = data

        FB_PATH_ = pathlib.Path(FB_PATH)

        # Read existing feedbacks
        try:
            with open(FB_PATH_, "r") as r:
                saved_feedbacks = json.load(r)
                if not isinstance(saved_feedbacks, list):
                    saved_feedbacks = []
        except json.JSONDecodeError:
            saved_feedbacks = []
        except FileNotFoundError:
            logging.error(
                f"No {FB_PATH_.name}. "
                f"Will create a {FB_PATH_.name} "
                "file when saving")
            saved_feedbacks = []
        except Exception as e:
            logging.error(
                f"An unknown error while trying to read feedback json\n{e}")

        # Append new feedback and save
        saved_feedbacks.append(self.data)
        with open(FB_PATH_, "w") as w:
            json.dump(saved_feedbacks, w)

        logging.info(f"Saved feedback into '{FB_PATH_.name}'")
        # tkmsg.showinfo("Saved for later", "We have saved your feedback.")

    def _web(self, LINK):
        import webbrowser as wb
        wb.open_new_tab(LINK)

    def clear_saved(self):
        """Clear the feedbacks.json file"""
        with open(FB_PATH, "w") as w:
            json.dump([], w)

    def check_periodically(self):
        # Wake up the server if it is sleeping
        try:
            requests.get(BMTB_FEEDBACK_SERVER)
        except Exception as e:
            logging.error(f"Server problems again. {e}", stack_info=True)
        logging.info("Starting internet check background process")
        while True:
            saved_feedbacks = self.get_saved()
            # XXX
            if saved_feedbacks and (has_internet()):
                logging.info(
                    f"Sending {len(saved_feedbacks)} saved feedback(s)..."
                )
                for fb in saved_feedbacks:
                    try:
                        s = self.send_feedback(fb)
                        if s:
                            logging.info("Sent feedback successfully")
                            self.clear_saved()
                        elif s is None:
                            logging.error(
                                "Failed to connect to server."
                            )
                        else:
                            logging.error(
                                "Failed to send feedback; will retry later")
                    except Exception as e:
                        logging.error(
                            f"Failed to send feedback; will retry later\n{e}")
                        break  # stop trying to send more if one fails

            elif not saved_feedbacks:
                break


            time.sleep(60)  # check every 1 minute


if __name__ == "__main__":
    # FeedbackAPI().start()
    pass
