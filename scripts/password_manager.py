import hashlib
import string
from scripts import Settings
from scripts.constants import NOTE_CRYPTOGRAPHIC_KEY, PASS_FILE, APP_PHOTO

from PyQt5.QtGui import QIcon

from PyQt5.QtWidgets import (QLabel, QPushButton,
                             QVBoxLayout,
                             QMessageBox,
                             QDialog,
                             QLineEdit,
                             QFormLayout)
from cryptography.fernet import Fernet
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Cipher import AES, PKCS1_OAEP


class Cryptography:
    def __init__(self) -> None:
        self.key = None
        self.crypter = None
        self.public_key = None
        self.settings_manager = Settings(None, None)
        self.get_or_generate_key()

    def get_or_generate_key(self):
        """first time things"""
        self.key = NOTE_CRYPTOGRAPHIC_KEY
        self.crypter = Fernet(self.key.encode())
        return self.key

    def encrypt_note(self, text: str):
        # XXX: Highly breakable in the sense that a new key can be mistakenly generated
        self.get_or_generate_key()
        _data = self.crypter.encrypt(text.encode())
        return _data

    def decrypt_note(self, text: bytes):
        # XXX: Highly breakable in the sense that a new key can be mistakenly generated
        self.get_or_generate_key()
        _data = self.crypter.decrypt(text)
        return _data.decode()


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
    def __init__(self, db, settings_manager, new=False, change=False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowIcon(QIcon(str(APP_PHOTO)))
        self.correct = False
        self.db = db
        self.settings_manager = settings_manager
        self.set_new = new
        self.change_pass = change

        self.password_file = PASS_FILE
        self.cipher = SimpleCipher()

        # NOTE: This is required as the first sanity check.
        self.init_ui()

        self.hashed = None

        if not self.set_new:
            self.hashed = self.get_hashed()

        self.crypto = Cryptography()

    def encrypt_note(self, note_content):
        return self.crypto.encrypt_note(note_content)

    def decrypt_note(self, encrypted_content):
        return self.crypto.decrypt_note(encrypted_content)

    def set_message(self, msg, color="#b50000"):
        """only show message when this func is called"""
        self.status.show()
        self.status.setText(msg)
        self.status.setStyleSheet(f"color:{color};")

    def init_ui(self):
        self.setWindowTitle("Enter Password")
        self.setMaximumSize(700, 500)
        self.setMinimumSize(400, 300)
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.new_password_input = QLineEdit()
        self.old_password_input = QLineEdit()
        self.confirm_password_input = QLineEdit()
        self.password_hint_input = QLineEdit()

        self.save_button = QPushButton("Ok")

        self.status = QLabel()
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
            self.save_button.clicked.connect(self.okay_new)

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
            ps_hint = self.settings_manager.password_hint
            if ps_hint:
                self.set_message(
                    f"{self.status.text()}\nPassword Hint: {ps_hint}".strip(), "#21ec21")
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow("Password:", self.password_input)
            self.confirm_password_input = None
            self.new_password_input = None
            self.save_button.clicked.connect(self.okay)

        self.cancel_button = QPushButton("Quit")
        self.cancel_button.clicked.connect(self.reject)

        self.status.hide()
        main_layout.addWidget(self.status)
        main_layout.addLayout(form_layout)
        main_layout.addWidget(self.save_button)
        main_layout.addWidget(self.cancel_button)

        # main_layout.addStretch()

        self.setLayout(main_layout)

    def save_password_hint(self):
        self.settings_manager.password_hint = self.password_hint_input.text()

    def get_hashed(self):
        """The last place to check is the DB itself"""

        def search_pass_file():
            # Attempt 1
            if self.password_file.exists():
                with open(self.password_file, 'r') as f:
                    passfile_hash = f.readline().strip()
                if passfile_hash:
                    return passfile_hash
                else:
                    return ""
            else:
                return ""

        def search_regs():
            # Attempt 2: get the pass saved from reg.
            p_hist_stored_hash = str(self.settings_manager.password_version)
            if (p_hist_stored_hash.strip()):
                return p_hist_stored_hash.strip()
            else:
                print("p_hist also tampered. Security flags raised: 2")
                return ""

        def search_db():
            # Attempt 3: get it from the db itself.
            db_stored_hash = str(self.db.get_config("master_password"))
            if db_stored_hash.strip():
                return db_stored_hash.strip()
            else:
                return ""

        passfile_stored_hash = search_pass_file()
        reg_hash = search_regs()
        stored_hash = search_db()

        def check():
            sh = stored_hash or None
            rh = reg_hash or None
            ph = passfile_stored_hash or None
            print(sh == rh == ph)

        check()

        return stored_hash or passfile_stored_hash or reg_hash or None

    def save_hashed(self, new_pass_hash):
        """save the hashed password"""

        with open(self.password_file, 'w') as f:
            f.write(new_pass_hash)

        self.db.set_config("master_password", new_pass_hash)

        self.settings_manager.password_version = new_pass_hash

    def okay_new_change(self):
        self.current_pass = self.hashed
        if self.current_pass is not None:
            if self.cipher.pass_hash(self.old_password_input.text()) != self.current_pass:
                QMessageBox.critical(
                    self,
                    "Incorrect Password",
                    "The current password is incorrect."
                )
                return

        new_password = self.new_password_input.text().strip()  # type: ignore
        confirm = self.confirm_password_input.text().strip()  # type: ignore

        if not new_password:
            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password cannot be empty."
            )
            return

        if new_password != confirm:
            QMessageBox.warning(
                self,
                "Password Mismatch",
                "The passwords do not match."
            )
            return

        hashed = self.cipher.pass_hash(confirm)
        self.save_hashed(hashed)
        self.save_password_hint()

        QMessageBox.information(
            self,
            "Success",
            "Password saved successfully."
        )
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

        self.correct = True
        self.accept()

    def okay_new(self):
        self.current_pass = self.new_password_input.text()

        if not (self.confirm_password_input.text() == self.new_password_input.text()):
            QMessageBox.critical(
                self,
                "Password Mismatch",
                "Confirm and new Password must match exactly")
            return
        hashed = self.cipher.pass_hash(self.current_pass)
        self.save_hashed(hashed)
        self.save_password_hint()
        QMessageBox.information(self, "Password Set", "Password Set, Welcome")
        self.correct = True

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

    def okay(self):
        self.current_pass = self.password_input.text()

        try:
            assert self.password_input is not None
            self.password_input.clear()
        except Exception:
            pass

        if self.hashed is not None:
            if self.cipher.pass_hash(self.current_pass) == self.hashed:
                self.correct = True
                # Initiate the repopulation
                self.get_hashed()

                self.accept()
            else:
                QMessageBox.critical(self, "Incorrect Password",
                                     "Incorrect Password, Please try again.")

        else:
            QMessageBox.critical(
                self, "Corrupt password file",
                "Pass file, tampered with.")
