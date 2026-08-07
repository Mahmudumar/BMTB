from PyQt5.QtCore import QSettings


class PremiumTracker(QSettings):
    PREMIUM_REMINDERS_GIVEN = "premium_reminders_given"
    PREMIUM_LICENSE_KEY = "license_key"
    PREMIUM_NOTE_COUNT = "note_count"

    def __init__(self, db, parent=None):
        super().__init__("BM", "BMTB/PremiumTracker", parent=None)
        self.db = db
        self.master = parent

    def registy_intact(self, key):
        """Check if key is intact in registry"""
        if key in self.allKeys():
            return True
        return False

    @property
    def reminders_given(self) -> int:
        return self.value(f"{self.PREMIUM_REMINDERS_GIVEN}", 0, type=int)

    @reminders_given.setter
    def reminders_given(self, value: int):
        self.setValue(f"{self.PREMIUM_REMINDERS_GIVEN}", value)

    @property
    def note_count(self) -> int:
        return self.value(f"{self.PREMIUM_NOTE_COUNT}", 0, type=int)

    @note_count.setter
    def note_count(self, value: int):
        self.setValue(f"{self.PREMIUM_NOTE_COUNT}", value)

    @property
    def license_key(self) -> str:
        return self.value(f"{self.PREMIUM_LICENSE_KEY}", None, type=str)

    @license_key.setter
    def license_key(self, value: str):
        self.setValue(f"{self.PREMIUM_LICENSE_KEY}", value)
