import hashlib
import os
import string
from scripts.constants import PASS_FILE, APP_PHOTO
from scripts.database_manager import DatabaseManager
from scripts.password_hint import load_password_hint, save_password_hint

from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import (QLabel, QPushButton,
                             QVBoxLayout,
                             QMessageBox,
                             QDialog,
                             QLineEdit,
                             QFormLayout)
from cryptography.fernet import Fernet, InvalidToken
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES, PKCS1_OAEP

import base64

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class Cryptography:
    def __init__(self) -> None:
        self.dek = None
        self.kek = None

    def lock(self):
        self.dek = None
        self.kek = None

    def unlock(self, password, salt, encrypted_dek):
        self.kek = self.derive_KEK(password, salt)
        self.dek = self.decrypt_DEK(
            self.kek,
            encrypted_dek
        )

    def derive_KEK(self, master_password: str, salt: bytes) -> bytes:
        """
        Derive a Fernet-compatible encryption key from a master password.

        Args:
            master_password: The user's master password.
            salt: The vault's random salt.

        Returns:
            A 32-byte Base64-encoded key suitable for Fernet.
        """

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600_000,
        )

        derived_key = kdf.derive(master_password.encode("utf-8"))

        return base64.urlsafe_b64encode(derived_key)

    def generate_new_DEK(self):
        """Only when creating a fresh new DB alone should this """
        return Fernet.generate_key()

    def generate_salt(self):
        return os.urandom(16)

    def encrypt_DEK(self, key, dek):
        return Fernet(key).encrypt(dek)

    def decrypt_DEK(self, key, dek):
        return Fernet(key).decrypt(dek)

    def encrypt_note(self, key, text: str):
        return Fernet(key).encrypt(text.encode())

    def decrypt_note(self, key, text: bytes):
        return Fernet(key).decrypt(text).decode()

    def pass_hash(self, text: str) -> str:
        """
        Generate a secure SHA-256 hash of the password.
        Returns the hex digest string (64 characters).
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SimpleCipher:
    """
    TODO: find a way to encrypt even the key itself
    so that a person cannot use a program to hack and decode
    the notes
    """

    def __init__(self, key=3) -> None:
        self.alphabet = string.ascii_lowercase
        self.key = key

    def encrypt(self, text: str):
        encoded = ""
        for ch in text:
            c = ord(ch) + self.key % 26
            encoded += chr(c)
        return encoded

    def decrypt(self, text):
        decoded = ""
        for ch in text:
            c = ord(ch) - self.key % 26
            decoded += chr(c)
        return decoded

    def pass_hash(self, text: str) -> str:
        """
        Generate a secure SHA-256 hash of the password.
        Returns the hex digest string (64 characters).
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SimpleSubstitution:
    def __init__(self):
        # Only a–i mapped
        self.encode_map = {
            "a": "01", "b": "02", "c": "03",
            "d": "04", "e": "05", "f": "06",
            "g": "07", "h": "08", "i": "09",

            "A": "11", "B": "12", "C": "13",
            "D": "14", "E": "15", "F": "16",
            "G": "17", "H": "18", "I": "19",

        }
        self.encode_map = {
            ch: f"{num}".zfill(2) for num, ch in enumerate(string.printable)}

        self.decode_map = {v: k for k, v in self.encode_map.items()}

    def encrypt(self, text: str) -> str:
        """Replace a–i with digits 1–9."""
        encoded = ""
        for char in text:
            encoded += self.encode_map.get(char, char)
        return encoded

    def decrypt(self, text: str) -> str:
        decoded = ""
        i = 0
        while i < len(text):
            pair = text[i:i+2]
            if pair in self.decode_map:
                decoded += self.decode_map[pair]
                i += 2
            else:
                decoded += text[i]
                i += 1
        return decoded

    def pass_hash(self, text: str) -> str:
        """
        Generate a secure SHA-256 hash of the password.
        Returns the hex digest string (64 characters).
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PasswordManager(QDialog):
    def __init__(self, db: DatabaseManager, settings_manager, new=False, change=False, parent=None, new_change=False) -> None:

        super().__init__(parent)
        self.setWindowIcon(QIcon(str(APP_PHOTO)))
        self.parent_app = parent
        self.def_password = "user123"
        self.correct = False
        self.db = db
        self.turning_require_password_back_on = new_change
        self.settings_manager = settings_manager
        self.set_new = new
        self.change_pass = change

        self.password_file = PASS_FILE

        self.hashed = None

        if not self.set_new:
            self.hashed = self.get_hashed()

        self.crypto = Cryptography()

        # do the check from the beginning of the password init
        # check if there are notes in the vault and disallow creating new
        # if self.notes_present():
        #     self.set_new = False

        # NOTE: This is required as the first sanity check.
        

        self.init_ui()

    def pass_hash(self, password):
        """Return the hash of a password"""
        return self.crypto.pass_hash(password)

    def notes_present(self):
        """It is always crucial we must have notes to protect. The only time, password_manager(new=True) is allowed, is when there are no notes in the vault."""
        # XXX: inefficient check, soon to change
        return bool(len(self.db.get_all_notes()))

    def encrypt_note(self, key, note_content: str):
        # TODO
        return self.crypto.encrypt_note(key, note_content)

    def decrypt_note(self, key, encrypted_content):
        # TODO
        return self.crypto.decrypt_note(key, encrypted_content)

    def set_message(self, msg, color="#b50000"):
        """only show message when this func is called"""
        if not msg.strip():
            self.status.hide()
            return

        existing = self.status.text().strip()
        if existing:
            self.status.setText(f"{existing}\n{msg}")
        else:
            self.status.setText(f"{msg}")
        self.status.setStyleSheet(f"color:{color};")
        self.status.show()

        print(self.main_layout.children())

    def init_ui(self):
        self.setWindowTitle("Enter Password")
        self.setMaximumSize(700, 500)
        self.setMinimumSize(400, 300)
        self.main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.new_password_input = QLineEdit()
        self.old_password_input = QLineEdit()
        self.confirm_password_input = QLineEdit()
        self.password_hint_input = QLineEdit()
        self.password_hint_input.setPlaceholderText("Optional reminder, not your password")
        self.password_hint_input.setToolTip(
            "Optional. Write a clue that helps you remember without revealing the password."
        )
        self.status = QLabel()
        self.save_button = QPushButton("Ok")

        

        self.status.setWordWrap(True)
        if self.set_new:
            self.setWindowTitle("Set a New Password")
            self.new_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("New Password:", self.new_password_input)
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow(
                "Confirm Password:",
                self.confirm_password_input
            )
            form_layout.addRow(
                "Password Hint:",
                self.password_hint_input
            )

            if not self.turning_require_password_back_on:
                self.save_button.clicked.connect(self.okay_new)
            else:
                self.save_button.clicked.connect(
                    lambda: self.okay_resetting_after_require_off())

        elif self.change_pass:
            self.setWindowTitle("Change Password")
            self.old_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("Current Password:", self.old_password_input)
            self.new_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("New Password:", self.new_password_input)
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow(
                "Confirm Password:",
                self.confirm_password_input
            )
            form_layout.addRow(
                "Password Hint:",
                self.password_hint_input
            )
            self.save_button.clicked.connect(self.okay_new_change)

        else:
            
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("Password:", self.password_input)
            self.confirm_password_input = None
            self.new_password_input = None
            self.save_button.clicked.connect(self.okay)

            ps_hint = load_password_hint(self.db, self.settings_manager)
            if ps_hint:
                self.set_message(f"Password Hint: {ps_hint}", "#21ec21")

        self.cancel_button = QPushButton("Quit")
        self.cancel_button.clicked.connect(self.reject)

        # self.status.hide()
        

        self.main_layout.addLayout(form_layout)
        self.main_layout.addWidget(self.save_button)
        self.main_layout.addWidget(self.cancel_button)

        # main_layout.addStretch()
        self.main_layout.insertWidget(0,self.status)

        self.setLayout(self.main_layout)

    def save_password_hint(self):
        """Persist an explicitly entered hint without replacing it with an empty value."""
        return save_password_hint(
            self.db, self.settings_manager, self.password_hint_input.text()
        )

    def get_hashed(self):
        """Get the stored password hash from the db"""
        def search_db():
            # Attempt 3: get it from the db itself.
            db_stored_hash = str(self.db.get_config("password_hash"))
            if db_stored_hash.strip():
                return db_stored_hash
            else:
                return ""

        stored_hash = search_db()

        return stored_hash or None

    def save_changed(self, old: str, new: str):
        """This function was created because of the case of when a user disables require password, we need a password to decrypt their notes at all times (because the .db itself must be always encrypted), so as soon as they turn off that 'require pass' setting, we will use that confirmation to generate a new password, then just automatically log in when user enters the app the next time."""
        # NOTE: unlock DEK first
        try:
            stored_DEK = self.db.get_config("encDEK").encode()
            stored_salt = base64.urlsafe_b64decode(
                self.db.get_config("salt").encode())
            self.crypto.unlock(old, stored_salt, stored_DEK)
        except Exception as e:
            QMessageBox.critical(self, "Something's wrong",
                                 f"While decrypting prev password: {e}")
            print("wrong password or salt was changed")
            print(e)
            return
        try:
            # The DEK is now decrypted by our KEK gotten from our old config. Ready to be encrypted with the new kek
            decrypted_DEK = self.crypto.dek

            # THEN CREATE NEW KEK and REENCRYPT the DEK with it.
            new_salt = self.crypto.generate_salt()
            new_KEK = self.crypto.derive_KEK(new, new_salt)
            new_enc_DEK = self.crypto.encrypt_DEK(new_KEK, decrypted_DEK)

            hashed_pass = self.crypto.pass_hash(new)
            new_salt_stored = base64.urlsafe_b64encode(new_salt)

            self.db.set_config("encDEK", new_enc_DEK.decode())
            self.db.set_config("password_hash", hashed_pass)
            self.db.set_config("salt", new_salt_stored.decode())

            self.crypto.unlock(new, new_salt, new_enc_DEK)
        except Exception as e:
            QMessageBox.critical(self, "Something's wrong",
                                 f"While saving the password{e}")
            print("wrong password or salt was changed")
            print(e)
            return

    def okay_new_change(self):
        def save_changed(old: str, new: str):
            # NOTE: unlock DEK first
            try:
                stored_DEK = self.db.get_config("encDEK").encode()
                stored_salt = base64.urlsafe_b64decode(
                    self.db.get_config("salt").encode())
                self.crypto.unlock(old, stored_salt, stored_DEK)
            except Exception as e:
                print("wrong password or salt was changed")
                print(e.__cause__)
                return

            # The DEK is now decrypted by our KEK gotten from our old config. Ready to be encrypted with the new kek
            decrypted_DEK = self.crypto.dek

            # THEN CREATE NEW KEK and REENCRYPT the DEK with it.
            new_salt = self.crypto.generate_salt()
            new_KEK = self.crypto.derive_KEK(new, new_salt)
            new_enc_DEK = self.crypto.encrypt_DEK(new_KEK, decrypted_DEK)

            hashed_pass = self.crypto.pass_hash(new)
            new_salt_stored = base64.urlsafe_b64encode(new_salt)

            self.db.set_config("encDEK", new_enc_DEK.decode())
            self.db.set_config("password_hash", hashed_pass)
            self.db.set_config("salt", new_salt_stored.decode())

            self.crypto.unlock(new, new_salt, new_enc_DEK)

        
        if not self.validate_inputs():
            return
        
        old_pass = self.old_password_input.text()
        new_pass = self.new_password_input.text()
        pass_hint = self.password_hint_input.text()

        confirm_pass = self.confirm_password_input.text()
        stored_hash = self.db.get_config("password_hash")

        if self.crypto.pass_hash(old_pass) != stored_hash:
            # incorrect old pass word.
            QMessageBox.critical(
                self,
                "Incorrect Password",
                "The current password is incorrect."
            )
            return
        try:
            save_changed(old_pass, new_pass)
            if pass_hint.strip():
                save_password_hint(self.db, self.settings_manager, pass_hint)
            QMessageBox.information(
                self,
                "Success",
                "Password saved successfully."
            )
            self.accept()
            return
        except Exception as e:
            print(e)
            QMessageBox.information(
                self,
                "Error",
                "Sorry, something went terribly wrong."
            )

    def okay_new(self):
        """This is only called on the first install. Or on a new .db file"""
        def save_new(password):
            DEK = self.crypto.generate_new_DEK()
            salt = self.crypto.generate_salt()
            KEK = self.crypto.derive_KEK(password, salt)
            encDEK = self.crypto.encrypt_DEK(KEK, DEK)
            hashed_pass = self.crypto.pass_hash(password)

            self.db.set_config("encDEK", encDEK.decode())
            self.db.set_config("password_hash", hashed_pass)
            salt_stored = base64.urlsafe_b64encode(salt)
            self.db.set_config("salt", salt_stored.decode())
            self.crypto.unlock(password, salt, encDEK)

        password = self.new_password_input.text()

        if not self.validate_inputs():
            return

        QMessageBox.information(self, "Password Set", "Password Set")

        self.correct = True
        save_new(password)
        self.save_password_hint()
        try:
            assert self.old_password_input is not None
            self.old_password_input.clear()
            assert self.new_password_input is not None
            self.new_password_input.clear()
            assert self.confirm_password_input is not None
            self.confirm_password_input.clear()
            assert self.password_input is not None
            self.password_input.clear()
        except Exception:
            pass

        self.accept()

    def okay_resetting_after_require_off(self):
        """This is for when turning back the require pass option back on...it will change from the default password to the new password"""
        if self.validate_inputs():
            old, new = self.def_password, self.confirm_password_input.text()
            self.save_changed(old, new)

            # everytime, you must modify self.correct accordingly before the password setting window, disappears because it is used by app
            self.correct=True
            self.accept()
        else:
            self.correct = False

    def validate_inputs(self):
        """To be called in every OK call. we must make the user not press okay if """
        if self.set_new:
            if not (self.confirm_password_input.text() == self.new_password_input.text()):
                QMessageBox.critical(
                    self,
                    "Password Mismatch",
                    "Confirm and new Password must match exactly")
                return
        elif self.change_pass:
            new_pass = self.new_password_input.text()
            confirm_pass = self.confirm_password_input.text()
            if new_pass != confirm_pass:
                QMessageBox.warning(
                    self,
                    "Password Mismatch",
                    "The passwords do not match."
                )
                return
        
        return True


    def unlock_DEK(self, password):
        encDEK = self.db.get_config("encDEK").encode()
        salt = base64.urlsafe_b64decode(self.db.get_config("salt").encode())
        self.crypto.unlock(password, salt, encDEK)
        # return self.crypto.dek

    def lock_DEK(self):
        self.crypto.lock()

    def okay(self):
        password = self.password_input.text().strip()
        # developed for when user wants to turn off require pass.
        self.password = password
        # How can we know if the DEK is valid

        try:
            assert self.password_input is not None
            self.password_input.clear()
        except Exception:
            pass

        try:
            if self.db.get_config("password_hash") == self.crypto.pass_hash(password):
                self.correct = True
                self.unlock_DEK(password)
                self.accept()
            else:
                QMessageBox.information(
                    self, "Incorrect Password", "Please enter the Correct Password")
        except Exception as e:
            QMessageBox.information(
                self, "Tampered Database", "Your Notes database might have been tampered with.")

    def validate_silent_password(self, password):
        """`password=""` is used for silent logins."""
        if self.db.get_config("password_hash") == self.crypto.pass_hash(password):
            self.correct = True
            self.unlock_DEK(password)
            return True
        else:
            self.correct = False
            return False
            # tampered with default password or something else.
