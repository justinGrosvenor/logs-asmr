"""Audio state machine — MUTED / IDLE / HEALTHY / WARNING / ALARM."""

from __future__ import annotations

import enum
import logging
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from logs_asmr.constants import (
    ALARM_COOLDOWN_SECONDS,
    ERROR_RATE_ALARM_THRESHOLD,
    ERROR_RATE_WINDOW_SECONDS,
    WARNING_COOLDOWN_SECONDS,
)

logger = logging.getLogger("logs_asmr.audio.state_machine")


class AudioState(enum.Enum):
    MUTED = "muted"
    IDLE = "idle"
    HEALTHY = "healthy"
    WARNING = "warning"
    ALARM = "alarm"


class AudioStateMachine(QObject):
    """Manages audio state transitions based on error rate over a sliding window."""

    state_changed = pyqtSignal(str)  # AudioState.value

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = AudioState.IDLE
        self._error_timestamps: list[float] = []
        self._last_high_rate_time = 0.0  # last time rate was above alarm threshold
        self._last_any_error_time = 0.0  # last time rate was above zero

        # Cooldown timer — checks if we should transition based on error rate
        self._cooldown_timer = QTimer(self)
        self._cooldown_timer.setInterval(1000)
        self._cooldown_timer.timeout.connect(self._check_cooldown)

    @property
    def state(self) -> AudioState:
        return self._state

    def set_muted(self, muted: bool) -> None:
        """Toggle mute state."""
        if muted:
            self._transition(AudioState.MUTED)
        else:
            self._transition(AudioState.IDLE)

    def set_streaming(self, streaming: bool) -> None:
        """Notify that streaming has started/stopped."""
        if self._state == AudioState.MUTED:
            return
        if streaming:
            self._transition(AudioState.HEALTHY)
        else:
            self._transition(AudioState.IDLE)

    def on_error_batch(self, error_count: int) -> None:
        """Called each processing tick with the number of errors in the batch."""
        if self._state in (AudioState.MUTED, AudioState.IDLE):
            return

        now = time.monotonic()

        # Record error timestamps
        for _ in range(error_count):
            self._error_timestamps.append(now)

        # Prune old timestamps and evaluate rate
        self._evaluate_rate(now)

    def _evaluate_rate(self, now: float) -> None:
        """Compute error rate and transition upward if needed."""
        cutoff = now - ERROR_RATE_WINDOW_SECONDS
        self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]

        rate = len(self._error_timestamps) / ERROR_RATE_WINDOW_SECONDS

        if rate > ERROR_RATE_ALARM_THRESHOLD:
            self._last_high_rate_time = now
            self._last_any_error_time = now
            if self._state != AudioState.ALARM:
                self._transition(AudioState.ALARM)
        elif rate > 0:
            self._last_any_error_time = now
            if self._state == AudioState.HEALTHY:
                self._transition(AudioState.WARNING)

    def _transition(self, new_state: AudioState) -> None:
        if new_state == self._state:
            return

        old = self._state
        self._state = new_state
        logger.debug("Audio state: %s -> %s", old.value, new_state.value)
        self.state_changed.emit(new_state.value)

        # Manage cooldown timer
        if new_state in (AudioState.HEALTHY, AudioState.WARNING, AudioState.ALARM):
            self._cooldown_timer.start()
        elif new_state in (AudioState.MUTED, AudioState.IDLE):
            self._cooldown_timer.stop()

    def _check_cooldown(self) -> None:
        """Periodic check to transition downward after cooldown."""
        now = time.monotonic()

        # Re-evaluate current rate
        cutoff = now - ERROR_RATE_WINDOW_SECONDS
        self._error_timestamps = [t for t in self._error_timestamps if t > cutoff]

        rate = len(self._error_timestamps) / ERROR_RATE_WINDOW_SECONDS

        if self._state == AudioState.ALARM:
            # Only step down if rate dropped below alarm AND cooldown elapsed
            if rate <= ERROR_RATE_ALARM_THRESHOLD:
                if now - self._last_high_rate_time >= ALARM_COOLDOWN_SECONDS:
                    if rate > 0:
                        self._transition(AudioState.WARNING)
                    else:
                        self._transition(AudioState.HEALTHY)

        elif self._state == AudioState.WARNING:
            if rate == 0 and now - self._last_any_error_time >= WARNING_COOLDOWN_SECONDS:
                self._transition(AudioState.HEALTHY)
