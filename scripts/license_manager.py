import json
import re
import threading
import webbrowser
from PyQt5.QtWidgets import QDialog, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
from PyQt5.QtGui import QIcon


import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64

import requests

from scripts.constants import (
    APP_PHOTO, EMAIL_ID_FILE, LICENSE_FILE, LICENSE_MESSAGE, LICENSE_MESSAGE_FILE,
    TNR_BMTB_SERVER,  logging,
    APP_NAME, read_json_file,
    get_device_id,
    ID_FILE, PUBLIC_KEY,
    write_json_file)
from scripts.utils import connected_to_server
from scripts import Settings

USER_APP_ID = get_device_id(ID_FILE)


class LicenseManager:
    def __init__(self, master=None) -> None:
        """Managing all license related things. 
        This classed is called in the Notes app.
        """
        self.master = master

        self.license_file = LICENSE_FILE
        self.public_key = PUBLIC_KEY

        self.license_message = LICENSE_MESSAGE
        self.settings_manager = Settings()

        self.is_premium = False
        self.license_data = None
        self.license_key = None

        # Even if there's an error,
        # This would wake it up.

    def load_and_validate_license(self):
        if not self.license_file.exists():
            logging.error("License file corrupted or missing!")
            self.is_premium = False
            return False

        data = read_json_file(self.license_file)
        self.license_data, self.license_key = self.parse_license(data)

        if self.verify_signature(self.license_data, self.license_key):
            logging.info("License file found and valid!")
            self.is_premium = True
            return True
        else:
            logging.error("License file corrupted or missing!")
            os.remove(self.license_file)  # 🚨 remove tampered/invalid license
            logging.error("Trying reg")
            self.license_key = self.settings_manager.user_license_key or ""
            self.license_data = self.settings_manager.user_license_data or ""
            if self.verify_signature(self.license_data, self.license_key):
                self.is_premium = True
                return True
            return False

    def activate_license(self, license_data, license_key):
        """Called ONLY when user enters key """
        if self.verify_signature(license_data, license_key):
            self.license_data = license_data
            self.license_key = license_key
            self.is_premium = True
            write_json_file(self.license_file, self.format_license(
                license_data, license_key))

            # store in reg too
            self.settings_manager.user_license_key = license_key
            self.settings_manager.user_license_data = license_data

            logging.info("Saved license to file and reg.")
            QMessageBox.information(None,
                                    "Success", "License activated successfully! "
                                    "You are now a premium user.")
            logging.info("Premium mode on.")
            return True
        else:
            self.is_premium = False
            QMessageBox.critical(None, "License Error",
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

    def _show_license_window(self):
        """Display modal license entry window"""
        self.license_window = QDialog(self.master)
        self.license_window.setWindowIcon(QIcon(str(APP_PHOTO)))
        self.license_window.setFixedSize(600, 500)
        self.license_window.setWindowTitle(f"Activate {APP_NAME}")

        self.mainlayout = QVBoxLayout()

        instructions = QLabel(self.license_message, self.license_window,)

        # TODO: Add pricing buttons to choose from if possible

        payment_link = (lambda: self.initiate_payment())

        purchase_link = QPushButton("Purchase License")
        purchase_link.setStyleSheet("background:none;color:#77e;")
        purchase_link.clicked.connect(payment_link)

        license_key_label = QLabel(
            "License Key:", self.license_window)
        license_key_entry = QLineEdit(self.license_window)

        license_data_label = QLabel(
            "License Data:", self.license_window)
        license_data_entry = QLineEdit(self.license_window)

        submit_btn = QPushButton("Activate", self.license_window)
        submit_btn.clicked.connect(
            lambda: self.__submit_license(license_key_entry.text(), license_data_entry.text()))

        
        self.status = QLabel(self.license_window)

        self.mainlayout.addWidget(instructions)
        self.mainlayout.addWidget(purchase_link)
        self.mainlayout.addWidget(license_key_label)
        self.mainlayout.addWidget(license_key_entry)
        self.mainlayout.addWidget(license_data_label)
        self.mainlayout.addWidget(license_data_entry)
        self.mainlayout.addWidget(submit_btn)
        self.mainlayout.addWidget(self.status)

        self.license_window.setLayout(self.mainlayout)
        self.license_window.exec()

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
                email = QInputDialog.getText(
                    None,
                    "Email Required for payment",
                    "Enter your email (required for payment).\n\n"
                    "We'll save it on your computer\n"
                    "so you never have to type it again:"
                )

                email = email[0]

                if not email:
                    continue  # prompt again if empty

                if validate_email(email):
                    self.user_email = email
                    write_json_file(
                        EMAIL_ID_FILE, {"user_email": self.user_email})
                    break
                else:
                    QMessageBox.critical(None, "Invalid Email",
                                         "Please enter a valid email address.")
        else:
            self.user_email = read_json_file(EMAIL_ID_FILE)["user_email"]
            logging.error(f"Using stored email: {self.user_email}")

    def server_ping_and_price_get(self):
        """the way to do that is to occasionally delete the file"""
        # Wake up our server
        

        try:
            connected_to_server(TNR_BMTB_SERVER+"/ping")
        except Exception as e:
            logging.error(
                "While waking up server, something"
                f" Happened: {e}")

        # check for the number of opens and remove after every 2 app opens
        if self.settings_manager.number_of_opens % 2 == 0:
            if (LICENSE_MESSAGE_FILE.exists()):
                os.remove(LICENSE_MESSAGE_FILE)
        try:
            if (not LICENSE_MESSAGE_FILE.exists()):
                if not connected_to_server(TNR_BMTB_SERVER):
                    resp = requests.get(
                        f"{TNR_BMTB_SERVER}/licenseinfo").json()
                    # print(resp)
                    write_json_file(LICENSE_MESSAGE_FILE, dict(resp))

            lm = read_json_file(LICENSE_MESSAGE_FILE)[
                'license_message']

            if lm.strip():
                self.license_message = lm
                return
        except Exception as e:
            logging.error(f"update_license_message: {e}")
            self.license_message = LICENSE_MESSAGE
            pass

    def __initiate_payment(self):
        """Perform server payment initiation"""
        def open_link(link):
            webbrowser.open_new_tab(f"{payment_page_link}")
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
                    # TODO: Here, we have to control
                    # the price from us not from the
                    # app

                    json={
                        "app_name": APP_NAME,
                        "email": self.user_email,
                        "device_id": USER_APP_ID
                    })

                reference = str(resp.json()["data"]["reference"])
            except Exception as e:
                logging.error(
                    f"Server either sleeping, or internet is slow: {e}")

            logging.info(f"Payment initiated, reference: {reference}")
            payment_page_link = resp.json()['data']['authorization_url']
            payment_page_link_btn = QPushButton(
                f"Open Link: {payment_page_link}")
            payment_page_link_btn.clicked.connect(
                lambda: open_link(payment_page_link))
            self.mainlayout.addWidget(payment_page_link_btn)
            self._update_status(
                "Click on the link to open your browser", "#3dff33")

        except Exception as e:
            logging.error(f"Error during payment processing: {e}")
            QMessageBox.critical(None, "Error occured",
                                 "Failed to initiate payment."
                                 " Might be a connection problem."
                                 " Please try again later.")
            self._update_status(
                "Payment process failed. Please try again.", col="#ff3333")

    def _update_status(self, msg, col="#ff976a"):
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{col};")

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

            self.__initiate_payment()

    def __submit_license(self, license_key, license_data):
        """Handle license submission"""
        self._update_status("Verifying license, please wait...")

        try:
            license_key = str(license_key)
            license_data = str(license_data)

            if not license_data or not license_key:
                self._update_status("Required fields missing.", col="#ff3333")
                QMessageBox.critical(
                    None,
                    "Missing Data",
                    "Both License Data and License Key are required.")
                return

            # Loudly declare if license is valid or not
            self.activate_license(license_data, license_key)

            self.license_window.destroy()
            return
        except Exception as e:
            print(e)
