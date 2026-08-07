

from PyQt5.QtWidgets import (QMainWindow, QCheckBox,
                             QPushButton,
                             QVBoxLayout,
                             QMessageBox,
                             QInputDialog,
                             QDialog)
from PyQt5.QtGui import QIcon

from scripts.constants import APP_NAME, APP_PHOTO

from . import Settings


class SettingsDialog(QDialog):
    def __init__(self, db_manager, pman_uninit_class, parent: QMainWindow):
        """`password_manager_class` must be a fresh uninitialized class. i.e.

        ```
        SettingsDialog(...,password_manager_class = PasswordManager,...)
        ```
        NOT

        ```
        SettingsDialog(..., password_manger_class = PasswordManager(), ...)
        ```

        """
        super().__init__(parent)
        self.setWindowIcon(QIcon(str(APP_PHOTO)))

        self.db = db_manager
        self.settings_manager = Settings(self.db)

        self.password_manager = pman_uninit_class
        # initialize the class

        self.parent_app = parent
        self.lock = pman_uninit_class(self.db, self.settings_manager)
        self.current_password = self.lock.get_hashed()
        self.has_existing_password = self.current_password is not None

        self.require_pass_at_startup = self.settings_manager.require_password

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Settings")
        self.setFixedSize(420, 320)

        main_layout = QVBoxLayout()
        # form_layout = QFormLayout()

        # -----------------------------
        # Password Fields
        # -----------------------------

        self.require_password = QCheckBox("Request Password at startup")
        self.require_password.setObjectName("require_pass_at_startup")

        gotten_setting = self.settings_manager.require_password

        if gotten_setting:
            self.require_password.setChecked(True)
        else:
            self.require_password.setChecked(False)

        self.require_password.clicked.connect(
            lambda: self.set_setting(self.require_password))

        main_layout.addWidget(self.require_password)

        self.autolock_app = QCheckBox(
            "Automatically lock app when you leave")
        self.autolock_app.setObjectName("autolock_app")
        self.autolock_app.hide()

        if self.require_password.isChecked():
            self.autolock_app.show()
        else:
            self.settings_manager.autolock_enabled = False
            self.autolock_app.hide()

        if not self.parent_app.is_premium_user():
            self.autolock_app.setText(
                f"{self.autolock_app.text()} (Premium)")

        gotten_setting = (
            self.settings_manager.autolock_enabled and self.parent_app.is_premium_user())
        if gotten_setting:
            self.autolock_app.setChecked(True)
        else:
            self.autolock_app.setChecked(False)

        self.autolock_app.clicked.connect(
            lambda: self.set_setting(self.autolock_app))

        self.warn_unprotected = QCheckBox("Warn me when unprotected")
        self.warn_unprotected.setObjectName("warn_unprotected")
        self.warn_unprotected.setToolTip(
            f"Warn me if my {APP_NAME} is not Password Protected.")

        gotten_setting = (self.settings_manager.warn_if_unprotected)
        if gotten_setting:
            self.warn_unprotected.setChecked(True)
        else:
            self.warn_unprotected.setChecked(False)

        self.warn_unprotected.clicked.connect(
            lambda: self.set_setting(self.warn_unprotected))

        main_layout.addWidget(self.warn_unprotected)
        main_layout.addWidget(self.autolock_app)

        # -----------------------------
        # Danger Zone
        # -----------------------------
        self.change_pass_button = QPushButton("Change Password")
        self.change_pass_button.clicked.connect(self.change_pass)
        main_layout.addWidget(self.change_pass_button)

        self.clear_notes_button = QPushButton("⚠ Clear All Notes")

        self.clear_notes_button.setStyleSheet("""
            QPushButton{
                background:#ffdddd;
                color:#990000;
                font-weight:bold;
                padding:10px;
            }

            QPushButton:hover{
                background:#ffbcbc;
            }
        """)

        self.clear_notes_button.clicked.connect(self.clear_all_notes)

        main_layout.addWidget(self.clear_notes_button)

        self.setLayout(main_layout)

    # =====================================================
    # Password
    # =====================================================
    def change_pass(self):
        lock = self.password_manager(
            self.db, self.settings_manager, change=True)
        lock.exec()

    def set_setting(self, widget: QPushButton | QCheckBox):
        """The objectName of the `widget` must match the setting key. e.g., require_pass_at_startup"""
        obj_name = widget.objectName()

        if self.require_password.isChecked():
            self.autolock_app.show()
        else:
            self.autolock_app.hide()

        if isinstance(widget, QCheckBox):
            if "require_pass" in obj_name:
                if self.require_password.isChecked():
                    self.settings_manager.require_password = True
                else:
                    self.settings_manager.require_password = False
                    self.settings_manager.autolock_enabled = False

                if self.has_existing_password:
                    lock = self.password_manager(
                        self.db, self.settings_manager)
                    lock.exec()
                    if not lock.correct:
                        self.require_password.setChecked(True)
                        self.settings_manager.require_password = True
                        # keep it locked, they must remember their password.
                        return
                else:
                    lock = self.password_manager(
                        self.db, self.settings_manager, new=True)
                    lock.exec()
                    return

            elif "autolock" in obj_name:
                if self.autolock_app.isChecked():
                    # XXX: Locking this feature
                    if not self.parent_app.is_premium_user():
                        self.autolock_app.setChecked(False)
                        self.parent_app.prompt_buy()
                        return

                    self.settings_manager.autolock_enabled = True
                    if self.settings_manager.is_first_run:
                        QMessageBox.information(
                            self, "Autolock Enabled", "When you don't engage with the app for a while, It will lock automatically.")

                    self.autolock_mins = QInputDialog.getItem(
                        self, "Autolock After", "Autolock After __ Minutes", ["3", "5", "10", "30", "50"], 1, False)

                    # TODO: We can premiumize this editableness too
                    # To allow them to set any time they want.

                    if self.autolock_mins is not None:
                        self.settings_manager.autolock_minutes = self.autolock_mins[0]
                    else:
                        # default is 5 mins
                        self.settings_manager.autolock_minutes = 5

                else:
                    self.settings_manager.autolock_enabled = False
                    QMessageBox.warning(
                        self, "Autolock Disabled", "Autolock Disabled. Just ensure you exit the app or lock the app manually before you leave.")
            elif "warn" in obj_name:
                self.settings_manager.warn_if_unprotected = self.warn_unprotected.isChecked()

        elif isinstance(widget, QPushButton):
            # print(f"Some button clicked {obj_name}")
            pass

    def refresh_ui(self):
        self.init_ui()

    def save_password(self):

        if self.has_existing_password:
            if self.old_password_input.text() != self.current_password:
                QMessageBox.critical(
                    self,
                    "Incorrect Password",
                    "The current password is incorrect."
                )
                return

        new_password = self.new_password_input.text().strip()
        confirm = self.confirm_password_input.text().strip()

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
        # print(new_password)
        self.password_manager.save_hashed(
            self.password_manager.cipher.pass_hash(new_password))

        QMessageBox.information(
            self,
            "Success",
            "Password saved successfully."
        )

        self.accept()

    # =====================================================
    # Clear Notes
    # =====================================================

    def clear_all_notes(self):

        reply = QMessageBox.question(
            self,
            "Delete Everything?",
            (
                "This will permanently delete ALL notes.\n\n"
                "This action cannot be undone.\n\n"
                "Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        reply = QMessageBox.question(
            self,
            "Final Confirmation",
            (
                "Are you absolutely sure?\n\n"
                f"Every note in your {APP_NAME} "
                "will be permanently erased."
            ),
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.db.clear_database_notes()

        if self.parent_app is not None:

            self.parent_app.current_note_id = None
            # self.parent_app.viewer.clear()
            self.parent_app.refresh_notes_list()

        QMessageBox.information(
            self,
            "Completed",
            "All notes have been deleted."
        )

        # self.accept()
