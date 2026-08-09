
import re
import threading

from PyQt5 import QtCore
from PyQt5.QtCore import QObject, QEvent, QTimer
from scripts.auto_updater import AutoUpdater
from scripts.database_manager import DatabaseManager
from scripts.license_manager import LicenseManager
import sys

# import markdown
from scripts.constants import APP_PHOTO, MAX_REMINDER_ABOUT_UPGRADE, MAX_NOTE_AMOUNT, APP_NAME, NOTES_DB

from scripts.password_manager import PasswordManager

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon

from PyQt5.QtWidgets import (QApplication, QMainWindow, QMenuBar, QStatusBar, QToolBar, QWidget,
                             QTextEdit,
                             QListWidget,
                             QListWidgetItem,
                             QPushButton,
                             QAction,
                             QHBoxLayout,
                             QVBoxLayout,
                             QMessageBox,
                             QLineEdit)

from scripts.premium_manager import PremiumTracker
from scripts.settings_manager import Settings, SettingsDialog


class ActivityMonitor(QObject):
    def __init__(self, autolock_timer: QTimer, parent=None):
        super().__init__(parent)

        self.timer = autolock_timer
        self.timer.start()

    def eventFilter(self, obj, event):
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        ):
            self.timer.start()      # Restart idle timer

        return False


class OnBoardingTracker(QObject):
    def __init__(self, timer: QTimer, parent=None) -> None:
        super().__init__(parent)
        self.timer = timer
        self.keys_pressed = 0

    def eventFilter(self, obj, event):
        if event.type() in (
            # QEvent.Type.MouseMove,
            # QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            # QEvent.Type.Wheel,
        ):
            self.timer.start()
            print("typed ", self.keys_pressed)
            self.keys_pressed += 1
        return False


class NoteApp(QMainWindow):
    def __init__(self, parent: QApplication):
        super().__init__()
        self.master = parent

        self.db = DatabaseManager()
        self.settings_manager = Settings(self.db)
        self.premium_tracker = PremiumTracker(self)
        self.autoupdate_checker = AutoUpdater(self)
        self.update_is_available = False

        self.current_note_id = None
        c_title = ""
        c_content = ""
        self.is_read_mode = False
        self.notes = []

        self.app_actions = [
            "New", "Del", "Lock"
        ]

        self.master.setStyleSheet("""
QMainWindow, QDialog{
    background-color: #222222;
    border: none;
    color:#eeeeee;
}

QTextEdit, QLineEdit{
    background:#282828;
    border:none;
    color:#eee;
}

QPushButton{
    background:#333333;
    color:#eeeeee;
}
QPushButton:hover{
    background:#555555;
    color:#eeeeee;
}
QCheckBox{
    color:#eeeeee;
}
QLabel{
    color:#eeeeee;
}
QListWidget{
    color:#eeeeee;
    background:#222222;
    border:none;
}
""")

        # We will falsify the is_first_time the moment the user exits the app for the first time.
        self.main_text_size = self.settings_manager.editor_font_size

        # COUNTERS and VARIABLES
        self.buy_btn_col_flipper = 0
        self.times_reminded_about_password_protection = 0

        # Delayed autosave timer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.auto_save_note)

        self.license_man = LicenseManager(self)
        self.license_man.load_and_validate_license()

        if not self.is_premium_user():
            threading.Thread(target=self.license_man.server_ping_and_price_get,
                             daemon=True).start()

        self.init_ui()
        self.show()

        NOO = self.settings_manager.number_of_opens
        self.settings_manager.number_of_opens = NOO + 1

        self.lock = PasswordManager(
            self.db, self.settings_manager, parent=self)

        # Autolock Timer
        if self.settings_manager.autolock_enabled:
            self.autolock_timer = QTimer(self)
            if self.is_premium_user():
                self.autolock_event_listener = ActivityMonitor(
                    self.autolock_timer, parent=self)
                self.autolock_timer.timeout.connect(self.lock_app)
                self.set_autolock_timer_interval()
                self.master.installEventFilter(self.autolock_event_listener)

        hashes_tampered = [
            False
        ]

        # TODO: Another security idea is for the hash to be recognized by every note, we will propagate the hash that locked them and update them everytime the user changes password so that an attacker cannot just create a new hash of a password they know, then put in the stolen database, if there's a mismatch, we will flag that there's an unknown hash in the master_password of the db. We will encrypt the hashes together with the note titles, when the titles are being loaded (after being decrypted, we extract and remove the hash)

        # NOTE: If there's no notes.db we don't have anything to protect. So we can ask for a new password and save it in that NEW db. Encrypt the DB too.

        fresh_install = [
            ((not self.db.get_config("encDEK").strip()) and (
                not self.db.get_config("salt").strip())),
            (len(self.db.get_all_notes()) <= 0)
        ]

        if all(fresh_install):
            self.settings_manager.is_first_run = True

        self.onboarding_steps = [
            "set_password",
            "set_password_hint",
            "create_one_note",
            "write",
            "manually_lock",
            "unlock",
            "congrats"
        ]
        # We want to check if there are any updates, then we prompt
        if ((self.settings_manager.update_reminders_given < 3)):
            self.background_update_check()
            self.settings_manager.update_reminders_given += 1
        else:
            self.update_btn.show()

        if self.settings_manager.onbrd_stps_completed >= len(self.onboarding_steps):
            self.settings_manager.is_first_run = False

        if self.settings_manager.is_first_run:
            self.begin_onboarding()
        else:
            if self.settings_manager.require_password:
                self.lock_app()
                self.lock.correct = False
                self.refresh_notes_list()
            else:
                # Unprotected entry
                self.unlock_app()

    def begin_onboarding(self, next_step="set_password"):
        """This is recursive in nature. parts of it will call back at the function itself.

        After every if or elif or else block, ensure you call this function with the step you want the user to go to.

        """
        # "set_password",
        # "set_password_hint",
        # "create_one_note",
        # "write",
        # "manually_lock",
        # "unlock",
        # "congrats"
        # Onboarding process

        if self.settings_manager.onbrd_stps_completed > len(self.onboarding_steps):
            self.settings_manager.is_first_run = False

        print(next_step)
        if "set_password" == next_step:
            # NOTE: Must add 'and' logic
            # XXX: Hackable area:

            if (self.settings_manager.is_first_run):
                self.settings_manager.require_password = True
                self.lock = PasswordManager(
                    db=self.db, settings_manager=self.settings_manager, new=True)
                self.lock.set_message(f"""\
Welcome to {APP_NAME}

Please set an easy but hard to guess password.
And a hint to help you remember.

Your Password will be used to encrypt all your notes.
""", "#19d819")

            self.lock.exec()
            # TODO: also secretly check if there's already a notes db.
            # already.
            if not self.lock.correct:
                sys.exit(0)
                return
            self.settings_manager.onbrd_stps_completed = 1
            self.begin_onboarding("set_password_hint")

        elif "set_password_hint" == next_step:
            a = QMessageBox(self)
            a.setWindowTitle("I must remember my Password")
            a.setText(
                "Ensure you remember your password and hint, once you forget them, the only way to reset it is to delete all your notes.")
            a.setIcon(a.Icon.Warning)
            go_back = a.addButton("Go back", a.ButtonRole.NoRole)
            go_back.clicked.connect(
                lambda: self.begin_onboarding("set_password"))
            a.addButton("Next", a.ButtonRole.AcceptRole)
            a.exec()

            self.settings_manager.onbrd_stps_completed += 1
            self.begin_onboarding("create_one_note")

        elif "create_one_note" == next_step:
            a = QMessageBox(self)
            a.setWindowTitle("Encrypted and AutoSaved")
            a.setText("All your notes are saved in one secure place.")
            a.setIcon(a.Icon.Information)
            a.addButton("Start Writing", a.ButtonRole.AcceptRole)
            a.exec()

            self.settings_manager.onbrd_stps_completed += 1
            self.begin_onboarding("write")
            pass

        elif "write" == next_step:
            # self.editor.blockSignals(True)
            self.title_entry.blockSignals(True)
            self.title_entry.setText("First Note to Self")
            self.editor.setPlaceholderText(
                "Don't fear the blank page... Start with 'Hello' or something controversial. LOL.")
            self.editor.setFocus()

            timer = QTimer(self)
            timer.setInterval(3_000)
            tracker = OnBoardingTracker(timer, parent=self)
            self.master.installEventFilter(tracker)

            def to_next():
                a = QMessageBox(self)

                boost = ""
                a.setWindowTitle(
                    f"Nice But Don't Expose Yourself")
                if tracker.keys_pressed > 20:
                    boost = "Nice. That's what I call a piece of art.\n"

                a.setText(f"""\
{boost}
When you want to write sensitive notes, don't use notepad.

Instead, lock all your notes in {APP_NAME}.""")

                a.setIcon(a.Icon.Information)
                lock = a.addButton("Secure Your Notes",
                                   a.ButtonRole.AcceptRole)
                a.exec()

                timer.stop()
                self.master.removeEventFilter(tracker)
                self.settings_manager.onbrd_stps_completed += 1
                self.begin_onboarding("manually_lock")

            timer.timeout.connect(to_next)

            # wait for user to start writing. When they start and we have move on after celebrating them.

        elif "manually_lock" == next_step:
            col = "#9b0d0d"
            self.lock_app_btn.setStyleSheet("""QPushButton{
            background:#9b0d0d;} QPushButton{ background:#ac1e1e;}""")
            self.lock_app_btn.clicked.disconnect()

            def onboard_lock():
                self.editor.blockSignals(True)
                self.title_entry.blockSignals(True)
                self.notes_list_widget.clear()
                self.editor.clear()
                self.title_entry.clear()

                self.current_note_id = None
                lock = PasswordManager(
                    self.db, self.settings_manager, parent=self)
                lock.set_message(
                    f"Now enter your set password to unlock your {APP_NAME}.", "#14b324")
                lock.exec()
                if not lock.correct:
                    sys.exit(0)
                    return
                self.settings_manager.onbrd_stps_completed += 1
                self.begin_onboarding("unlock")

            self.lock_app_btn.clicked.connect(lambda: onboard_lock())

        elif "unlock" == next_step:
            self.title_entry.blockSignals(False)
            self.editor.blockSignals(False)
            self.lock_app_btn.clicked.disconnect()
            self.lock_app_btn.setStyleSheet("")
            self.lock_app_btn.clicked.connect(self.lock_app)
            self.refresh_notes_list()

            a = QMessageBox(self)
            a.setWindowTitle("Well Done and Welcome")
            a.setText(
                f"Welcome to {APP_NAME}! It is a more private alternative to notepad for avid note-takers like you.")
            a.setIcon(a.Icon.Information)
            a.addButton("Start Writing", a.ButtonRole.AcceptRole)
            a.exec()

            self.settings_manager.onbrd_stps_completed += 1
            self.begin_onboarding("congrat")

        elif "congrat" == next_step:
            self.title_entry.blockSignals(False)
            self.editor.blockSignals(False)
            self.editor.setPlaceholderText("Think...")

            a = QMessageBox(self)
            a.setWindowTitle(f"Support {APP_NAME}")
            a.setText(
                f"Before you go on, consider supporting the cause of creating more offline-friendly and private software for people with unreliable internet and people who don't like how AI is integrated into everything.")
            a.setIcon(a.Icon.Information)
            support = a.addButton(
                f"Support {APP_NAME}", a.ButtonRole.YesRole)
            support.clicked.connect(self.open_license_buy)
            a.addButton("Skip", a.ButtonRole.NoRole)
            a.exec()

            self.settings_manager.onbrd_stps_completed += 1

    def get_all_notes_with_contents(self):
        """for search"""
        self.notes = self.db.get_all_notes_with_content()

    def search(self):
        """TODO: sort based on search result"""
        try:
            search_term = self.notes_list_search.text()

            if not search_term:
                self.refresh_notes_list()
                return

            self.notes_list_widget.clear()
            final_ranking = []
            for note in self.notes:
                note_ = note['title']
                if ((re.search(search_term, f"{note_}: {self.decrypt_note_content(note['content'])}", re.IGNORECASE) is not None)):
                    final_ranking.append(note)

            for note in final_ranking:
                item = QListWidgetItem(note['title'])
                item.setData(Qt.UserRole, note["id"])  # type: ignore
                self.notes_list_widget.addItem(item)
        except Exception as e:
            print(f"error in search: {e}")

    def restart_app(self):
        # os.execv(sys.executable, [sys.executable]+sys.argv)
        print("you should restart")

    def init_ui(self):
        self.setWindowTitle("Thought Book")
        self.resize(1200, 600)

        # ===========================
        # Main Layout
        # ===========================

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===========================
        # Sidebar
        # ===========================

        sidebar = QWidget()
        sidebar.setFixedWidth(50)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        notes_list_sidebar = QWidget()
        notes_list_sidebar.setFixedWidth(250)

        notes_list_sidebar_layout = QVBoxLayout(notes_list_sidebar)
        notes_list_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        notes_list_sidebar_layout.setSpacing(0)

        # ---------------------------
        # Action List
        # ---------------------------

        self.action_sidebar = QToolBar(self)
        self.action_sidebar.setStyleSheet(
            r"QPushButton{border:none;padding:5px 0px;background:transparent;}"
            r"QPushButton:hover{background:#333333;}"
        )
        self.action_sidebar.setOrientation(QtCore.Qt.Orientation.Vertical)
        self.action_sidebar.setMinimumWidth(20)
        # self.action_sidebar.setFixedHeight(110)

        self.new_note_btn = QPushButton("New")
        self.del_note_btn = QPushButton("Del")
        self.lock_app_btn = QPushButton("Lock")

        self.new_note_btn.clicked.connect(self.create_new_note)
        self.del_note_btn.clicked.connect(self.delete_current_note)
        self.lock_app_btn.clicked.connect(self.lock_app)

        self.action_sidebar.addWidget(self.new_note_btn)
        self.action_sidebar.addWidget(self.del_note_btn)
        self.action_sidebar.addWidget(self.lock_app_btn)

        sidebar_layout.addWidget(self.action_sidebar)
        self.refresh_actions_UI()

        # ---------------------------
        # Notes List
        # ---------------------------

        self.notes_list_widget = QListWidget()
        self.notes_list_widget.itemClicked.connect(
            self.handle_note_selection
        )

        self.notes_list_search = QLineEdit()
        self.notes_list_search.setPlaceholderText("Search")
        self.notes_list_search.textChanged.connect(
            self.search
        )

        notes_list_sidebar_layout.addWidget(self.notes_list_search)
        notes_list_sidebar_layout.addWidget(self.notes_list_widget)

        sidebar_layout.addStretch()

        # ---------------------------
        # Settings Button
        # ---------------------------

        self.premium_button = QPushButton("Buy")
        # self.premium_button.setStyleSheet("background:#edd;")
        self.premium_button.clicked.connect(
            self.open_license_buy
        )
        self.premium_button.hide() if self.is_premium_user() else self.premium_button.show()

        self.settings_button = QPushButton("⚙")
        self.settings_button.clicked.connect(
            self.open_settings_dialog
        )

        sidebar_layout.addWidget(self.premium_button)
        sidebar_layout.addWidget(self.settings_button)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(notes_list_sidebar)

        # ===========================
        # Workspace
        # ===========================

        workspace = QWidget()
        self.stack = QVBoxLayout(workspace)

        # Editor

        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText("Title...")
        self.title_entry.returnPressed.connect(
            lambda: self.editor.setFocus())
        self.title_entry.textChanged.connect(
            self.trigger_autosave
        )

        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Think...")
        self.editor.textChanged.connect(
            self.trigger_autosave
        )
        self.editor_font = QFont("sans-serif")
        self.editor.setFontPointSize(self.main_text_size)
        self.editor.setFont(self.editor_font)

        self.stack.addWidget(self.title_entry)
        self.stack.addWidget(self.editor)

        # workspace_layout.addWidget(self.stack)

        main_layout.addWidget(workspace)

        # ===========================
        # Central Widget
        # ===========================

        container = QWidget()
        container.setLayout(main_layout)

        self.setCentralWidget(container)

        # ===========================
        # Menu Bar & Status Bar
        # ===========================
        self.statusArea = QStatusBar(self)
        self.statusArea.setStyleSheet("color:#eee;")
        self.setStatusBar(self.statusArea)

        self.menuArea = QMenuBar(self)
        self.menuArea.setStyleSheet("""
QMenuBar{
background:#222;
color:#eee;
}
QMenuBar::item:selected{
background:#333;
color:#eee;
}
QMenu{
background:#222;
color:#eee;
}

QMenu::item:selected{
background:#888;
color:#eee;
}""")

        self.setMenuBar(self.menuArea)

        view_menu = self.menuArea.addMenu("View")  # type: ignore

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut("Ctrl+=")
        self.zoom_in_action.triggered.connect(lambda: self.zoom("in"))

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.zoom_out_action.triggered.connect(lambda: self.zoom("out"))

        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)

        help_menu = self.menuArea.addMenu("Help")  # type: ignore

        self.buy_action = QAction(f"Buy {APP_NAME}", self)
        self.buy_action.triggered.connect(lambda: self.open_license_buy())
        self.buy_action.setVisible(not self.is_premium_user())

        self.update_check_action = QAction(f"Check for Updates", self)
        self.update_check_action.triggered.connect(
            lambda: self.obvi_update_check())

        self.update_btn = QPushButton("Update Now")
        self.update_btn.clicked.connect(self.update_now)
        self.update_btn.hide()

        self.statusArea.addPermanentWidget(self.update_btn)

        help_menu.addAction(self.buy_action)
        help_menu.addAction(self.update_check_action)

        self.enablePassword = QPushButton("Enable Password")

        def enpass():
            self.settings_manager.require_password = True
            self.inform_user(
                f"Your {APP_NAME} is now Password Protected. Ensure you remember it though.")
            self.enablePassword.hide()

        self.enablePassword.clicked.connect(enpass)
        self.enablePassword.setStyleSheet("color:#ccc;")
        self.enablePassword.hide()

        self.statusArea.addPermanentWidget(self.enablePassword)

    # =====================================================
    # Note Management
    # =====================================================
    def background_update_check(self):
        threading.Thread(target=self._check_for_updates,
                         args=(True,), daemon=True).start()

    def update_now(self):
        print("Updating...")
        pass

    def obvi_update_check(self):
        """Give notification for the availability"""
        threading.Thread(target=self._check_for_updates,
                         args=(False,), daemon=True).start()

    def get_update_availability_status(self, status):
        if status:
            self.inform_user(
                f"Your {APP_NAME} needs an update to stay secure.")
            self.update_btn.show()
        elif not status:
            self.update_btn.hide()
        else:
            print("some error")
            pass

        # silently fail.

        return status

    def _check_for_updates(self, silent=False):
        update_is_available = self.autoupdate_checker._check()
        if silent:
            self.update_is_available = self.get_update_availability_status(
                update_is_available)

        if not silent:
            if update_is_available:
                a = QMessageBox()
                a.setIcon(a.Icon.Information)
                a.setWindowTitle(f"{APP_NAME} update is available")
                a.setText(
                    f"{APP_NAME} needs an update. Do you want to install updates now?")
                update = a.addButton("Yes", a.ButtonRole.AcceptRole)
                # Do the actual download. same as the subtle statusArea button
                update.clicked.connect()
                a.addButton("No", a.ButtonRole.RejectRole)
                a.exec()
            elif update_is_available is False:
                a = QMessageBox.information(None, f"{APP_NAME} is Up to Date",
                                            f"{APP_NAME} is Up to date.")
            else:
                QMessageBox.critical(
                    None, "Something happened", f"Update checking encountered a problem, might be from our server or a connection problem. Try checking for updates later.")

    def open_license_buy(self):
        """Manage Licenser"""

        self.license_man._show_license_window()

    def open_donation_box(self):
        # What is the ruling on asking for donations
        pass

    def prompt_buy(self, feature_name="this feature"):
        a = QMessageBox()
        a.setIcon(a.Icon.Information)
        a.setWindowTitle(f"Buy {APP_NAME}")
        a.setText(
            f"Purchase {APP_NAME} to enjoy {feature_name}")
        buy_bt = a.addButton("Purchase", a.ButtonRole.AcceptRole)
        buy_bt.clicked.connect(self.open_license_buy)
        buy_bt.setStyleSheet("""QPushButton{
            background:#ddffdd;
            color:#009900;
            font-weight:bold;
            padding:7px 10px;
            border:none;
            border-radius:3px;
        }

        QPushButton:hover{
            background:#bcffbc;
        }""")
        a.addButton("Cancel", a.ButtonRole.RejectRole)
        a.exec()

    def open_settings_dialog(self):
        self.settings_dialog = SettingsDialog(
            self.db, PasswordManager, parent=self)
        self.settings_dialog.accepted.connect(self.after_settings_exit)
        self.settings_dialog.rejected.connect(self.after_settings_exit)
        self.settings_dialog.exec()

    def lock_app(self):
        self.editor.blockSignals(True)
        self.title_entry.blockSignals(True)
        self.notes_list_widget.clear()
        self.editor.clear()
        self.title_entry.clear()
        self.current_note_id = None
        self.lock.lock_DEK()

        # make a new instance so that any data saved from the
        # prev instance disappears
        self.lock = PasswordManager(
            db=self.db, settings_manager=self.settings_manager)
        # self.db = None
        self.lock.exec()
        if not self.lock.correct:
            self.master.exit(0)
            sys.exit(0)
            return
        else:
            self.unlock_app()

    def refresh_actions_UI(self):
        for act in self.app_actions:
            if "new" in act.lower():
                self.new_note_btn.setVisible(True)

            elif "del" in act.lower():
                self.del_note_btn.setVisible(True)

            elif "lock" in act.lower():
                if self.settings_manager.require_password:
                    self.lock_app_btn.setVisible(True)

                else:
                    self.lock_app_btn.setVisible(False)

    def unlock_app(self):
        self.db = DatabaseManager()
        self.refresh_notes_list()
        self.refresh_actions_UI()
        self.editor.blockSignals(False)
        self.title_entry.blockSignals(False)
        self.editor.blockSignals(False)
        self.title_entry.blockSignals(False)

    def after_settings_exit(self):
        """After we exit settings, this func will refresh the UI by checking all setting and applying those changes"""
        self.refresh_actions_UI()
        self.refresh_notes_list()

    def delete_current_note(self):
        if self.current_note_id is None:
            return

        self.db.delete_note(self.current_note_id)

        self.refresh_notes_list()

        self.editor.blockSignals(True)
        self.title_entry.blockSignals(True)
        self.editor.clear()
        self.title_entry.clear()
        self.editor.blockSignals(False)
        self.title_entry.blockSignals(False)

        self.current_note_id = None

    def set_autolock_timer_interval(self):
        """Autolock timer similar to autosave. It will be triggered everytime you make an action within the app. meaning, that any action you do while the app has focus, then this will be triggered and set for the interval minutes you set.
        """
        if not self.is_premium_user():
            return

        interval_mins = self.settings_manager.autolock_minutes
        if interval_mins:
            self.autolock_timer.setInterval((interval_mins*60)*1000)
        else:
            self.autolock_timer.setInterval((5*60)*1000)
        # TODO: How to use events in pyqt5 to track usage so as to ensure user is using app, if not, then automatically lock after set minutes...

    def trigger_autosave(self):
        # print("scheduling autosave")
        self.autosave_timer.setInterval(1000)
        self.autosave_timer.start()

    def lock_unlimited_notes(self):
        """Disallow further action through:
       ```python
       if lock_feature_until_paid():
            return
       ```"""

        checks = (
            (self.premium_tracker.note_count
             >= MAX_NOTE_AMOUNT) or (
                self.get_note_count() > MAX_NOTE_AMOUNT))

        if checks:
            if not self.is_premium_user():
                reminded_times = self.premium_tracker.reminders_given

                if not (reminded_times > MAX_REMINDER_ABOUT_UPGRADE):
                    self.prompt_buy()
                    self.premium_tracker.reminders_given = reminded_times+1
                else:
                    if not self.premium_button.isVisible():
                        self.premium_button.show()
                    else:
                        col = "#ffdcdc"
                        if self.buy_btn_col_flipper % 2 == 0:
                            col = "#ffb2b2"
                        else:
                            col = "#ffdcdc"
                        self.premium_button.setStyleSheet(
                            f"background:{col};")
                        self.buy_btn_col_flipper += 1

                # TODO: Open license buying page.
                return True
            else:
                # NOTE: this person has paid
                return False

    def is_premium_user(self):
        """This will be defined by the presence of the license key. If it has been tampered, then we automatically lock the app again by returning False. until the user resolves their issue, only then, we return True."""
        return self.license_man.is_premium_user()
        # return True

    def inform_user(self, info, col="#f6f6f6", for_secs=8):
        self.statusArea.showMessage(info, for_secs*1000)
        self.statusArea.setStyleSheet(f"color:{col};")

    def auto_save_note(self):
        c_title = self.title_entry.text()
        c_content = self.editor.toPlainText().strip()

        self.editor.setFontPointSize(self.main_text_size)
        # ensure there's something before saving.
        if c_content:
            c_content = self.lock.encrypt_note(
                self.lock.crypto.dek, c_content)

            if not c_title:
                self.title_entry.setText("Untitled")

            assert self.db is not None
            self.db.save_note_content(
                self.current_note_id,
                c_title,
                c_content.decode())

        if self.current_note_id is None:
            self.create_new_note()
            return

        self.refresh_notes_list()

        # Remind user subtly about if his notes are not protected.
        if (not self.settings_manager.require_password) and (self.settings_manager.warn_if_unprotected):
            self.enablePassword.show()

            if self.times_reminded_about_password_protection < 3:
                self.inform_user(
                    f"Your {APP_NAME} is not protected currently. Careful not to write any sensitive stuff. Or enable Password now.", "#FF2424")
                self.times_reminded_about_password_protection += 1
            elif (self.times_reminded_about_password_protection > 3) and (self.times_reminded_about_password_protection < 6):
                self.inform_user(
                    f"Your {APP_NAME} is not protected currently. Careful not to write any sensitive stuff. Or enable Password now.", "#656565")
                self.times_reminded_about_password_protection += 1
            else:
                # Leave the enable password button there.
                # when they decide, they can enable it.
                pass

        self.select_note(self.current_note_id)

        # zoom must be maintained
        self.editor.setFontPointSize(self.main_text_size)

        # print("autosaved")

    def zoom(self, type_):
        tmp = ""
        if "in" in type_:
            # print(type_)
            self.main_text_size += 2
            tmp = self.editor.toPlainText()
            self.editor.blockSignals(True)
            self.editor.selectAll()
            self.editor.setFontPointSize(self.main_text_size)
            self.editor.insertPlainText(tmp)

        elif "out" in type_:
            # print(type_)
            self.main_text_size -= 2
            tmp = self.editor.toPlainText()
            self.editor.blockSignals(True)
            self.editor.selectAll()
            self.editor.setFontPointSize(self.main_text_size)
            self.editor.insertPlainText(tmp)

        self.editor.blockSignals(False)
        self.settings_manager.editor_font_size = self.main_text_size

    def refresh_notes_list(self):
        """
        Reload every note from the database into the sidebar.
        """
        self.notes_list_widget.clear()
        # print("sdf")

        assert self.db is not None
        notes = self.db.get_all_notes()

        # For search...update
        self.get_all_notes_with_contents()

        # update the premium tracker number
        self.premium_tracker.note_count = len(notes)

        for note in notes:
            item = QListWidgetItem(note["title"])
            item.setData(Qt.UserRole, note["id"])  # type: ignore
            self.notes_list_widget.addItem(item)

    def create_new_note(self):
        """
        Prompt for a title and create a new note.
        """
        if self.lock_unlimited_notes():
            # print("Sorry, please buy me.")
            return

        title = ""
        content = ""
        if self.current_note_id is None:
            title = self.title_entry.text()
            content = self.editor.toPlainText()

        self.current_note_id = None

        note_id = self.db.create_note(title, content)

        self.current_note_id = note_id

        self.refresh_notes_list()
        # self.display_note_content()
        self.select_note(note_id)

        if (not title.strip()):
            self.title_entry.setText("Untitled")
            if not content.strip():
                self.editor.clear()
                self.title_entry.setFocus()
                self.title_entry.selectAll()
            return

    def select_note(self, note_id):
        # Automatically select the new note
        for row in range(self.notes_list_widget.count()):

            item = self.notes_list_widget.item(row)

            if item.data(Qt.UserRole) == note_id:
                self.notes_list_widget.setCurrentItem(item)
                break

    def handle_note_selection(self, item):
        """
        User clicked a note in the sidebar.
        """

        note_id = item.data(Qt.UserRole)

        if note_id is None:
            return

        self.current_note_id = note_id

        self.display_note_content()

    def display_note_content(self):
        """
        Load the selected note into the editor.
        """

        if self.current_note_id is None:
            return

        assert self.db is not None
        info = self.db.get_note_content(
            self.current_note_id
        )

        self.title = ""
        c_content = ""

        self.title = info[0]
        c_content = info[1]

        try:
            if c_content.strip():
                c_content = self.lock.decrypt_note(
                    self.lock.crypto.dek, c_content)
            else:
                self.editor.setPlaceholderText(
                    "Write like an independent thinker...")
        except Exception as e:
            print(e)
            self.editor.setPlaceholderText(
                "Sorry, this note is not decryptable, it is lost forever.")

        # Prevent autosave from firing while loading

        self.editor.blockSignals(True)
        self.title_entry.blockSignals(True)
        self.title_entry.setText(self.title)
        self.editor.setPlainText(c_content)
        self.title_entry.blockSignals(False)
        self.editor.blockSignals(False)

        # Always return to edit mode when opening a note
        self.is_read_mode = False

    def get_note_count(self):
        try:
            assert self.db is not None
            return len(self.db.get_all_notes())
        except Exception as e:
            return 0

    def abouttoquit(self):
        """What to do when user is leaving"""
        print("bye")


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_PHOTO)))
    window = NoteApp(app)
    window.setWindowIcon(QIcon(str(APP_PHOTO)))
    app.aboutToQuit.connect(window.abouttoquit)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
