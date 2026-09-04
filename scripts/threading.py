from __future__ import annotations
from PyQt5.QtCore import QObject, pyqtSignal

class Signals(QObject):
    progress = pyqtSignal(str)
    update_percent = pyqtSignal(int)
    update_cancelled = pyqtSignal()
    finished = pyqtSignal()

