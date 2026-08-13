from __future__ import annotations

from typing import Any, Callable, Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


class _Worker(QObject):
    """
    Internal QObject that executes the target function.

    This class should not be used directly.
    """

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)
    cancelled = pyqtSignal()

    def __init__(
        self,
        target: Callable[..., Any],
        args: tuple,
        kwargs: dict,
    ):
        super().__init__()

        self.target = target
        self.args = args
        self.kwargs = kwargs

        self._cancel_requested = False

    def request_cancel(self):
        """
        Request cancellation.

        This does NOT forcibly kill the running function.

        The target function must cooperate with cancellation if
        cancellation is required.
        """
        self._cancel_requested = True

    def is_cancelled(self) -> bool:
        """
        Allows the target function to check whether cancellation
        was requested.
        """
        return self._cancel_requested

    @pyqtSlot()
    def run(self):
        """
        Execute the target function inside the worker thread.
        """

        try:
            result = self.target(
                *self.args,
                **self.kwargs,
            )

            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.finished.emit(result)

        except Exception as exc:
            self.error.emit(exc)


class QtThreadRunner(QObject):
    """
    Reusable PyQt5 threading abstraction.

    Example:

        runner = QtThreadRunner(
            target=my_function,
            args=(arg1,),
            kwargs={"name": "BMTB"},
        )

        runner.progress.connect(self.update_progress)
        runner.finished.connect(self.task_finished)
        runner.error.connect(self.task_failed)

        runner.start()

    The target function runs outside the GUI thread.

    Signals are emitted back through Qt's signal/slot system.
    """

    progress = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(Exception)
    cancelled = pyqtSignal()

    started = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(
        self,
        target: Callable[..., Any],
        args: tuple = (),
        kwargs: Optional[dict] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        if not callable(target):
            raise TypeError(
                "target must be callable."
            )

        self.target = target
        self.args = args
        self.kwargs = kwargs or {}

        self._thread: Optional[QThread] = None
        self._worker: Optional[_Worker] = None

        self._running = False
        self._finished = False
        self._cancelled = False

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def start(self):
        """
        Start the target function in a background thread.
        """

        if self._running:
            raise RuntimeError(
                "Thread is already running."
            )

        self._create_thread()

        self._running = True
        self._finished = False
        self._cancelled = False

        self.started.emit()

        self._thread.start()

    def cancel(self):
        """
        Request cancellation.

        The target function must cooperate by checking
        the cancellation state.

        This does NOT forcibly terminate the thread.
        """

        if not self._running:
            return

        if self._worker is not None:
            self._worker.request_cancel()

        self._cancelled = True

    def is_running(self) -> bool:
        """
        Return True if the background task is running.
        """

        return self._running

    def is_finished(self) -> bool:
        """
        Return True if the task has completed.
        """

        return self._finished

    def is_cancelled(self) -> bool:
        """
        Return True if cancellation was requested.
        """

        return self._cancelled

    def wait(self, timeout: Optional[int] = None):
        """
        Wait for the thread to finish.

        timeout:
            milliseconds

        WARNING:
            Do not call this from the GUI thread unless you
            intentionally want to block the UI.
        """

        if self._thread is None:
            return True

        if timeout is None:
            return self._thread.wait()

        return self._thread.wait(timeout)

    # ==========================================================
    # THREAD CREATION
    # ==========================================================

    def _create_thread(self):
        """
        Create and configure QThread + worker.
        """

        self._thread = QThread()

        self._worker = _Worker(
            target=self.target,
            args=self.args,
            kwargs=self.kwargs,
        )

        # Move worker into the background thread.
        self._worker.moveToThread(self._thread)

        # Thread starts → worker executes target.
        self._thread.started.connect(
            self._worker.run
        )

        # Worker signals → public runner signals.
        self._worker.progress.connect(
            self.progress.emit
        )

        self._worker.finished.connect(
            self._handle_finished
        )

        self._worker.error.connect(
            self._handle_error
        )

        self._worker.cancelled.connect(
            self._handle_cancelled
        )

        # Worker completion → thread shutdown.
        self._worker.finished.connect(
            self._thread.quit
        )

        self._worker.error.connect(
            self._thread.quit
        )

        self._worker.cancelled.connect(
            self._thread.quit
        )

        # Thread finished → cleanup.
        self._thread.finished.connect(
            self._handle_thread_finished
        )

        self._thread.finished.connect(
            self._thread.deleteLater
        )

        self._worker.finished.connect(
            self._worker.deleteLater
        )

        self._worker.error.connect(
            self._worker.deleteLater
        )

        self._worker.cancelled.connect(
            self._worker.deleteLater
        )

    # ==========================================================
    # INTERNAL SIGNAL HANDLERS
    # ==========================================================

    @pyqtSlot(object)
    def _handle_finished(self, result):
        """
        Handle successful completion.
        """

        self._finished = True

        self.finished.emit(result)

    @pyqtSlot(Exception)
    def _handle_error(self, exception):
        """
        Handle target-function exceptions.
        """

        self._finished = True

        self.error.emit(exception)

    @pyqtSlot()
    def _handle_cancelled(self):
        """
        Handle cancellation.
        """

        self._finished = True

        self.cancelled.emit()

    @pyqtSlot()
    def _handle_thread_finished(self):
        """
        Final cleanup after QThread exits.
        """

        self._running = False

        self.stopped.emit()

        self._thread = None
        self._worker = None

    # ==========================================================
    # DESTRUCTOR SAFETY
    # ==========================================================

    def __del__(self):
        """
        Best-effort cleanup.

        Normally the thread should already have completed before
        this object is destroyed.
        """

        if self._thread is not None:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait()