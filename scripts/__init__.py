"""Don't know why packages are just annoying."""
from PyQt5.QtCore import QSettings


class Settings(QSettings):
    REQUIRE_PASSWORD = "security/require_password"
    AUTOLOCK_ENABLED = "security/autolock_enabled"
    AUTOLOCK_MINUTES = "security/autolock_minutes"
    WARN_UPROTECTED = "security/warn_if_unprotected"

    PASSWORD_VERSION = "security/p_hash_1"
    PASSWORD_HINT = "security/p_hint_hash"
    LICENSE_KEY = "security/license_key"
    LICENSE_DATA = "security/license_data"
    KEY = "security/key_1"

    EDITOR_FONT_SIZE = "editor/font_size"

    IS_FIRST_RUN = "system/is_first_run"
    UPDATE_REMINDERS_GIVEN = "system/update_reminders_given"
    ONBOARDING_STEPS = "system/onboarding_steps_completed"
    NUMBER_OF_OPENS = "system/number_of_app_opens"

    def __init__(self, db=None, parent=None):
        super().__init__("BM", "BMTB", parent=None)
        self.db = db
        self.master = parent
        # print(self.settings_intact())

    def setting_intact(self, setting_constant):
        """Check if the key is in settings and hasn't been deleted"""
        if setting_constant in self.allKeys():
            return True
        return False

    @property
    def onbrd_stps_completed(self):
        return self.value(f"{self.ONBOARDING_STEPS}", 0, type=int)

    @onbrd_stps_completed.setter
    def onbrd_stps_completed(self, value):
        self.setValue(f"{self.ONBOARDING_STEPS}", value)

    @property
    def update_reminders_given(self):
        return self.value(f"{self.UPDATE_REMINDERS_GIVEN}", 0, type=int)

    @update_reminders_given.setter
    def update_reminders_given(self, value):
        self.setValue(f"{self.UPDATE_REMINDERS_GIVEN}", value)

    @property
    def warn_if_unprotected(self):
        return self.value(f"{self.WARN_UPROTECTED}", True, type=bool)

    @warn_if_unprotected.setter
    def warn_if_unprotected(self, value):
        self.setValue(f"{self.WARN_UPROTECTED}", value)

    @property
    def number_of_opens(self) -> int:
        return self.value(f"{self.NUMBER_OF_OPENS}", 0, type=int)

    @number_of_opens.setter
    def number_of_opens(self, value: int):
        self.setValue(f"{self.NUMBER_OF_OPENS}", value)

    @property
    def editor_font_size(self) -> int:
        return self.value(f"{self.EDITOR_FONT_SIZE}", 10, type=int)

    @editor_font_size.setter
    def editor_font_size(self, value: int):
        self.setValue(f"{self.EDITOR_FONT_SIZE}", value)

    @property
    def password_version(self) -> str:
        return self.value(f"{self.PASSWORD_VERSION}", "", type=str)

    @password_version.setter
    def password_version(self, value: str):
        self.setValue(f"{self.PASSWORD_VERSION}", value)

    @property
    def password_hint(self) -> str:
        return self.value(f"{self.PASSWORD_HINT}", "", type=str)

    @password_hint.setter
    def password_hint(self, value: str):
        self.setValue(f"{self.PASSWORD_HINT}", value)

    @property
    def user_license_key(self) -> str:
        return self.value(f"{self.LICENSE_KEY}", "", type=str)

    @user_license_key.setter
    def user_license_key(self, value: str):
        self.setValue(f"{self.LICENSE_KEY}", value)

    @property
    def user_license_data(self) -> str:
        return self.value(f"{self.LICENSE_DATA}", "", type=str)

    @user_license_data.setter
    def user_license_data(self, value: str):
        self.setValue(f"{self.LICENSE_DATA}", value)

    @property
    def crypto_key(self) -> str:
        return self.value(f"{self.KEY}", "", type=str)

    @crypto_key.setter
    def crypto_key(self, value: str):
        self.setValue(f"{self.KEY}", value)

    @property
    def is_first_run(self) -> bool:
        return self.value(f"{self.IS_FIRST_RUN}", False, type=bool)

    @is_first_run.setter
    def is_first_run(self, value: bool):
        self.setValue(f"{self.IS_FIRST_RUN}", value)

    @property
    def autolock_minutes(self) -> int:
        return self.value(f"{self.AUTOLOCK_MINUTES}", 5, type=int)

    @autolock_minutes.setter
    def autolock_minutes(self, value):
        self.setValue(f"{self.AUTOLOCK_MINUTES}", value)

    @property
    def autolock_enabled(self) -> bool:
        return self.value(f"{self.AUTOLOCK_ENABLED}", True, type=bool)

    @autolock_enabled.setter
    def autolock_enabled(self, value: bool):
        self.setValue(f"{self.AUTOLOCK_ENABLED}", value)

    @property
    def require_password(self) -> bool:
        return self.value(f"{self.REQUIRE_PASSWORD}", True, type=bool)

    @require_password.setter
    def require_password(self, value: bool):
        self.setValue(f"{self.REQUIRE_PASSWORD}", value)


if __name__ == "__main__":
    Settings(None)
