
import re
import threading

from PyQt5 import QtCore
from PyQt5.QtCore import QObject, QEvent, QTimer, pyqtSignal, pyqtSlot
from scripts.auto_updater import AutoUpdater, ProgressDialog
from scripts.database_manager import DatabaseManager
from scripts.markdown_editor import PlainTextMarkdownAdapter
from scripts.license_manager import LicenseManager
import sys

# import markdown
from scripts.constants import APP_PHOTO, APP_VERSION, MAX_REMINDER_ABOUT_UPGRADE, MAX_NOTE_AMOUNT, APP_NAME, NOTES_DB

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
                             QLineEdit, QSplitter, QSizePolicy)

from scripts.premium_manager import PremiumTracker
from scripts.settings_manager import Settings, SettingsDialog
from scripts.threading import Signals


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
        self.times_reminded_about_autolock = 0

        # Delayed autosave timer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self.auto_save_note)

        self.license_man = LicenseManager(self)
        self.license_man.load_and_validate_license()

        self.init_ui()
        self.show()

        if not self.is_premium_user():
            threading.Thread(target=self.license_man.server_ping_and_price_get,
                             daemon=True).start()

        NOO = self.settings_manager.number_of_opens
        self.settings_manager.number_of_opens = NOO + 1

        self.lock = PasswordManager(
            self.db, self.settings_manager, parent=self)

        self.autolock_timer = QTimer(self)
        self.autolock_event_listener = ActivityMonitor(
            self.autolock_timer, parent=self)

        self.start_autolock_engine()

        hashes_tampered = [
            False
        ]

        fresh_install = [
            ((not self.db.get_config("encDEK").strip()) and (
                not self.db.get_config("salt").strip())),
            (len(self.db.get_all_notes()) <= 0)
        ]

        if all(fresh_install):
            self.settings_manager.is_first_run = True
            self.settings_manager.onbrd_stps_completed = 0

        self.onboarding_steps = [
            "set_password",
            "set_password_hint",
            "create_one_note",
            "write",
            "manually_lock",
            "unlock",
            "congrats"
        ]

        # ==================AUTO-UPDATE-CHECK================
        # We want to check if there are any updates, then we prompt
        self.silent_update_signal = Signals()
        self.loud_update_signal = Signals()
        self.download_update_signal = Signals()

        self.loud_update_signal.finished.connect(self.loud_update_notify)
        self.loud_update_signal.progress.connect(
            lambda: print("Obvi Checking update"))

        self.silent_update_signal.finished.connect(self.silent_update_notify)
        self.silent_update_signal.progress.connect(
            lambda: print("Silently Checking update"))

        self.download_update_widget = ProgressDialog(
            self.download_update_signal, parent=self)

        self.background_update_check()

        if self.settings_manager.onbrd_stps_completed >= len(self.onboarding_steps):
            self.settings_manager.is_first_run = False

        if self.settings_manager.is_first_run:
            self.begin_onboarding()
        else:
            if self.settings_manager.require_password:
                # 'and' another check (because this reg key can easily be manipulated.)
                self.lock_app()
                # self.lock.correct = False
                self.refresh_notes_list()
            else:
                # Unprotected entry
                if self.lock.validate_silent_password(self.lock.def_password):
                    self.unlock_app()
                else:
                    if self.lock.get_hashed() is not None:
                        # The password
                        self.settings_manager.require_password = True
                        self.lock_app(
                            "Some settings are being tampered with. Please enter your set password.")

    def begin_onboarding(self, next_step="set_password"):
        """Run the short first-run setup without changing vault security behavior."""
        if not self.settings_manager.is_first_run:
            return

        self.settings_manager.require_password = True
        self.lock = PasswordManager(
            db=self.db,
            settings_manager=self.settings_manager,
            new=True,
            parent=self,
        )
        self.lock.set_message(
            f"Welcome to {APP_NAME}. Choose a memorable but hard-to-guess password. "
            "The hint is optional; use a reminder that does not reveal your password. "
            "Your password encrypts your notes. If you forget it, the notes cannot "
            "be recovered; the only reset is deleting the local notes vault.",
            "#19d819",
        )
        self.lock.password_hint_input.setToolTip(
            "Optional reminder. Do not put the password itself in the hint."
        )
        self.lock.exec()

        if not self.lock.correct:
            sys.exit(0)
            return

        self.settings_manager.onbrd_stps_completed = len(self.onboarding_steps)
        self.settings_manager.is_first_run = False
        self.refresh_notes_list()

    def get_all_notes_with_contents(self):
        """for search"""
        self.notes = self.db.get_all_notes_with_content()

    def encrypt(self, key, data):
        return self.lock.encrypt_note(key, data)

    def decrypt(self, key, data):
        return self.lock.decrypt_note(key, data)

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
                if ((re.search(search_term, f"{note_}: {self.decrypt(self.lock.crypto.dek, note['content'])}", re.IGNORECASE) is not None)):
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
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
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

        self.notes_toggle_btn = QPushButton("☰")
        self.notes_toggle_btn.setToolTip("Hide or show the notes list")
        self.notes_toggle_btn.clicked.connect(self.toggle_notes_sidebar)
        sidebar_layout.addWidget(self.notes_toggle_btn)

        notes_list_sidebar = QWidget()
        notes_list_sidebar.setMinimumWidth(160)
        notes_list_sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.notes_list_sidebar = notes_list_sidebar

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
        # self.refresh_actions_UI()
        # self.lock_app_btn.hide()

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

        # The splitter lets users resize the notes list without affecting note content.
        self.notes_splitter = QSplitter(Qt.Horizontal, self)
        self.notes_splitter.setChildrenCollapsible(False)
        self.notes_splitter.addWidget(notes_list_sidebar)

        # ===========================
        # Workspace
        # ===========================

        workspace = QWidget()
        self.stack = QVBoxLayout(workspace)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(0)

        # Editor

        self.title_entry = QLineEdit()
        self.title_entry.setPlaceholderText("Title...")
        self.title_entry.returnPressed.connect(
            lambda: self.editor.setFocus())
        self.title_entry.textChanged.connect(
            self.trigger_autosave
        )

        self.editor = QTextEdit()
        self.markdown_editor = PlainTextMarkdownAdapter(self.editor)
        self.editor.setPlaceholderText("Think...")
        self.editor.textChanged.connect(
            self.trigger_autosave
        )
        self.editor_font = QFont("sans-serif")
        self.editor.setFontPointSize(self.main_text_size)
        self.editor.setFont(self.editor_font)

        self.title_entry.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stack.addWidget(self.title_entry)
        self.stack.addWidget(self.editor, 1)

        self.notes_splitter.addWidget(workspace)
        self.notes_splitter.setStretchFactor(0, 0)
        self.notes_splitter.setStretchFactor(1, 1)
        self.notes_splitter.setSizes([250, 900])
        main_layout.addWidget(self.notes_splitter, 1)

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
        self.update_btn.clicked.connect(self.download_update)
        self.update_btn.hide()
        self.statusArea.addPermanentWidget(self.update_btn)

        help_menu.addAction(self.buy_action)
        help_menu.addAction(self.update_check_action)

        # Quick settings shown in statusArea
        self.enablePassword = QPushButton("Enable Password")
        self.enableAutolock = QPushButton("Enable Autolock")

        def enpass():
            self.settings_dialog = SettingsDialog(
                self.db, PasswordManager, parent=self)
            self.settings_dialog.manage_pass_request_at_startup()
            if self.settings_manager.require_password:
                self.inform_user(
                    f"Your {APP_NAME} is now Password Protected. Ensure you remember your password.")
            else:
                # leave the button there,
                return
            self.enablePassword.hide()

        def enautolock():
            self.settings_dialog = SettingsDialog(
                self.db, PasswordManager, parent=self)

            self.settings_dialog.manage_autolock_setup()
            if self.settings_manager.autolock_enabled:
                self._install_autolock_timer()

            self.inform_user(
                f"After {self.settings_manager.autolock_minutes} minutes of inactivity, your {APP_NAME} will automatically lock.")
            self.enableAutolock.hide()

        self.enablePassword.clicked.connect(enpass)
        self.enablePassword.setStyleSheet("color:#ccc;")
        self.enablePassword.hide()

        self.enableAutolock.clicked.connect(enautolock)
        self.enableAutolock.setStyleSheet("color:#ccc;")
        self.enableAutolock.hide()

        self.statusArea.addPermanentWidget(self.enablePassword)
        self.statusArea.addPermanentWidget(self.enableAutolock)

    def toggle_notes_sidebar(self):
        """Hide or restore the notes list while keeping its contents intact."""
        visible = self.notes_list_sidebar.isVisible()
        self.notes_list_sidebar.setVisible(not visible)
        self.notes_toggle_btn.setToolTip(
            "Show the notes list" if visible else "Hide the notes list"
        )

    def start_autolock_engine(self):
        # Autolock Timer
        if self.settings_manager.autolock_enabled:
            if self.is_premium_user():
                self._install_autolock_timer()
    
    def _install_autolock_timer(self):
        """Instantiate the autolock timer: This is for when autolock is turned on, everytime the setting is true, whether from settings or from reading from the reg, then this is what instantiates the timer, so that the user doesn't have to restart the app for timer to take effect"""
        self.autolock_timer.timeout.connect(self.lock_app)
        self._set_autolock_timer_interval()
        self.master.installEventFilter(self.autolock_event_listener)

    def loader(self, percent: int):
        self.download_update_widget.update_progress(percent,
                                                    f"Updating {APP_NAME}...")
        self.master.processEvents()

    def clean_up_cancelled_download(self):
        self.download_update_widget.close()
        self.autoupdate_checker.cleanup_cancelled_download()
        self.inform_user("Update Cancelled")

    def download_update(self):
        """What to do when the user hits the update app btn"""

        self.download_update_signal.finished.connect(self.launch_installer)
        self.download_update_signal.update_percent.connect(
            lambda e: self.loader(e))
        self.download_update_signal.update_cancelled.connect(
            self.clean_up_cancelled_download)

        download_thread = threading.Thread(target=self.autoupdate_checker.download_update, args=(
            self.download_update_signal,), daemon=True, name="download_thread")

        download_thread.start()
        self.download_update_widget.exec()

    def launch_installer(self):
        print("Launching installer")
        self.autoupdate_checker.launch_installer()

    def background_update_check(self):
        """Silently Give notification for the availability"""
        # Assume everything is silent.

        silent_update_checker = threading.Thread(
            target=self.autoupdate_checker._check, name="background_check_thread", args=(self.silent_update_signal,), daemon=True)
        silent_update_checker.start()

    def obvi_update_check(self):
        """Give notification for the availability"""
        self.inform_user("Checking for updates now...")
        loud_update_checker = threading.Thread(
            target=self.autoupdate_checker._check, args=(self.loud_update_signal,), name="obvious_check_thread", daemon=True)
        loud_update_checker.start()

    def silent_update_notify(self):
        if self.autoupdate_checker.get_update_available():
            self.inform_user(
                f"Update available. Your {APP_NAME} needs an update to stay secure.")
            self.update_btn.show()
        elif self.autoupdate_checker.get_update_available() is False:
            # self.inform_user("No update available yet")
            self.update_btn.hide()
        elif self.autoupdate_checker.get_update_available() is None:
            # silently fail.
            # self.inform_user("No connection to check for updates")
            print("No internet")
            pass

    def loud_update_notify(self):
        if self.autoupdate_checker.get_update_available():
            a = QMessageBox()
            a.setIcon(a.Icon.Information)
            a.setWindowTitle(f"{APP_NAME} update is available")
            a.setText(
                f"{APP_NAME} needs an update. Do you want to install updates now?\n\n")
            update = a.addButton("Yes", a.ButtonRole.AcceptRole)
            # Do the actual download. same as the subtle statusArea button
            update.clicked.connect(self.download_update)
            a.addButton("No", a.ButtonRole.RejectRole)
            a.exec()
        elif self.autoupdate_checker.get_update_available() is False:
            a = QMessageBox.information(None, f"{APP_NAME} is Up to Date",
                                        f"{APP_NAME} is Up to date.")
        else:
            QMessageBox.critical(
                None, "Something happened", f"Update checking encountered a problem, might be from our server or an internet connection problem. Try checking for updates later.")

    def open_license_buy(self):
        """Manage Licenser"""

        self.license_man._show_license_window()

    def open_donation_box(self):
        # What is the ruling on asking for donations
        pass

    def ask_question(self, title, message, type_="info"):
        """Usage: 

        question = ask_question(title, message)
        question.addButton("yes", ...)
        question.exec()

        returns: the QMessageBox() object"""
        a = QMessageBox()
        if "info" in type_:
            a.setIcon(a.Icon.Information)
        elif "warn" in type_:
            a.setIcon(a.Icon.Warning)
        elif "criti" in type_ or "err" in type_:
            a.setIcon(a.Icon.Critical)

        a.setWindowTitle(f"{title}")
        a.setText(f"{message}")
        return a

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

    def lock_app(self, optional_msg=""):
        self.editor.blockSignals(True)
        self.title_entry.blockSignals(True)
        self.autolock_timer.blockSignals(True)
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
        # self.lock.set_message(optional_msg)
        # self.lock.set_message(optional_msg)
        self.lock.exec()
        if not self.lock.correct:
            self.master.exit(0)
            sys.exit(0)
            return
        else:
            self.unlock_app()

    def refresh_actions_UI(self):
        # self.action_sidebar.clear()
        for act in self.app_actions:
            if "new" in act.lower():
                self.action_sidebar.addWidget(self.new_note_btn)
                self.new_note_btn.show()

            elif "del" in act.lower():
                self.action_sidebar.addWidget(self.del_note_btn)
                self.del_note_btn.show()

            elif "lock" in act.lower():
                if self.settings_manager.require_password:
                    self.action_sidebar.addWidget(self.lock_app_btn)
                    self.lock_app_btn.show()
                else:
                    self.lock_app_btn.hide()

    def unlock_app(self):
        self.db = DatabaseManager()
        self.refresh_notes_list()
        # self.refresh_actions_UI()
        self.editor.setFocus()
        self.editor.blockSignals(False)
        self.title_entry.blockSignals(False)
        self.autolock_timer.blockSignals(False)


    def after_settings_exit(self):
        """After we exit settings, this func will refresh the UI by checking all setting and applying those changes"""
        # self.refresh_actions_UI() XXX
        self.refresh_notes_list()

        if not self.settings_manager.autolock_enabled:
            self.inform_user(
                "It is recommended to enable autolock if you tend to be forgetful.")
            self.remind_user_autolock()
            try:
                self.master.removeEventFilter(self.autolock_event_listener)
            except Exception as e:
                print(e)

        else:
            if self.enableAutolock.isVisible():
                self.enableAutolock.hide()
            # Do the actual enabling of the autolock
            self.start_autolock_engine()

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

    def _set_autolock_timer_interval(self):
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
        # XXX XXX XXX XXX: TODO: TODO
        # return self.license_man.is_premium_user()
        return True

    def inform_user(self, info, col="#f6f6f6", for_secs=8):
        self.statusArea.showMessage(info, for_secs*1000)
        self.statusArea.setStyleSheet(f"color:{col};")

    def auto_save_note(self):
        c_title = self.title_entry.text()
        c_content = self.markdown_editor.read_source()

        self.editor.setFontPointSize(self.main_text_size)

        # ensure there's something before saving.
        if c_content.strip():
            c_content = self.encrypt(
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

        self.remind_user_protection()
        self.remind_user_autolock()

        self.select_note(self.current_note_id)

        # zoom must be maintained
        self.editor.setFontPointSize(self.main_text_size)

        # print("autosaved")

    def remind_user_autolock(self):
        """Subtly remind a user when autosaving that they might leave the app open by mistake. Prompt them by placing a button that enables autolock right there; place that button on the statusArea.

        This enables `autolock` setting. And they will be asked same way they would be asked in settings.
        """
        msg = f"Turn on Autolock just incase you leave your {APP_NAME} open by mistake."

        # Remind user subtly about if his app is not set to autolock.
        if (self.settings_manager.require_password and not self.settings_manager.autolock_enabled) and (self.settings_manager.warn_if_unprotected):

            self.enableAutolock.show()
            if self.times_reminded_about_autolock < 3:
                self.inform_user(msg, "#FF2424")
                self.times_reminded_about_autolock += 1
            elif (self.times_reminded_about_autolock > 3) and (self.times_reminded_about_password_protection < 6):
                self.inform_user(
                    msg, "#656565")
                self.times_reminded_about_autolock += 1
            else:
                # Leave the enable password button there.
                # when they decide, they can enable it.
                pass

        if not self.settings_manager.require_password:
            self.enableAutolock.hide()

    def remind_user_protection(self):
        """Subtly remind a user when autosaving that they are currently not password protected. Prompt them by placing a button that enables protection right there; place that button on the statusArea.

        This enables require_password setting.
        """

        # Remind user subtly about if his notes are not protected.
        if (not self.settings_manager.require_password) and (self.settings_manager.warn_if_unprotected):
            self.enablePassword.show()
            # require_password being false implies autolock being false.
            # require_password being true implies autolock being either true or false.

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

    def zoom(self, type_):
        tmp = ""
        if "in" in type_:
            # print(type_)
            self.main_text_size += 2
            tmp = self.markdown_editor.read_source()
            self.editor.blockSignals(True)
            self.editor.selectAll()
            self.editor.setFontPointSize(self.main_text_size)
            self.editor.insertPlainText(tmp)

        elif "out" in type_:
            # print(type_)
            self.main_text_size -= 2
            tmp = self.markdown_editor.read_source()
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
        c_content = ""
        if self.current_note_id is None:
            title = self.title_entry.text()
            c_content = self.markdown_editor.read_source()

        self.current_note_id = None

        if c_content.strip():
            c_content = self.lock.encrypt_note(
                self.lock.crypto.dek, c_content)

        note_id = self.db.create_note(title, c_content)

        self.current_note_id = note_id

        # self.display_note_content()

        if (not title.strip()):
            self.title_entry.setText("Untitled")
            if not c_content.strip():
                self.editor.clear()
                self.title_entry.setFocus()
                self.title_entry.selectAll()
            return

        self.refresh_notes_list()
        self.select_note(note_id)

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
                c_content = self.decrypt(
                    self.lock.crypto.dek, c_content)
            else:
                self.editor.setPlaceholderText(
                    "Write like an independent thinker...")
        except Exception as e:
            print(e)
            self.editor.setPlaceholderText(
                "Sorry, this note is empty and not decryptable, it can be lost forever.")

        # Prevent autosave from firing while loading

        self.editor.blockSignals(True)
        self.title_entry.blockSignals(True)
        self.title_entry.setText(self.title)
        self.markdown_editor.load_source(c_content)
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

    def confirm_exit_without_protection(self):
        """Always check when exiting, whether protection is on or not, warn the user to turn on protection if warn if not protected setting is on else, just exit like that."""
        # If warn_if_not_protected is on then check
        
        if self.settings_manager.warn_if_unprotected:
            print("about to warn", self.settings_manager.require_password)
            if not self.settings_manager.require_password:
                print("Hey")
                # self.inform_user(
                #     f"Warning: Anyone can access your notes, the next time you open your {APP_NAME}")
                self.ask_question(
                    "Warning: Not Password Protected",
                    f"Warning: Anyone can access your notes, the next time {APP_NAME} is opened.\n\nAre you sure you want to exit without protection?")
                

    def abouttoquit(self):
        """What to do when user is leaving"""
        self.confirm_exit_without_protection()
        print("bye")


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_PHOTO)))
    window = NoteApp(app)
    app.aboutToQuit.connect(window.abouttoquit)
    window.setWindowIcon(QIcon(str(APP_PHOTO)))
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
