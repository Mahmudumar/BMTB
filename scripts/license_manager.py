# license_manager.py

# For license management
import json
import re
import threading
import webbrowser
import customtkinter as ctk
import tkinter.messagebox as tkmsg
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64

import requests

from scripts.constants import (EMAIL_ID_FILE, LICENSE_FILE,
                               TNR_BMTB_SERVER,  logging,
                               APP_ICON, APP_NAME, read_json_file,
                               get_device_id,
                               ID_FILE, PUBLIC_KEY,
                               write_json_file,
                               PREMIUM_PRICE)

from scripts.utils import askstring, center_window, connected_to_server

USER_APP_ID = get_device_id(ID_FILE)


class LicenseManager:
    def __init__(self, master) -> None:
        """Managing all license related things. 
        This classed is called in the Notes app.
        """
        self.master = master

        self.cipher = self.master.cipher
        self.license_file = LICENSE_FILE
        self.public_key = PUBLIC_KEY

        self.is_premium = False
        self.license_data = None
        self.license_key = None

        self.load_and_validate_license()

        # Wake up our server
        try:
            connected_to_server(TNR_BMTB_SERVER+"/ping")
        except Exception as e:
            logging.error(
                "While waking up server, something"
                f" Happened: {e}")
        # Even if there's an error,
        # This would wake it up.

    def load_and_validate_license(self):
        if not os.path.exists(self.license_file):
            logging.error("License file corrupted or missing!")
            self.is_premium = False
            return False

        data = read_json_file(self.license_file)
        self.license_data, self.license_key = self.parse_license(data)

        if self.verify_signature(self.license_data, self.license_key):
            logging.error("License file found and valid!")
            self.is_premium = True
            return True
        else:
            logging.error("License file corrupted or missing!")
            self.is_premium = False
            os.remove(self.license_file)  # 🚨 remove tampered/invalid license
            return False

    def activate_license(self, license_data, license_key):
        """Called when user enters key only"""
        if self.verify_signature(license_data, license_key):
            self.license_data = license_data
            self.license_key = license_key
            self.is_premium = True
            write_json_file(self.license_file, self.format_license(
                license_data, license_key))
            logging.info("Saved license to file.")
            tkmsg.showinfo(
                "Success", "License activated successfully! "
                "You are now a premium user.")
            logging.info("Premium mode on.")
            return True
        else:
            self.is_premium = False
            tkmsg.showerror("License Error",
                            "Invalid license. Please try again.")
            return False

    def is_premium_user(self):
        return self.is_premium

    def verify_signature(self, license_data, license_key):
        """This is a silent function 
        as opposed to  `activate_license(...)`"""
        try:
            public_key = serialization.load_pem_public_key(
                self.public_key.encode())

            # Encode and hash the license data
            license_bytes = license_data.encode()
            signature = base64.b64decode(license_key)

            public_key.verify(  # type: ignore
                signature,
                license_bytes,
                padding.PKCS1v15(),  # type: ignore
                hashes.SHA256()  # type: ignore
            )

            # ✅ Now confirm it’s for this specific machine
            data = json.loads(license_data)
            if data.get("device_id") != USER_APP_ID:
                logging.error("License used on unauthorized device.")
                return False

            logging.info("License verified and bound to this device.")
            self.is_premium = True
            return True
        except Exception as e:
            logging.error(f"License verification failed: {e}")
            return False

    # Formatting
    def format_license(self, license_data, license_key):
        return {
            "license_data": license_data,
            "license_key": license_key
        }

    def parse_license(self, data):
        """TODO: decrypt data"""
        license_dict = data if isinstance(data, dict) else json.loads(data)
        return license_dict["license_data"], license_dict["license_key"]

    # --- Link and license acquisition ---

    def _show_license_window(self, master):
        """Display modal license entry window"""
        self.license_window = ctk.CTkToplevel(master)
        self.license_window.title(f"Activate {APP_NAME}")
        # self.license_window.geometry("500x480")
        try:
            self.license_window.grab_set()
        except Exception:
            pass
        self.license_window.resizable(False, True)
        self.license_window.iconbitmap(APP_ICON)
        center_window(self.license_window, 500, 470, offsety=-150)

        instructions = ctk.CTkLabel(
            self.license_window,
            text=(
                f"Welcome to {APP_NAME}!\n\n"
                "You are currently using the free version.\n\n"
                "Unlock the full version to enjoy:\n"
                "• Premium features: Unlimited Notes\n"
                "• A smoother, distraction-free experience\n\n"
                "To activate, please paste your License Key below\n\n\n"
                "If you don’t have a license yet, click below to purchase one.\n\n"
                f"The license costs: {PREMIUM_PRICE:,d} Naira only"
            ),
            justify="left",
            wraplength=480
        )
        # TODO: Add pricing buttons to choose from if possible


        instructions.pack(pady=(10, 0), padx=10, anchor="w")

        link_label = ctk.CTkLabel(
            self.license_window, text=f"Purchase License",
            text_color="#6b9eda",
            cursor="hand2", justify="left"
        )
        link_label.pack(pady=(0, 10), padx=10, anchor="w")
        link_label.bind("<Button-1>", lambda e: threading.Thread(
            target=self.initiate_payment, daemon=True).start())

        # license_data_label = ctk.CTkLabel(
        #     self.license_window, text="License Data:")
        # license_data_label.pack(anchor="w", padx=20)
        # license_data_entry = ctk.CTkTextbox(self.license_window, height=4)
        # license_data_entry.pack(fill="x", padx=20, pady=(0, 10))

        license_key_label = ctk.CTkLabel(
            self.license_window, text="License Key:")
        license_key_label.pack(anchor="w", padx=20)
        license_key_entry = ctk.CTkTextbox(self.license_window, height=2)
        license_key_entry.pack(fill="x", padx=20, pady=(0, 10))

        submit_btn = ctk.CTkButton(
            self.license_window,
            text="Activate",
            command=lambda: self.__submit_license(license_key_entry)
        )
        submit_btn.pack(pady=10)
        # something to tell the user that it is
        # loading just as we did in feedback
        # system.
        self.status = ctk.CTkLabel(
            self.license_window, text="",
            text_color="#f5ca3f")
        self.status.pack(anchor="w", padx=20)

        # self.license_window.wait_window()

    def __ask_email(self):
        """Prompt user for email if not stored

        You must validate it because Paystack needs a 
        valid email address
        """
        def validate_email(email):
            return bool(re.match(
                r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
                email))

        if not os.path.exists(EMAIL_ID_FILE):
            while True:
                email = askstring("Email Required for payment",
                                  "Enter your email (required for payment).\n\n"
                                  " We'll save it on your computer\n"
                                  "so you never have to type it again:",height=210)
                if not email:
                    continue  # prompt again if empty
                elif email == "exit":
                    logging.warning("Payment process cancelled.")
                    return

                if validate_email(email):
                    self.user_email = email
                    write_json_file(
                        EMAIL_ID_FILE, {"user_email": self.user_email})
                    break
                else:
                    tkmsg.showerror("Invalid Email",
                                    "Please enter a valid email address.")
        else:
            self.user_email = read_json_file(EMAIL_ID_FILE)["user_email"]
            logging.error(f"Using stored email: {self.user_email}")

    def __initiate_payment(self):
        """Perform server payment initiation"""
        try:
            # Since our users just might not have
            # (stable) internet,
            # we must deal with this TODO
            try:
                # send the device id as well
                # this would be saved and tied
                # to the key that will be
                # given to you
                resp = requests.post(
                    f"{TNR_BMTB_SERVER}/payment",
                    # Here, we have to control
                    # the price from us not from the
                    # app
                    json={"amount": PREMIUM_PRICE,
                          "email": self.user_email,
                          "device_id": USER_APP_ID})

                reference = str(resp.json()["data"]["reference"])
            except Exception as e:
                logging.error(
                    f"Server either sleeping, or internet is slow: {e}")

            logging.info(f"Payment initiated, reference: {reference}")

            webbrowser.open_new_tab(resp.json()['data']['authorization_url'])
            self._update_status(
                "Payment link opened in browser.",
                col="#3fbf3f")

        except Exception as e:
            logging.error(f"Error during payment processing: {e}")
            tkmsg.showerror("Error occured",
                            "Failed to initiate payment."
                            " Might be a connection problem."
                            " Please try again later.")
            self._update_status(
                "Payment process failed. Please try again.", col="#ff3333")

    def _update_status(self, msg, col="#f5ca3f"):
        self.status.configure(text=msg, text_color=col)
        self.license_window.update_idletasks()

    def initiate_payment(self):
        """Start freemium registration/payment flow"""
        # Ask email first, and if it is cancelled or invalid,
        # just cancel the payment process, don't
        # run the thread
        self.__ask_email()
        if hasattr(self, 'user_email'):
            self._update_status(
                "Opening payment link. "
                "It might take some seconds...")

            threading.Thread(target=self.__initiate_payment,
                             daemon=True).start()

    def __submit_license(self, key_entry):
        """Handle license submission"""
        self._update_status("Verifying license, please wait...")

        # license_data = data_entry.get("1.0", "end-1c").strip()

        data = str(key_entry.get("1.0", "end-1c").strip()).split("||")

        license_data = data[1]
        license_key = data[0]

        if not license_data or not license_key:
            self._update_status("Required fields missing.", col="#ff3333")
            tkmsg.showerror(
                "Missing Data",
                "Both License Data and License Key are required.")
            return

        # Loudly declare if license is valid or not
        self.activate_license(license_data, license_key)

        self.license_window.destroy()
        return
