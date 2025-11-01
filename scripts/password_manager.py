import hashlib
import string
import tkinter.messagebox as tkmsg

from scripts.utils import (verify_recovery_key,
                           askstring,
                           set_recovery_key)


class PasswordManager:
    def __init__(self, master):
        self.master = master
        self.cipher = self.master.cipher
        self.password_file = self.master.password_file

    def forgot_password(self):
        """Handle password recovery via recovery code input."""
        code = askstring(
            "Recovery",
            "Enter recovery code:\n\nWrite this recovery code down in a safe place.\nLosing it means you cannot reset your password.",
            show="*")

        if code is None:
            return False
        
        if code.lower() == "exit":
            exit()

        if verify_recovery_key(code):
            new_pass = askstring(
                "New Password", "Enter new password:", show="*")
            if new_pass:
                with open(self.password_file, 'w') as f:
                    f.write(self.cipher.pass_hash(new_pass))
                tkmsg.showinfo("Success", "Password reset successfully!")
                return True
        else:
            tkmsg.showerror("Error", "Invalid recovery code.")
            return False

    def ask_password(self):
        """Prompt user for password and validate or trigger recovery."""
        try:
            with open(self.password_file, 'r') as f:
                stored_hash = f.readline().strip()

            entered = askstring(
                "Password", "Enter password (or leave blank to reset):", show="*")
            if entered is None:
                return "Cancelled"
            if entered.lower() == "exit":
                return "exit"
            if entered == "":
                return self.forgot_password()

            if self.cipher.pass_hash(entered) == stored_hash:
                return True
            else:
                tkmsg.showerror("Error", "Incorrect password.")
                return False

        except FileNotFoundError:
            # First-time setup
            new_pass = askstring("Password", "Create password:", show="*")
            if new_pass is None:
                return "Cancelled"

            with open(self.password_file, 'w') as f:
                f.write(self.cipher.pass_hash(new_pass))

            recovery = askstring(
                "Recovery Code", "Set a recovery code (write it down somewhere safe):", show="*")
            if recovery:
                set_recovery_key(recovery)

            tkmsg.showinfo("Info", "Password and recovery code set.")
            return True


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
